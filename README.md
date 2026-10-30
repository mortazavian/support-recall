# SupportRecall

SupportRecall is a local, Persian-first assistant for finding answers in past support conversations. Stage 2 provides the Persian right-to-left application shell, persistent SQLite storage, and import and inspection of synthetic support conversations in CSV, JSON, and plain text. Retrieval and chat answers are planned for later stages.

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

Compose creates persistent named volumes for SQLite data, imported uploads, future vectors, and the embedding-model cache. `docker compose down` removes containers and the network but preserves these volumes. `docker compose down --volumes` deletes all of them, including the database and imported data; use it only when you intend to erase the application data.

### Back up and restore data

Stop the backend briefly so the SQLite file is consistent, then copy the database and original uploads out of their named volumes:

```powershell
docker compose stop backend
docker compose cp backend:/app/data/supportrecall.sqlite3 .\supportrecall.sqlite3.backup
docker compose cp backend:/app/uploads .\uploads-backup
docker compose start backend
```

Restore both while the backend is stopped. Keep the uploads directory contents intact because SQLite source rows point to generated filenames in that directory:

```powershell
docker compose stop backend
docker compose cp .\supportrecall.sqlite3.backup backend:/app/data/supportrecall.sqlite3
docker compose cp .\uploads-backup/. backend:/app/uploads
docker compose run --rm --no-deps --user 0:0 backend chown -R 10001:10001 /app/data /app/uploads
docker compose start backend
```

The application does not require a model to import or inspect support sources. Vector storage is reserved for a later stage.

### Ollama

Ollama is not a Compose service and is not needed to start the UI, health endpoint, or source import. `.env.example` gives the future backend integration the host URL `http://host.docker.internal:11434`; Compose also maps `host.docker.internal` to the host gateway for Linux. No model is downloaded automatically, and Stage 2 does not call Ollama.

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

Original uploads are kept in an `uploads` subdirectory under that data directory. Set `SUPPORTRECALL_UPLOADS_DIR` to choose a separate location:

```powershell
$env:SUPPORTRECALL_UPLOADS_DIR = 'D:\SupportRecallUploads'
```

On startup, the backend additively migrates a Stage 1 database and marks interrupted imports as failed and retryable. Each source stores a generated upload filename, so the original client filename is never used as a filesystem path.

The database is initialized when the backend starts and reused on later starts. Neither local startup path needs a model, a GPU, or an external API key.

## Manual walkthrough

1. Start the backend and frontend using the local instructions above, or start the Compose stack.
2. Open the UI and confirm the Persian navigation, right-to-left layout, and connected server and storage states.
3. Open **دانش‌ها** (Knowledge). Download one of the Persian CSV, JSON, or text samples, select it, and inspect the preview before importing.
4. For CSV, map the required question and answer columns, then build the preview. Review its conversation count and sample records before choosing **ورود به کتابخانه** (Import to library).
5. Open source details to inspect the stored messages and metadata. Import the same content again to confirm that the existing source is reported instead of creating a duplicate.
6. To exercise recovery, stop the backend during an import or restart it with a source left in progress. It should appear as failed and offer **تلاش دوباره** (Retry). Retry it, inspect its details, then choose **حذف منبع** (Delete source) and confirm the deletion.
7. Try an unsupported file, malformed JSON, or an empty question/answer cell and confirm that the UI shows an actionable Persian validation message without importing it.

### Import formats and limits

The accepted formats are `.csv`, `.json`, and `.txt`. Each upload is limited to 5 MiB and 2,000 conversations. CSV headers can be Persian or English; choose the required question and answer columns in the UI. JSON accepts direct question/answer records and ordered `customer`/`support` messages. Plain text uses Persian labels and `---` separators. Missing dates are left empty.

See the [Persian import format guide](docs/IMPORT_FORMATS.md) for complete examples, field names, text labels, and validation behavior. Synthetic files are available from the knowledge page and in [frontend/public/samples](frontend/public/samples).

Preview validates the upload without saving a source. Import parses it again before writing the source and its normalized records. Identical normalized content is deduplicated; deleting a source removes its records and stored upload. After a restart, an import interrupted in progress is marked failed so its original upload can be retried.

## Project docs

- [Design and architecture](docs/SUPPORTRECALL_DESIGN.md)
- [Stage checklist](docs/STAGE_CHECKLIST.md)
- [Progress and verification](docs/PROGRESS.md)
- [Import formats and sample schemas](docs/IMPORT_FORMATS.md)
- [Code map](docs/CODE_MAP.md)
- [Customization guide](docs/CUSTOMIZATION.md)
