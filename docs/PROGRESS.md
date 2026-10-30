# SupportRecall progress

## Current checkpoint

**Stage 3 - Embeddings and retrieval**

**Status:** Implemented and committed on `stage3-embeddings-retrieval`; awaiting the user's review.
**Architecture:** FastAPI, React/TypeScript/Vite, SQLite, persistent Chroma, local Ollama embeddings with `embeddinggemma:latest`, and a Persian right-to-left interface. Stage 2 was approved as the prerequisite for Stage 3 on 2026-10-30.

## Stage 3 delivered

- Support conversations are formatted with stable `Customer:` and `Support:` labels, then split into chunks of at most 1,200 characters with 150 characters of overlap. Persian Unicode is preserved.
- `embeddinggemma:latest` creates multilingual vectors through the local Ollama `/api/embed` endpoint. Ollama is not called during startup or health checks.
- Chroma persists vectors under `SUPPORTRECALL_VECTOR_DIR` (default `<data_dir>/vectors`). SQLite remains authoritative for sources and normalized records.
- Imports and retries mark a source ready only after indexing succeeds. Provider failures keep the original upload and records and mark the source retryable. Source deletion removes vectors before records and uploads.
- `POST /api/retrieval/inspect` returns up to 10 ranked, source-linked excerpts in Persian or English without generating an answer.
- Model or dimension changes block indexing and inspection until an explicit `python -m app.retrieval.reindex --confirm` rebuild. Stage 2 sources missing vectors are detected at startup, marked retryable without contacting Ollama, and included in the confirmed rebuild.
- `backend/tests/fixtures/retrieval_evaluation.json` provides synthetic Persian, English, and cross-language queries. The local model achieved recall@3 of 6/6 during the Stage 3 run.

## Stage 3 commits

- `fde8f4a` - `feat: add Ollama embeddings and conversation chunking`
- `f414292` - `feat: persist source-linked retrieval vectors`
- `9d6f6ad` - `feat: add retrieval inspection and reindex safeguards`
- `9a378a6` - `docs: complete Stage 3 retrieval handoff`
- Review fixes for Chroma lifecycle and Stage 2 migration are included in the current checkpoint.

## Stage 3 verification

- Backend: `python -m uv run --project . pytest -q` - 76 passed, with one Chroma deprecation warning. Ruff reported no issues.
- Dependency checks: `uv lock --check` resolved 95 packages; the regenerated requirements export matched `backend/requirements.lock`.
- Retrieval evaluation: `embeddinggemma:latest` retrieved all six expected Persian, English, and cross-language conversations in the top three (recall@3: 6/6).
- Compose: `docker compose config --quiet` passed and both backend and frontend images built successfully.
- Manual API walkthrough: imported a two-conversation Persian/English JSON file; both queries returned the expected source-linked excerpts before and after a backend restart. With Ollama unavailable, `/api/health` returned 200 and inspection returned the Persian `embedding_unavailable` error. Deleting the source returned 204, and a later query returned no results.
- Review regressions confirm dimension changes still require reindex after the last vector is deleted, active clients recover after collection replacement, failed-source vectors do not crowd out ready results, and pre-Stage 3 sources become retryable and can be restored by confirmed reindex.
- Chroma adds a sizable runtime dependency set; the lock contains 95 packages, including ONNX Runtime and Kubernetes client dependencies.

## Stage 2 delivered

- CSV imports support explicit question and answer mapping plus optional conversation ID, date, product, and category columns. Persian and English headers are accepted.
- JSON imports support direct question/answer records and ordered `customer`/`support` messages.
- Strict CSV validation rejects malformed quoting; CSV fields accept the documented 5 MiB limit, and invalid JSON Unicode receives a Persian validation error.
- Plain-text imports use the documented Persian metadata and speaker labels separated into conversations by `---`.
- Uploads are limited to 5 MiB and 2,000 conversations. Preview and detail responses show at most 20 conversations.
- Preview validates and shows sample content without persisting a source. Import reparses, stores the original file under a generated name, and persists normalized messages in SQLite.
- Original bytes are written before a source becomes visible; deletion keeps its database record until the upload is removed. Startup cleans interrupted temporary and unreferenced upload files.
- The production Nginx proxy accepts a 5 MiB file plus multipart overhead and returns an actionable Persian JSON error for requests beyond its proxy limit.
- Canonical normalized-content hashes prevent duplicate sources. Source list/detail, status, retry, and confirmed deletion are available through the Persian knowledge page.
- Startup additively migrates Stage 1 databases and marks interrupted imports as failed and retryable. Original files use `SUPPORTRECALL_UPLOADS_DIR` or default to `<data_dir>/uploads`.
- Three synthetic Persian samples are downloadable in the UI. The full schemas and validation rules are in `docs/IMPORT_FORMATS.md`.
- Retrieval, vectors, and chat answer generation are not implemented in this checkpoint. No model or external provider is required to start or import data.

## Stage 2 commits

- `852f91c` - `feat: add Persian support import formats`
- `00b0b16` - `feat: persist and manage support sources`
- `a3f8c7e` - `feat: add Persian knowledge import workflow`
- `64aee50` - `feat: complete Stage 2 source import`
- `5354c3d` - `fix: harden Stage 2 import recovery`

## Stage 2 verification

- Backend: `pytest` - 30 passed. Ruff reported no issues.
- Frontend: Vitest - 9 passed. Oxlint, TypeScript typecheck, and production Vite build passed.
- Dependency checks: `uv lock --check` resolved 33 packages; the regenerated locked requirements export matched `backend/requirements.lock`.
- Compose: `docker compose config --quiet` passed.
- Local HTTP smoke: the Vite-served page returned HTTP 200 with Persian language and RTL direction; the Persian JSON sample was served and previewed through Vite's API proxy. Import, list, details, and duplicate import passed.
- Restart recovery smoke: a source left in processing became failed and retryable after backend restart; retry returned it to ready, detail returned its records, and deletion removed its rows and original upload.
- Backend and Vite processes used a temporary local data directory; it was removed after the smoke run.

## Environment notes

Both Docker images built, and the Compose stack reached healthy backend and frontend states. The first container smoke exposed that `frontend/Dockerfile` omitted `public/`, so the Persian sample files were not in the production image. The build now copies `public/`; a fresh image served the samples and passed the API proxy smoke.

Final-review fixes were covered by regression cases for malformed CSV, oversized CSV fields, invalid JSON Unicode, upload-write failure, interrupted temporary uploads, unlink failure, and stale UI previews.

With isolated Compose projects and uniquely named volumes, production proxy smoke checks accepted 1 MiB and 5 MiB previews, rejected a request above 6 MiB with Persian JSON, and served the Persian sample. A database and upload backup were copied out, removed from the temporary volumes, restored using the documented copy and ownership commands, and a restored source retried successfully as UID 10001. Temporary containers, volumes, and files were removed afterward.

The Windows Computer Use bridge could not connect to its native pipe, so a screenshot-based walkthrough was not available. HTTP checks and UI regression tests covered the production path and Persian workflow.

## Stage 2 manual walkthrough

1. Start the services using the local or Compose commands in `README.md`.
2. Open the Persian UI and confirm the server and storage indicators are ready.
3. Open the Knowledge view, download a Persian CSV, JSON, or text sample, select it, and inspect the preview.
4. For CSV, map the question and answer columns and build the preview before importing.
5. Open a source's details and inspect its metadata and messages. Import the same content again and confirm that no duplicate source is created.
6. Restart with an import left in progress, confirm it becomes retryable, retry it, then delete the source and confirm the records and original upload are removed.
7. Try malformed JSON or a missing required CSV mapping and confirm the interface displays a useful Persian error without importing invalid content.

## Stage 3 manual walkthrough

1. Start Ollama, pull `embeddinggemma:latest`, and start the app with the commands in `README.md`.
2. Import the bilingual JSON sample from the Knowledge view and confirm indexing finishes with the source marked ready.
3. Call `POST /api/retrieval/inspect` with a Persian password-reset query and an English refund query. Confirm each response includes a relevant excerpt, source filename, and conversation ID.
4. Restart the backend and repeat both queries to confirm the Chroma vectors persist.
5. Stop Ollama and confirm `/api/health` still returns 200 while inspection reports a Persian provider-unavailable error.
6. Restart Ollama, delete the imported source, and confirm its vectors no longer appear in inspection results.
7. Stop the backend before changing the embedding model. Run the explicit reindex command, confirm it refuses to run without `--confirm`, then restart the backend.

## Next stage

Stage 3 is ready for review. Stage 4 remains unchecked until the user authorizes that checkpoint.
