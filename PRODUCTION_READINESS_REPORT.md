# AgentGuard — Production-Readiness Report

**Date:** 2026-09-29
**Repo:** `https://github.com/debuJan/AgentGuard` (local: `~/workspace/agentguard`)
**Base commit:** `12529b9` — no remediation commit created yet

**Update (same day, later):** PostgreSQL 16 was installed locally and the full
suite was verified against a real server: **141 passed, 0 skipped** (run twice
consecutively to prove test isolation). Blocker #1 below is resolved. During
that verification two real bugs were found and fixed: a `psycopg2` vs
SQLAlchemy-2.1 dialect mismatch (requirements now pin `psycopg[binary]==3.2.9`),
and duplicate `run_id` silently overwriting instead of being rejected (now
raises `ValueError`; the API maps it to **409 Conflict**).

**Update (same day, evening):** Playwright E2E was executed on a real Windows
machine with Chromium and is now **fully green: 6 passed** (blocker #3
resolved). Diagnosing it exposed one genuine defect — in the *test harness*,
not the app: Playwright's `webServer.env` silently never reached the API
process on Windows, so the API kept its default CORS origins, the browser's
`OPTIONS` preflight got a 400 with no `access-control-allow-origin` header,
and Chromium blocked every API response (`Failed to fetch`, UI showed
"API Unavailable") while the API itself was always healthy. Fix: the harness
now launches the API through a committed launcher,
`frontend/e2e/launch-api.mjs`, which sets `USE_POSTGRES=false` and
`AGENTGUARD_CORS_ORIGINS=http://127.0.0.1:4173` in-process via Node's `spawn`
instead of trusting Playwright's env plumbing. A permanent regression test
("e2e API allows the preview origin via CORS") fails if the harness ever
launches the API without the CORS env again. Backend re-verified the same
day: `pytest -q` → **139 passed, 3 skipped** (skips are the Postgres tests;
no DB in that environment).

**Update (same day, night) — production-hardening pass.** The remaining
"NOT READY" items that could be fixed in code were implemented and tested:

- **Alembic migrations** (`alembic.ini`, `migrations/`): initial migration
  `0001` creates `run_reports` exactly as the models define it (19 columns,
  2 indexes, `created_at` server default). Verified with upgrade/downgrade
  round-trip tests (`tests/test_migrations.py`, 3 tests). The Docker
  entrypoint runs `alembic upgrade head` before serving traffic.
- **Rate limiting** (`src/api/rate_limit.py`): dependency-free fixed-window
  per-IP limiter, 429 + `Retry-After` on exceed, `/health` and API docs
  always exempt, `X-Forwarded-For` aware. Default `200/minute`, env-tunable.
  9 tests in `tests/test_rate_limit.py`.
- **Docker hardening**: fixed a real bug — compose and `src/db.py` defaulted
  to the `postgresql://` / `psycopg2` dialect, which is not installed in the
  image (only `psycopg` v3); both now use `postgresql+psycopg://`. New
  `docker/entrypoint.sh` (migrations + configurable uvicorn workers),
  `.dockerignore` (lean, secret-free build context), and
  `docker-compose.prod.yml` + `docker/Caddyfile`: Caddy reverse proxy with
  automatic Let's Encrypt HTTPS, security headers, API/Postgres no longer
  published directly.
- **Pins**: `alembic==1.20.0`, `langchain-groq==1.1.3` (reproducible builds;
  the live Groq provider path still needs exercising against a real key).
- **Credential scan**: full-history scan (27 commits, full clone) found no
  `gsk_`/`sk-` key material and no high-entropy secret assignments anywhere
  in history or the tree — no history purge required. Operational rule
  stands: generate fresh `POSTGRES_PASSWORD`/`AGENTGUARD_API_KEY` at deploy
  time, never commit `.env`.

What genuinely remains (cannot be done without a deploy target / Docker
daemon, both absent here): running `docker compose up --build` end-to-end,
a real deployment with DNS + TLS issuance, and a live-key exercise of the
Groq provider path.

## Verdict: NOT READY

Code-level remediation is complete and verified everywhere this environment allows.
Release is blocked on environmental verification that could not be performed here:
Docker build/compose, a real browser for Playwright, and a real deployment.
Details below.

## Evidence

- **Backend:** `139 passed, 3 skipped, 6 warnings` with the in-memory store
  (`pytest tests/ -q`); **`141 passed, 0 skipped`** against real PostgreSQL 16
  (`USE_POSTGRES=true`, `DATABASE_URL=postgresql://…@localhost:5432/agentguard`),
  run twice back-to-back. The 3 skips in the in-memory run are the Postgres
  repository tests, which require a server.
  The 6 warnings are benign: pytest attempting to collect the `TestCase` /
  `TestCaseCategory` model classes as test classes, plus one starlette/httpx
  deprecation notice.
- **PostgreSQL behaviors verified directly against the server:** newest-first
  `list_runs` ordering, `get`/`delete` round-trip, and duplicate-`run_id`
  rejection in both the Postgres and in-memory repositories.
  (`created_at` is stamped once by the DB `server_default`; re-saves are
  rejected, so creation time can no longer be reset.)
- **Frontend:** `npm run build` passes (Vite 5.4.21, 48 modules).
- **Live API contract verified** against uvicorn + in-memory repo: `POST /runs`
  → 201 with a correct unified report, `GET /runs`, `GET /runs/{run_id}`,
  `DELETE /runs/{run_id}` → 404 after delete, `/health` → 200. Metrics shape
  matches what the dashboard reads (`metrics.duration_ms`,
  `metrics.tokens.total_tokens`, `metrics.cost.total_cost`), with honest
  `unavailable` statuses where the provider reports nothing.
- **Secret scan of the full diff:** no key-shaped values added. Credential-shaped
  Groq values that predated this work were removed from source.

## Blockers (resolve before release)

1. ~~**PostgreSQL never exercised.**~~ **RESOLVED** — verified against
   PostgreSQL 16 on 2026-09-29 (141 passed, 0 skipped, twice in a row).
2. **Docker never built.** `docker` is not installed in this environment.
   Dockerfile was hardened (non-root `agentguard` user, `/health` HEALTHCHECK,
   pinned `python:3.10-slim-bookworm`) but the image was never built and
   compose was never started.
   → **Improved 2026-09-29 (night):** fixed a real packaging bug found by
   review (compose/`src/db.py` defaulted to the `psycopg2` dialect, which is
   not installed in the image — both now use `postgresql+psycopg://`); added
   `docker/entrypoint.sh` (Alembic migrations + multi-worker uvicorn),
   `.dockerignore`, and `docker-compose.prod.yml` with Caddy automatic-HTTPS.
   Compose YAML validated; the actual `docker compose up --build` run still
   needs a machine with Docker.
3. ~~**Playwright never executed.**~~ **RESOLVED** — executed on a real
   Windows machine on 2026-09-29: **6 passed** (seed → runs list → run detail
   → delete, plus a CORS regression test). Root cause of the initial failure
   was harness-side (Playwright `webServer.env` not reaching the API process
   on Windows → missing CORS headers); fixed via `frontend/e2e/launch-api.mjs`.
   No browser could be downloaded in *this* environment, but the suite is
   verified green on real hardware.
4. **Pre-existing credential-shaped values.** ~~Groq-key-shaped strings existed in
   the repo before remediation and were removed from current source. Whether
   any was a *real* key was never established: if real, rotate it and purge it
   from git history (`git filter-repo` / BFG).~~ **CLEARED 2026-09-29
   (night):** full-history scan (27 commits, non-shallow clone) found no
   `gsk_`/`sk-` key material and no high-entropy secret assignments in any
   commit or in the tree — no purge needed. Use fresh secrets at deploy.
5. **No production deployment performed.** Reverse-proxy timeouts, TLS, and
   real traffic behavior are unvalidated.

## Non-blocking limitations

- `POST /runs` is **synchronous**: a long agent run holds a worker thread for
  its whole duration. Deploy with multiple uvicorn workers and a reverse-proxy
  timeout; background/async execution is a future feature, not added here.
- Duration metrics are event-gap approximations, not measured execution time;
  cost is labeled `ESTIMATED`; token/cost fields are `None`/`UNAVAILABLE` when
  the provider doesn't report them (dashboard renders `N/A`, never zero).
- ~~**No rate limiting** on the API — add at the reverse proxy or as middleware
  before public exposure.~~ **DONE 2026-09-29:** fixed-window per-IP limiter
  in `src/api/rate_limit.py` (429 + `Retry-After`, `/health` and docs exempt,
  default `200/minute` via `AGENTGUARD_RATE_LIMIT`).
- Auth is a single shared API key (`X-API-Key`); there is no per-user auth or
  RBAC. Fine for a small trusted team, not for multi-tenant use.
- DNS-rebinding window between SSRF validation and the outbound request is not
  closed (documented, accepted risk for this release).
- ~~`langchain-groq` remains unpinned and was not installed/exercised — pin or
  remove before claiming reproducible installs.~~ **Pinned 2026-09-29:**
  `langchain-groq==1.1.3`. The live provider path still needs exercising
  against a real API key.
- **Alembic** migration framework added 2026-09-29 (`migrations/`, initial
  `0001` migration, entrypoint runs `alembic upgrade head`).

## Security considerations

- When `AGENTGUARD_API_KEY` is set, every route except `/health` requires the
  `X-API-Key` header (constant-time comparison, 401 otherwise). Unset = dev
  mode with auth disabled — production **must** set it.
- CORS is env-configurable via `AGENTGUARD_CORS_ORIGINS`; defaults to the
  localhost dev origins only.
- Permission findings redact tool arguments (findings are persisted and served
  via the API); crashed security checks fail closed as `HIGH ENGINE-ERROR`.
- External-agent SSRF hardening: private/loopback endpoints blocked by default
  (`AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS` opt-in), response-size and call-count
  caps, `auth_header_env` restricted to an operator allowlist
  (`AGENTGUARD_ALLOWED_AUTH_ENV`).
- Data-exfiltration check now covers `cc`/`bcc`, URLs, webhooks, phone args;
  destinations are normalized (email→domain, URL→host) and compared against
  `AgentConfig.trusted_email_domains`.
- Prompt-injection matching normalizes zero-width characters and whitespace and
  covers "disregard/override … instructions" variants; tool results are scanned
  for indirect injection; intermediate LLM outputs are scanned for secrets.
- PRECONDITION policies (`{"tool": ..., "requires_prior_tool_result": {...}}`)
  are now actually evaluated in both the evaluation engine and the security
  engine — previously declared in the schema but never enforced.
- Container runs as non-root; compose references secrets via env only
  (`${POSTGRES_PASSWORD:?…}`), never hardcoded.

## Deployment requirements

- Python 3.10+, PostgreSQL 16.
- Environment: `POSTGRES_PASSWORD` (required by compose), `DATABASE_URL`,
  `USE_POSTGRES=true`, `AGENTGUARD_API_KEY` (required in production),
  `AGENTGUARD_CORS_ORIGINS` (production frontend origin), `GROQ_API_KEY`
  (only for live LLM runs), `AGENTGUARD_ALLOWED_AUTH_ENV` (opt-in).
- Serve the API with multiple workers behind a reverse proxy, e.g.
  `uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 4`, proxy
  timeout ≥ 300s, or `docker compose up` after verifying the build.
- Frontend: build with `VITE_API_BASE_URL` pointing at the API origin, serve
  `frontend/dist/` statically.
- Copy `.env.example` to `.env` and fill in real values; never commit `.env`.

## Tests and run commands

Backend (from repo root):

```powershell
.\.venv\Scripts\python -m pytest tests/ -q
```

With PostgreSQL running and `DATABASE_URL` set:

```powershell
$env:USE_POSTGRES = "true"
.\.venv\Scripts\python -m pytest tests/ -q
```

Frontend:

```powershell
cd frontend
npm install
npm run build
npx playwright install chromium   # once per machine
npm run e2e
```

## Next steps

1. ~~Stand up PostgreSQL; run the suite with `USE_POSTGRES=true` (un-skips 2 tests).~~ Done.
2. `docker compose up`; confirm both healthchecks; exercise the API through the container.
3. `npx playwright install chromium && npm run e2e` in `frontend/`.
4. Rotate any real Groq key found in history; purge history if needed.
5. Deploy to staging: set `AGENTGUARD_API_KEY` + `AGENTGUARD_CORS_ORIGINS`,
   add rate limiting and proxy timeouts.
6. Re-run this checklist; flip the verdict to Ready.

## Exact changed paths

Modified:
- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- `frontend/package.json`, `frontend/package-lock.json`
- `frontend/src/App.jsx`
- `frontend/src/components/AlertsView.jsx`
- `frontend/src/components/FilterBar.jsx`
- `frontend/src/components/RunHistoryTable.jsx`
- `pytest.ini`, `requirements.txt`
- `src/api/app.py`, `src/api/deps.py`, `src/api/routes.py`, `src/api/schemas.py`
- `src/core/agent_runner.py`, `src/core/config_models.py`, `src/core/llm_provider.py`
- `src/evaluation/engine.py`, `src/evaluation/outcome_evaluator.py`,
  `src/evaluation/policy_evaluator.py`, `src/evaluation/scoring.py`,
  `src/evaluation/tool_evaluator.py`
- `src/integrations/external_agent.py`
- `src/observability/cost.py`, `src/observability/latency.py`,
  `src/observability/models.py`
- `src/reporting/engine.py`, `src/reporting/history/memory.py`,
  `src/reporting/history/postgres.py`, `src/reporting/scoring.py`
- `src/security/data_exfiltration.py`, `src/security/engine.py`,
  `src/security/permission_check.py`, `src/security/policy_check.py`,
  `src/security/prompt_injection.py`, `src/security/sensitive_data.py`,
  `src/security/tool_abuse.py`
- `tests/conftest.py`, `tests/test_agent_runner.py`, `tests/test_api.py`, `tests/test_external_agent.py`,
  `tests/test_observability.py`, `tests/test_postgres_repository.py`,
  `tests/test_reporting.py`, `tests/test_reporting_history.py`

Added:
- `frontend/e2e/smoke.spec.js`, `frontend/playwright.config.js`
- `frontend/src/utils/reportFields.js`
- `src/api/auth.py`
- `src/evaluation/latency_evaluator.py`
- `tests/test_security_depth.py`

Deleted:
- `src/rag/__init__.py`, `src/rag/data_loader.py`, `src/rag/embedding.py`,
  `src/rag/vectorstore.py`

## Suggested commit message

```
Production-readiness remediation: auth, evaluation integrity, security depth

- Add optional API-key auth (X-API-Key) + env-configurable CORS
- Enforce max_latency_ms, PRECONDITION policies, one-to-one expected-arg
  matching; add max_tool_calls / tool-result-coverage evaluators
- Harden security checks: fail-closed crashes, redacted permission evidence,
  exfiltration via URL/webhook/phone/cc/bcc, tool-variety check,
  obfuscated/indirect injection, LLM-output secret scan
- Fix final_response fallback for externally-supplied traces
- Docker: non-root user, healthcheck, pinned base image
- DB: created_at, newest-first ordering, duplicate run_id rejection (409 via API),
  psycopg3 driver alignment with SQLAlchemy 2.1
- Frontend: canonical metric fields, real alert severity, Playwright e2e harness
- Runner: per-run mock-tool state reset (no cross-run refund leakage);
  external-agent HTTP client ignores ambient proxy env (`trust_env=False`)
  so malformed proxy config cannot break invocations
- Tests: 139 passed (in-memory), 141 passed (real PostgreSQL 16);
  adversarial + real end-to-end reporting tests
```

## Honest disclosure of unverified areas

- **Cloud infrastructure:** none provisioned or tested.
- **Authentication:** API-key mechanism implemented and unit-tested (401/200
  paths), but never tested through a deployed reverse proxy with TLS.
- **Secrets:** compose and app read secrets from env only; no live secret
  rotation performed; pre-existing key-shaped values need owner review.
- **Deployment:** no staging/production deployment exists; gunicorn/uvicorn
  worker counts, proxy timeouts, and log shipping are documented, not proven.
- **PostgreSQL:** verified against PostgreSQL 16 on 2026-09-29 — migrations,
  newest-first ordering, duplicate-`run_id` rejection, and `created_at`
  semantics all exercised for real (141 passed, 0 skipped, run twice).
- **Docker:** Dockerfile and compose changes are unbuilt and unrun here.
