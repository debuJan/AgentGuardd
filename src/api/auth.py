"""Optional API-key authentication for production deployments.

If the ``AGENTGUARD_API_KEY`` environment variable is set, every route
except ``/health`` requires an ``X-API-Key`` header whose value matches it
(compared in constant time). If the variable is unset, authentication is
disabled — convenient for local development, and the reason production
deployments MUST set it (see .env.example).
"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status

_API_KEY_ENV = "AGENTGUARD_API_KEY"
_HEADER_NAME = "X-API-Key"


def get_configured_api_key() -> str:
    return os.environ.get(_API_KEY_ENV, "").strip()


async def require_api_key(x_api_key: str | None = Header(default=None, alias=_HEADER_NAME)) -> None:
    expected = get_configured_api_key()
    if not expected:
        return  # auth disabled: development mode
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
