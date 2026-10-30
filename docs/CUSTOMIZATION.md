# Customization guide

Stage 1 keeps the everyday changes in a few small files. UI labels are Persian-first, and request paths stay relative so the same browser build works in local development and Compose.

## Change visible text

Edit `frontend/src/strings.ts`. For example, update `chat.emptyTitle` to change the empty chat heading. The brand title and description shown in the browser tab are in `frontend/index.html`. Keep visible product copy in Persian and give controls a clear accessible name.

After an edit, run the frontend checks from the repository root:

```powershell
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

## Change colors or spacing

Edit `frontend/src/styles.css`. Shared colors are near the top in the `:root` variables, including `--ink`, `--muted`, `--line`, `--green`, and `--sidebar`. Component styles follow the shell, status, cards, and responsive breakpoint sections. Keep keyboard focus visible and check the narrow-screen layout after changing dimensions.

## Change the local API address

The browser always calls a same-origin path such as `/api/health` from `frontend/src/api.ts`. For local development, change the target under `server.proxy` in `frontend/vite.config.ts` if the backend moves from `127.0.0.1:8000`.

For Compose, edit the `backend:8000` target in `frontend/nginx.conf` if the backend service name or port changes. Keep both proxies aligned; browser code should not contain a Docker service hostname.

## Change the local data directory

Set `SUPPORTRECALL_DATA_DIR` before starting the backend. In PowerShell:

```powershell
$env:SUPPORTRECALL_DATA_DIR = 'D:\SupportRecallData'
python -m uv run --directory backend --project . uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The database file is `supportrecall.sqlite3` inside that directory. In Compose, the environment path is `/app/data`; if you change it, update the `app-data` volume mount in `compose.yaml` to match. Do not remove the named volume when rebuilding containers.

## Model and retrieval options

Stage 1 does not implement model settings, prompts, imports, or retrieval. The Compose `OLLAMA_BASE_URL` is only a future connection setting; the current backend ignores it. Model, prompt, import-format, chunking, and retrieval customization will be documented when those features are implemented.
