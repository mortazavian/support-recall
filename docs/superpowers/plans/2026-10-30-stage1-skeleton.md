# Stage 1 Runnable Application Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable SupportRecall version with a Persian RTL interface, real backend health status, persistent SQLite initialization, Windows instructions, and Docker support.

**Architecture:** FastAPI owns the API and initializes a small SQLite database at startup. React/TypeScript/Vite serves the Persian interface and calls a relative `/api` URL; Vite proxies it in development and Nginx proxies it to the Compose backend in production. Docker remains usable without Ollama, and named volumes preserve application data and future RAG storage.

**Tech Stack:** Python 3.14, FastAPI, Uvicorn, SQLite, pytest, React, TypeScript, Vite, Tailwind CSS, Node 24, Nginx, Docker Compose.

**Spec:** `docs/SUPPORTRECALL_DESIGN.md`; `SUPPORTRECALL_IMPLEMENTATION_GUIDE.md`, Stage 1 and Docker requirements.

## Global Constraints

- Persian is the only user-facing UI language at this stage; set `lang="fa"` and `dir="rtl"`.
- Startup and health must not depend on a running LLM or embedding model.
- Persist app data under one configurable directory; mount named volumes for app data, uploads, vectors, and model cache.
- Keep browser calls same-origin at `/api`; never put a Compose hostname in browser code.
- Publish the app on host loopback by default; keep secrets out of frontend assets.
- Keep settings centralized and backend routes thin. Use synthetic/empty-state content only.
- Preserve the approved design and leave ingestion, RAG, chat, and settings behavior for their authorized stages.

## Review Focus

- Missing data path and existing database: startup should create a missing path and reuse its SQLite file on restart. Pin with `test_health_initializes_persistent_database` and `test_health_reuses_existing_database`.
- Backend unavailable: UI should show a Persian disconnected state and its retry action should make a fresh real request. Verify manually with the backend stopped and restarted.
- Ollama unavailable: API and frontend containers should still become healthy. Verify with Compose without an Ollama service when the daemon is available.
- Browser proxy: frontend must request only relative `/api/health`. Verify the Vite proxy locally and Nginx proxy through the Compose URL.
- Persian/RTL: navigation, status, headings, empty states, and HTML direction must remain Persian/RTL. Inspect the rendered page and run a frontend production build.

## Planned Files

- `backend/pyproject.toml`, `backend/uv.lock`, `backend/requirements.lock`: pinned backend dependencies and exported container lock.
- `backend/app/settings.py`: centralized environment-derived data path.
- `backend/app/storage.py`: SQLite initialization and health query.
- `backend/app/main.py`: FastAPI lifespan and `/api/health` route.
- `backend/tests/test_health.py`: storage-backed health and restart tests.
- `frontend/package.json`, lockfile, `frontend/vite.config.ts`, and TypeScript config: frontend tooling and local proxy.
- `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/strings.ts`, `frontend/src/styles.css`, `frontend/src/App.test.tsx`: Persian UI shell and real connection indicator.
- `frontend/Dockerfile`, `frontend/nginx.conf`, `backend/Dockerfile`, and both `.dockerignore` files: multi-stage frontend, backend image, and constrained build contexts.
- `compose.yaml`, `.env.example`, `.gitignore`: loopback-only entry point, environment template, and local persistence.
- `README.md`, `docs/CODE_MAP.md`, `docs/CUSTOMIZATION.md`, `docs/PROGRESS.md`, `docs/STAGE_CHECKLIST.md`: Stage 1 setup and evolving guides.

---

### Task 1: Establish the approved design baseline

**Files:** repository metadata; `SUPPORTRECALL_IMPLEMENTATION_GUIDE.md`; Stage 0 docs.

**Interfaces:** establishes the local Git history before application code is added.

- [x] Confirm no Git repository existed, initialize local `main`, and inspect the configured commit identity.
- [x] Update the design status and progress log to record approval on 2026-10-30; mark Stage 0 approved in the checklist.
- [x] Commit the guide and approved Stage 0 documents with message `docs: approve SupportRecall design`.

### Task 2: Build persistent backend health

**Files:** `.gitignore`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/requirements.lock`, `backend/app/settings.py`, `backend/app/storage.py`, `backend/app/main.py`, `backend/tests/test_health.py`.

**Interfaces:**

- `Settings.from_environment() -> Settings` and `Settings.database_path -> Path`.
- `initialize_storage(database_path: Path) -> None` creates the parent and an `app_meta` table with a schema version.
- `create_app(settings: Settings | None = None) -> FastAPI` exposes `GET /api/health` returning `{"status":"ok","storage":"ready","service":"supportrecall"}` after storage initialization.

- [x] Write `test_health_initializes_persistent_database` (assert exact health JSON, database file, and `app_meta` schema version) and `test_health_reuses_existing_database` (write a sentinel, recreate the app, and verify the sentinel remains) using a temporary data directory and FastAPI `TestClient`.
- [x] Run the two tests; confirm they fail because the backend implementation is absent.
- [x] Implement settings, SQLite initialization, FastAPI lifespan, and the health route.
- [x] Run the focused tests and `ruff check app tests`; require both to pass.
- [x] Generate and commit the exact `uv.lock`, and export a fully pinned `requirements.lock` for Docker.
- [x] Commit the backend foundation with message `feat: add backend health and storage`.

### Task 3: Build the Persian RTL frontend shell

**Files:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/strings.ts`, `frontend/src/styles.css`, `frontend/src/App.test.tsx`, `frontend/src/test-setup.ts`.

**Interfaces:**

- `fetchHealth(signal?: AbortSignal): Promise<HealthStatus>` requests `/api/health` and validates the health response.
- `HealthStatus` has `status`, `storage`, and `service` string fields.
- `strings.ts` owns all visible Persian labels and status text.

- [x] Scaffold React/TypeScript/Vite and add Tailwind CSS; commit the generated npm lockfile.
- [x] Implement the responsive navigation shell, Persian empty states, `lang="fa"`, `dir="rtl"`, and a system Persian-capable font stack.
- [x] Add real loading/connected/disconnected states, periodic health refresh, and a retry button using the API function.
- [x] Configure the Vite `/api` development proxy to `http://127.0.0.1:8000`.
- [x] Run frontend tests, lint, typecheck, and production build; require passing connection-state tests, typecheck, and production build.
- [x] Commit the Persian frontend shell with message `feat: add Persian frontend shell`.

### Task 4: Add Docker and named persistence

**Files:** `backend/Dockerfile`, `backend/.dockerignore`, `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/nginx.conf`, `compose.yaml`, `.env.example`.

**Interfaces:** frontend listens on container port 8080 and proxies `/api/` to Compose service `backend:8000`; backend listens on 8000 and stores its database under `SUPPORTRECALL_DATA_DIR`.

- [x] Add backend and multi-stage frontend Dockerfiles with pinned application dependencies. `docker compose build` was attempted but image pulling is blocked by the configured Docker Desktop proxy; see `docs/PROGRESS.md`.
- [x] Configure Compose healthchecks, loopback-only host port, `host.docker.internal` mapping, backend runtime configuration, and named volumes for data, uploads, vectors, and model cache.
- [x] Confirm no endpoint or UI startup depends on Ollama; do not define an Ollama container as a default service.
- [x] Run `docker compose config --quiet`; configuration validation passed.
- [x] Attempt stack build/start and persistence verification. The builder could not fetch the Node base image through the refused proxy, so containers were not started; see `docs/PROGRESS.md`.
- [x] Commit the container configuration with message `build: add Docker Compose skeleton`.

### Task 5: Document and hand off Stage 1

**Files:** `README.md`, `docs/CODE_MAP.md`, `docs/CUSTOMIZATION.md`, `docs/PROGRESS.md`, `docs/STAGE_CHECKLIST.md`.

- [x] Document Windows local startup in two terminals, Compose startup/stop/logs/rebuild, storage paths, and the fact that no model is downloaded automatically.
- [x] Trace the current UI health request into FastAPI and SQLite; mark later RAG flow as planned until those stages exist.
- [x] Add initial examples for changing UI text/styles, API address, and data directory; mark prompt/retrieval/import customization as coming in later stages.
- [x] Update progress with actual results and Docker limitations; include exact commands and a short manual walkthrough.
- [x] Review `git diff`, ensure `.env`, generated databases, caches, and `node_modules` are ignored, then commit Stage 1 with message `feat: add runnable SupportRecall skeleton`.
