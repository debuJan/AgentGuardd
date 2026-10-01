"""Tests for the fixed-window per-IP rate limiting middleware."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rate_limit import (
    RateLimitMiddleware,
    parse_limit,
    settings_from_env,
)


def _make_client(**kwargs) -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/items")
    def items():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, **kwargs)
    return TestClient(app, raise_server_exceptions=False)


def test_parse_limit_valid():
    assert parse_limit("200/minute") == (200, 60)
    assert parse_limit("10/second") == (10, 1)
    assert parse_limit("1000/hour") == (1000, 3600)
    assert parse_limit("5/seconds") == (5, 1)  # plural accepted


def test_parse_limit_invalid():
    for bad in ("nope", "10", "10/day", "0/minute", "-5/minute", ""):
        with pytest.raises(ValueError):
            parse_limit(bad)


def test_settings_from_env_defaults(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.delenv("AGENTGUARD_RATE_LIMIT", raising=False)
    assert settings_from_env() == {
        "enabled": True,
        "limit": 200,
        "window_seconds": 60,
    }


def test_settings_from_env_custom(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_RATE_LIMIT", "50/hour")
    monkeypatch.setenv("AGENTGUARD_RATE_LIMIT_ENABLED", "false")
    assert settings_from_env() == {
        "enabled": False,
        "limit": 50,
        "window_seconds": 3600,
    }


def test_allows_requests_under_limit():
    client = _make_client(limit=5, window_seconds=60)
    for _ in range(5):
        r = client.get("/items")
        assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "5"
    assert r.headers["X-RateLimit-Remaining"] == "0"


def test_blocks_requests_over_limit_with_retry_after():
    client = _make_client(limit=2, window_seconds=60)
    assert client.get("/items").status_code == 200
    assert client.get("/items").status_code == 200
    r = client.get("/items")
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 1
    assert "rate limit" in r.json()["detail"].lower()


def test_health_is_never_throttled():
    client = _make_client(limit=1, window_seconds=60)
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_limits_are_per_ip_via_forwarded_for():
    client = _make_client(limit=1, window_seconds=60)
    assert client.get("/items", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 200
    # Same IP is now throttled...
    assert client.get("/items", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
    # ...but a different client IP gets its own bucket.
    assert client.get("/items", headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 200


def test_disabled_middleware_passes_everything():
    client = _make_client(limit=1, window_seconds=60, enabled=False)
    for _ in range(5):
        assert client.get("/items").status_code == 200
