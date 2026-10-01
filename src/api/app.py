import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.rate_limit import RateLimitMiddleware, settings_from_env
from src.api.routes import router

app = FastAPI(
    title="AI Agent Quality & Security Platform API",
    version="1.0.0",
)


def _cors_origins() -> list[str]:
    """Allowed CORS origins.

    ``AGENTGUARD_CORS_ORIGINS``: comma-separated list for production
    (e.g. "https://app.example.com"). Defaults to the local dev origins.
    Set to "*" only if you understand the implications; credentials are
    never allowed with a wildcard.
    """
    raw = os.environ.get("AGENTGUARD_CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last so it runs first (outermost): abusive traffic is rejected
# before touching routing, auth, or the database. /health stays exempt so
# orchestrators and load-balancer probes are never throttled.
app.add_middleware(RateLimitMiddleware, **settings_from_env())

app.include_router(router)
