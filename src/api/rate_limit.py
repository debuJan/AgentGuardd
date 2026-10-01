"""Fixed-window per-IP rate limiting as pure ASGI middleware.

No third-party dependencies. Configured via environment:

- ``AGENTGUARD_RATE_LIMIT_ENABLED``: "true"/"false" (default "true").
- ``AGENTGUARD_RATE_LIMIT``: "<requests>/<unit>", e.g. "200/minute",
  "1000/hour", "10/second" (default "200/minute").

Liveness and documentation routes are always exempt so orchestrators,
load-balancer health probes, and the API docs can never be throttled:
``/health``, ``/docs``, ``/openapi.json``, ``/redoc``.

When the limit is exceeded the middleware short-circuits with
``429 Too Many Requests`` and a ``Retry-After`` header (seconds until the
window resets). It is intentionally conservative: with multiple uvicorn
workers each worker keeps its own counters, so the effective cluster-wide
limit is ``workers × limit``. For strict distributed limiting, terminate
at a reverse proxy / API gateway instead.

Client identity is the first entry of ``X-Forwarded-For`` when present
(the deployment sits behind a reverse proxy), otherwise the direct peer
address.
"""
from __future__ import annotations

import threading
import time

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Paths that must never be throttled.
EXEMPT_PATHS = ("/health", "/docs", "/openapi.json", "/redoc")

_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600}

DEFAULT_LIMIT = "200/minute"


def parse_limit(spec: str) -> tuple[int, int]:
    """Parse "<requests>/<unit>" into (max_requests, window_seconds)."""
    try:
        count_raw, unit_raw = spec.strip().lower().split("/", 1)
        count = int(count_raw)
        unit = unit_raw.rstrip("s")  # accept "seconds" as well as "second"
        window = _UNIT_SECONDS[unit]
    except (ValueError, KeyError, AttributeError) as exc:
        raise ValueError(
            f"Invalid rate limit {spec!r}: expected '<requests>/<second|minute|hour>', "
            f"e.g. '200/minute'."
        ) from exc
    if count < 1:
        raise ValueError(f"Invalid rate limit {spec!r}: request count must be >= 1.")
    return count, window


def settings_from_env() -> dict:
    """Read middleware settings from the environment (fail fast on bad config)."""
    import os

    enabled = os.getenv("AGENTGUARD_RATE_LIMIT_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    limit, window_seconds = parse_limit(os.getenv("AGENTGUARD_RATE_LIMIT", DEFAULT_LIMIT))
    return {"enabled": enabled, "limit": limit, "window_seconds": window_seconds}


def _client_ip(scope: Scope) -> str:
    headers = dict(scope.get("headers", []))
    forwarded = headers.get(b"x-forwarded-for")
    if forwarded:
        # First entry is the original client; the rest are proxies.
        return forwarded.decode("latin1").split(",")[0].strip() or "unknown"
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


class RateLimitMiddleware:
    """Fixed-window per-IP rate limiter."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limit: int = 200,
        window_seconds: int = 60,
        enabled: bool = True,
    ) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be >= 1")
        self.app = app
        self.limit = limit
        self.window_seconds = window_seconds
        self.enabled = enabled
        self._lock = threading.Lock()
        # ip -> [window_start_epoch, count]
        self._buckets: dict[str, list[float]] = {}

    def _prune(self, now: float) -> None:
        # Opportunistic cleanup so the bucket map cannot grow unboundedly.
        if len(self._buckets) > 10000:
            cutoff = now - self.window_seconds
            self._buckets = {
                ip: bucket
                for ip, bucket in self._buckets.items()
                if bucket[0] >= cutoff
            }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            not self.enabled
            or scope.get("type") != "http"
            or scope.get("path") in EXEMPT_PATHS
            or scope.get("path", "").startswith("/docs/")
        ):
            await self.app(scope, receive, send)
            return

        ip = _client_ip(scope)
        now = time.monotonic()
        retry_after = 0
        remaining = self.limit

        with self._lock:
            self._prune(now)
            bucket = self._buckets.get(ip)
            if bucket is None or now - bucket[0] >= self.window_seconds:
                bucket = [now, 0]
                self._buckets[ip] = bucket
            bucket[1] += 1
            remaining = max(0, self.limit - bucket[1])
            reset_at = bucket[0] + self.window_seconds
            if bucket[1] > self.limit:
                retry_after = max(1, int(reset_at - now))

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers["X-RateLimit-Limit"] = str(self.limit)
                headers["X-RateLimit-Remaining"] = str(remaining)
                headers["X-RateLimit-Reset"] = str(int(reset_at - time.monotonic()))
            await send(message)

        if retry_after:
            response = JSONResponse(
                {
                    "detail": "Rate limit exceeded. Try again in "
                    f"{retry_after} seconds."
                },
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send_with_headers)
