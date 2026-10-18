# AgentGuard

AI-agent reliability & security evaluation platform. Run an agent through a
test case, get a deterministic reliability + security report with scores,
metrics, and findings — via API or the React dashboard.

## Quickstart (5 minutes, Docker)

Prereqs: Docker + a terminal. No Python/Node needed on your machine.

```bash
git clone https://github.com/debuJan/AgentGuard && cd AgentGuard
cp .env.example .env
# open .env and set a long random POSTGRES_PASSWORD (required)
docker compose up --build
```

That's it. The API runs on `http://localhost:8000` (docs at `/docs`,
health at `/health`); PostgreSQL 16 starts alongside it and the container
entrypoint runs Alembic migrations automatically before serving traffic.

Dashboard (second terminal):

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run build
npx serve dist -l 4173
```

Open `http://localhost:4173`. To stop everything: `docker compose down`.

> Windows (PowerShell): same steps; use `copy .env.example .env` and
> `$env:VITE_API_BASE_URL="http://localhost:8000"; npm run build`.

### Without Docker (local dev)

Backend (FastAPI):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Frontend (React + Vite):

```bash
cd frontend
npm install
npm run dev        # dev server
```

The dashboard talks to the API base URL baked in at build time via
`VITE_API_BASE_URL` (defaults to `http://localhost:8000`).

### Tests

```bash
pytest -q            # backend suite (in-memory store)
cd frontend
npx playwright test  # end-to-end: API + dashboard in Chromium
```

The Playwright suite is fully self-contained: it starts the API (in-memory,
no Postgres) through `frontend/e2e/launch-api.mjs` and builds/serves the
frontend itself. Just run `npx playwright test`. (First run:
`npx playwright install chromium`.)

### Production deploy (HTTPS)

```bash
# .env must set: POSTGRES_PASSWORD, AGENTGUARD_API_KEY,
# AGENTGUARD_CORS_ORIGINS=https://your-frontend, DOMAIN=api.example.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```
```

The prod overlay adds Caddy as a reverse proxy with **automatic HTTPS**
(Let's Encrypt — point your domain's DNS at the host first), runs the API
with 4 workers, and stops publishing the API/Postgres ports directly — only
80/443 are exposed. Caddy also sets basic security headers.

### Database migrations

Schema changes are managed with Alembic (`migrations/`):

```powershell
alembic upgrade head     # apply pending migrations
alembic revision --autogenerate -m "describe change"  # after editing models
```

The Docker entrypoint runs `alembic upgrade head` automatically. Databases
created before Alembic existed: run `alembic stamp 0001` once instead.

## Test cases

AgentGuard is domain-agnostic: refund, delivery, banking, support, etc. are
just test cases in a persistent library — nothing is hardcoded in the UI.

- **Dashboard → Test Cases**: create a test case (title, category, input,
  expected tools in order, expected outcome), delete it, or run it against
  any agent endpoint via **Run Evaluation**.
- **Seed demo cases** (3 refund + 3 delivery, idempotent):
  ```powershell
  $env:AGENTGUARD_API_URL="http://localhost:8000"
  $env:AGENTGUARD_API_KEY="your-key"   # if the API requires one
  python scripts/seed_demo_test_cases.py
  ```
- **API**:
  - `POST /test-cases` — create (`title`, `category`, `input_text`,
    `expected_tools`, `expected_outcome`, optional `id`)
  - `GET /test-cases` — list all · `GET /test-cases/{id}` · `DELETE /test-cases/{id}`
  - `POST /runs` accepts either `test_case` (inline, as before) or
    `test_case_id` (a stored case) — supplying both or neither is a 400.

Stored in Postgres (`test_cases` table, migration `0002`) or the in-memory
store when `USE_POSTGRES=false`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `USE_POSTGRES` | `true` | `false` → in-memory report store (dev/E2E) |
| `DATABASE_URL` | — | Postgres connection string (when `USE_POSTGRES=true`) |
| `AGENTGUARD_API_KEY` | unset (dev mode) | Set to require `X-API-Key` on the API |
| `AGENTGUARD_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed origins |
| `GROQ_API_KEY` | — | Optional LLM provider key |
| `AGENTGUARD_RATE_LIMIT` | `200/minute` | Per-IP rate limit (`<n>/<second\|minute\|hour>`); `/health` and docs exempt |
| `AGENTGUARD_RATE_LIMIT_ENABLED` | `true` | Set `false` to disable rate limiting |
| `UVICORN_WORKERS` | `2` | Worker count for the Docker entrypoint |
| `DOMAIN` | — | Public domain for the prod overlay (Caddy auto-HTTPS) |

## Project structure

```
src/                 # backend: api, evaluation, security, reporting
tests/               # backend test suite
frontend/            # React dashboard (Vite)
frontend/e2e/        # Playwright E2E suite + API launcher
configs/             # evaluation/security configuration
docker-compose.yml   # API + PostgreSQL 16
PRODUCTION_READINESS_REPORT.md   # verification status and remaining work
```

## Production readiness

See `PRODUCTION_READINESS_REPORT.md` for the full verification log, the
remaining deployment checklist (Docker build, TLS/reverse proxy, secret
rotation), and known limitations.
