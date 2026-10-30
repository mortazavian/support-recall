# SupportRecall progress

## Current checkpoint

**Stage 2 - Import and inspect support data**

**Status:** Implemented and committed on `stage2-support-data`; ready for the user's review.
**Architecture:** FastAPI, React/TypeScript/Vite, SQLite, and a Persian right-to-left interface. The user authorized Stage 2 on 2026-10-30.

## Delivered

- CSV imports support explicit question and answer mapping plus optional conversation ID, date, product, and category columns. Persian and English headers are accepted.
- JSON imports support direct question/answer records and ordered `customer`/`support` messages.
- Plain-text imports use the documented Persian metadata and speaker labels separated into conversations by `---`.
- Uploads are limited to 5 MiB and 2,000 conversations. Preview and detail responses show at most 20 conversations.
- Preview validates and shows sample content without persisting a source. Import reparses, stores the original file under a generated name, and persists normalized messages in SQLite.
- Canonical normalized-content hashes prevent duplicate sources. Source list/detail, status, retry, and confirmed deletion are available through the Persian knowledge page.
- Startup additively migrates Stage 1 databases and marks interrupted imports as failed and retryable. Original files use `SUPPORTRECALL_UPLOADS_DIR` or default to `<data_dir>/uploads`.
- Three synthetic Persian samples are downloadable in the UI. The full schemas and validation rules are in `docs/IMPORT_FORMATS.md`.
- Retrieval, vectors, and chat answer generation are not implemented in this checkpoint. No model or external provider is required to start or import data.

## Stage 2 commits

- `852f91c` - `feat: add Persian support import formats`
- `00b0b16` - `feat: persist and manage support sources`
- `a3f8c7e` - `feat: add Persian knowledge import workflow`
- The Stage 2 documentation and handoff commit follows these implementation commits.

## Verification

- Backend: `pytest` - 23 passed. Ruff reported no issues.
- Frontend: Vitest - 8 passed. Oxlint, TypeScript typecheck, and production Vite build passed.
- Dependency checks: `uv lock --check` resolved 33 packages; the regenerated locked requirements export matched `backend/requirements.lock`.
- Compose: `docker compose config --quiet` passed.
- Local HTTP smoke: the Vite-served page returned HTTP 200 with Persian language and RTL direction; the Persian JSON sample was served and previewed through Vite's API proxy. Import, list, details, and duplicate import passed.
- Restart recovery smoke: a source left in processing became failed and retryable after backend restart; retry returned it to ready, detail returned its records, and deletion removed its rows and original upload.
- Backend and Vite processes used a temporary local data directory; it was removed after the smoke run.

## Environment limitations

Both Docker images built, and the Compose stack reached healthy backend and frontend states. The first container smoke exposed that `frontend/Dockerfile` omitted `public/`, so the Persian sample files were not in the production image. The build now copies `public/`; a fresh image served the samples and passed the API proxy smoke.

With a temporary Compose project and uniquely named volumes, source import survived forced backend-container recreation. Startup marked the in-progress source retryable; retry read the original upload, detail returned its records, and deletion completed. The temporary project, containers, and volumes were removed afterward.

The Windows Computer Use bridge could not connect to its native pipe, so a screenshot-based walkthrough was not available. HTTP checks covered the served page, sample downloads, and API proxy; automated UI tests cover Persian upload, mapping, preview, import, detail, retry, and delete interactions.

## Manual walkthrough

1. Start the services using the local or Compose commands in `README.md`.
2. Open the Persian UI and confirm the server and storage indicators are ready.
3. Open the Knowledge view, download a Persian CSV, JSON, or text sample, select it, and inspect the preview.
4. For CSV, map the question and answer columns and build the preview before importing.
5. Open a source's details and inspect its metadata and messages. Import the same content again and confirm that no duplicate source is created.
6. Restart with an import left in progress, confirm it becomes retryable, retry it, then delete the source and confirm the records and original upload are removed.
7. Try malformed JSON or a missing required CSV mapping and confirm the interface displays a useful Persian error without importing invalid content.

## Next stage

Stage 2 is ready for review. Keep Stage 3 unchecked until the user approves the Stage 2 checkpoint.
