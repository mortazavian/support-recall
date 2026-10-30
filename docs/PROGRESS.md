# SupportRecall progress

## Current checkpoint

**Stage 1 — Runnable application skeleton**

**Status:** Implemented and committed; ready for the user's review.
**Architecture:** FastAPI + React/TypeScript/Vite, with SQLite and Persian right-to-left UI. The user selected the guide's stack and authorized Stage 1 on 2026-10-30.

## Delivered

- `GET /api/health` initializes and checks a persistent SQLite database, returning `{"status":"ok","storage":"ready","service":"supportrecall"}`.
- The frontend has Persian navigation, chat/knowledge/settings empty states, periodic backend checks, a retry control, responsive styles, and the real relative `/api/health` request. Storage shows checking, ready, or unknown based on the health response. Chat and import controls are disabled until their later stages.
- Vite proxies `/api` to the local backend. Nginx proxies the same path to the Compose `backend` service.
- Dockerfiles use a multi-stage frontend build and non-root runtime users. Compose binds the UI to host loopback by default and declares named volumes for application data, uploads, vectors, and model cache.
- Startup, storage, backup, code-map, customization, and progress instructions are in the root README and `docs/`.
- No model was downloaded or contacted. Ollama is not required for startup and is not a Compose service.

## Commits

- `c3c22fa` — `docs: approve SupportRecall design`
- `b98c72b` — `feat: add backend health and storage`
- `54cbab2` — `feat: add Persian frontend shell`
- `dc333e4` — `build: add Docker Compose skeleton`
- The Stage 1 handoff commit adds the README, code map, customization guide, and final status.

## Verification

- Backend: `python -m uv run --directory backend --project . pytest -q` — 2 passed. `ruff check app tests` and the locked dependency export/check passed during Task 2.
- Frontend: `npm.cmd ci --prefix frontend` completed with 0 reported vulnerabilities. `npm.cmd --prefix frontend run test -- --reporter=dot` — 4 passed, including checking, ready, and offline storage states; `npm.cmd --prefix frontend run lint`, `typecheck`, and `build` passed.
- Independent Stage 1 review findings were fixed: storage readiness now follows the verified health response, and small-text contrast was raised. Audited text/background pairs met at least 4.5:1 contrast.
- `docker compose config --quiet` passed, and `docker info` reported Docker Engine 29.9.2.
- Local smoke run: FastAPI and Vite started in separate terminals. A request through Vite to `/api/health` returned the exact ready JSON; the served page returned HTTP 200 with `lang="fa"`, `dir="rtl"`, and the Persian title.
- Backend tests verify database initialization and reuse. The local smoke run created the default `data/supportrecall.sqlite3` file, which is ignored by Git.

## Docker limitation

`docker compose build` was attempted but could not finish. Docker BuildKit tried to fetch the Node image through Docker Desktop's configured HTTPS proxy at `127.0.0.1:10808`; the connection was refused. As a result, neither image was built, and Compose container startup, Nginx proxying, and named-volume persistence after container recreation were not verified. The Compose file itself validates. Correct the Docker Desktop proxy and retry the Compose commands in the README.

The computer-use browser bridge was unavailable, so this session verified the served page and API over HTTP but could not capture a screenshot for visual review. The README includes a short visual walkthrough.

## Next stage

Stage 1 is ready for review. After review, proceed to **Stage 2 — Import and inspect support data** only when the user explicitly authorizes it.
