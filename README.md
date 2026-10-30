# SupportRecall

SupportRecall is a local, Persian-first assistant for finding answers in past support conversations. This Stage 1 build provides the Persian right-to-left application shell, a live backend status, and persistent SQLite initialization. Import, retrieval, and chat are planned for later stages; their controls are visibly disabled for now.

## Run with Docker Compose

Requirements: Docker Desktop with its Linux engine and Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build --detach
```

Open <http://127.0.0.1:8080>. The backend health endpoint is proxied at <http://127.0.0.1:8080/api/health> and should return:

```json
{"status":"ok","storage":"ready","service":"supportrecall"}
```

Useful commands:

```powershell
docker compose ps
docker compose logs --follow backend frontend
docker compose up --build --detach
docker compose stop
docker compose down
```

The published address is loopback-only by default. Change `SUPPORTRECALL_PORT` in `.env` to use another port. Keep `SUPPORTRECALL_BIND=127.0.0.1` for local-only access.

Compose creates named volumes for the SQLite data, future uploaded sources, future vectors, and future embedding-model cache. `docker compose down` removes containers and the network but preserves these volumes. `docker compose down --volumes` deletes all of them, including the database and any later imported data; use it only when you intend to erase the application data.

### Back up and restore the database

Stop the backend briefly so the SQLite file is consistent, then copy it out of the named volume:

```powershell
docker compose stop backend
docker compose cp backend:/app/data/supportrecall.sqlite3 .\supportrecall.sqlite3.backup
docker compose start backend
```

To restore that copy, stop the backend, copy the backup over the database file, and start the backend again:

```powershell
docker compose stop backend
docker compose cp .\supportrecall.sqlite3.backup backend:/app/data/supportrecall.sqlite3
docker compose start backend
```

Stage 1 has no imported sources yet. When uploads and vectors are implemented, include those named volumes in the backup procedure too.

### Ollama

Ollama is not a Compose service and is not needed to start the UI or health endpoint. `.env.example` gives the future backend integration the host URL `http://host.docker.internal:11434`; Compose also maps `host.docker.internal` to the host gateway for Linux. No model is downloaded automatically, and Stage 1 does not call Ollama.

If an image pull fails because Docker Engine is configured to use an unreachable proxy, correct the proxy in Docker Desktop and restart its engine before retrying `docker compose up --build`.

## Run locally on Windows

Requirements: Python 3.14, Node.js 24, and npm. PowerShell commands use `npm.cmd` so they do not depend on PowerShell script execution policy.

First install the Python environment and frontend packages:

```powershell
python -m pip install --user uv
python -m uv sync --project backend
npm.cmd ci --prefix frontend
```

Open two PowerShell terminals in this project directory.

**Terminal 1 — backend:**

```powershell
python -m uv run --directory backend --project . uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend:**

```powershell
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

Open <http://127.0.0.1:5173>. Vite forwards browser requests from `/api` to the backend on port 8000. Stop each service with `Ctrl+C` in its terminal.

The database is created at `data\supportrecall.sqlite3`. To choose another local data directory, set this in Terminal 1 before starting the backend:

```powershell
$env:SUPPORTRECALL_DATA_DIR = 'D:\SupportRecallData'
```

The database is initialized when the backend starts and reused on later starts. Neither local startup path needs a model, a GPU, or an external API key.

## Manual walkthrough

1. Start the backend and frontend using the local instructions above, or start the Compose stack.
2. Open the UI and confirm that the Persian navigation and right-to-left layout appear.
3. Confirm the status changes to **سرور متصل است** (server connected).
4. Confirm the storage indicator reports ready only after the health response succeeds. Open **دانش‌ها** (knowledge) and **تنظیمات** (settings) to see the current empty and service states. Import and chat controls remain disabled until their later stages.
5. Stop the backend and check that the UI reports a connection problem; restart it and use **تلاش دوباره** (retry).

## Project docs

- [Design and architecture](docs/SUPPORTRECALL_DESIGN.md)
- [Stage checklist](docs/STAGE_CHECKLIST.md)
- [Progress and verification](docs/PROGRESS.md)
- [Code map](docs/CODE_MAP.md)
- [Customization guide](docs/CUSTOMIZATION.md)
