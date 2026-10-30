# Stage 2 Import and Inspect Support Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import, validate, inspect, retry, and delete synthetic support conversations in CSV, JSON, and a documented Persian-labeled text format through the Persian UI.

**Architecture:** FastAPI parses uploads and SQLite is authoritative for sources and normalized records. The UI requests a server-side preview, maps CSV columns, confirms the import, and manages persisted sources. Original upload bytes live under a configurable uploads directory so failed imports can be retried.

**Tech Stack:** Python 3.14, FastAPI, `python-multipart`, SQLite, pytest, React, TypeScript, Vite, Vitest.

**Spec:** `SUPPORTRECALL_IMPLEMENTATION_GUIDE.md` sections 4.1, 4.3, 5 Stage 2, and 6; `docs/SUPPORTRECALL_DESIGN.md` application flow and knowledge view.

## Global Constraints

- All visible UI labels, validation messages, confirmations, status text, and docs are natural Persian; schema keys and file names may remain stable English identifiers.
- Accept `.csv`, `.json`, and `.txt` only; cap uploads at 5 MiB and parsed conversations at 2,000 per file.
- CSV requires explicitly mapped question and answer columns; conversation ID, date, product, and category are optional mapped columns.
- JSON accepts an array of question/answer records or an array of ordered-message conversations with `customer` and `support` roles.
- Text uses `---`-separated blocks with Persian metadata/role prefixes documented in `docs/IMPORT_FORMATS.md`.
- Never infer missing dates. Preserve message order, speaker roles, question/answer relationships, source filename, and available metadata.
- Preview performs parsing and validation without creating a source; import reparses the submitted file before persistence.
- Keep imports idempotent using a deterministic hash of normalized conversation content; do not create duplicate sources.
- Existing Stage 1 databases migrate additively; health startup and `/api/health` remain independent of sample data or model services.
- Source state is persisted as pending, processing, ready, or failed. Interrupted imports become retryable failures on startup.
- Store uploaded bytes under `SUPPORTRECALL_UPLOADS_DIR` or `<data_dir>/uploads`; use generated source IDs for storage paths, never user filenames.
- Sample files contain synthetic Persian support content and are downloadable from the knowledge UI.

## Review Focus

- Invalid, empty, oversized, or unsupported uploads return actionable Persian errors and create no ready source; pin parser/API validation tests.
- CSV with Persian headers works after explicit mapping, and missing question/answer mappings fail before import; pin parser and UI mapping tests.
- JSON preserves both direct question/answer records and ordered role messages; pin both parser tests.
- Plain-text blocks preserve Persian role order and optional metadata while leaving absent dates empty; pin text parser tests.
- Identical normalized imports are idempotent, interrupted imports are retryable after restart, and source deletion removes its records and upload; pin persistence/API tests.
- UI stays entirely Persian and supports keyboard operation for file selection, mapping, preview, confirm, details, retry, and delete; pin component tests and a manual walkthrough.

---

### Task 1: Define parsers, schemas, and Persian samples

**Files:**
- Create: `backend/app/imports/__init__.py`
- Create: `backend/app/imports/parsers.py`
- Test: `backend/tests/test_import_parsers.py`
- Create: `frontend/public/samples/نمونه-پشتیبانی.csv`
- Create: `frontend/public/samples/نمونه-پشتیبانی.json`
- Create: `frontend/public/samples/نمونه-پشتیبانی.txt`
- Create: `docs/IMPORT_FORMATS.md`

**Interfaces:**
- `parse_import(filename: str, content: bytes, mapping: CsvColumnMapping | None = None) -> ParsedImport` returns normalized ordered conversations and CSV headers.
- `Conversation` stores optional `conversation_id`, `date`, `product`, `category`, plus ordered `Message(role, content)` values.
- `CsvColumnMapping` requires `question` and `answer` header names; optional keys are `conversation_id`, `date`, `product`, `category`.
- `ImportParseError` exposes a stable code and a Persian-safe message for invalid input.

- [x] Write parser tests for CSV mapping/metadata, missing required mappings, both JSON shapes, Persian text blocks, empty/invalid input, and absent dates.
- [x] Run `python -m uv run --project . pytest tests/test_import_parsers.py -q` and confirm the tests fail because the parser module is absent.
- [x] Implement the normalized parser with UTF-8/UTF-8 BOM decoding, strict schema validation, ordered messages, and no guessed metadata.
- [x] Add three small synthetic Persian sample files and document their exact schemas and upload limits in Persian.
- [x] Rerun parser tests; require all focused tests to pass.
- [ ] Commit as `feat: add Persian support import formats`.

### Task 2: Persist and manage imported sources

**Files:**
- Modify: `backend/app/settings.py`
- Modify: `backend/app/storage.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/sources.py`
- Create: `backend/app/routes/sources.py`
- Modify: `backend/pyproject.toml`, `backend/uv.lock`, `backend/requirements.lock`
- Modify: `compose.yaml`, `.env.example`
- Test: `backend/tests/test_sources.py`

**Interfaces:**
- `Settings.uploads_dir -> Path` reads `SUPPORTRECALL_UPLOADS_DIR`, defaulting to `<data_dir>/uploads`.
- `POST /api/sources/preview` accepts one file and optional JSON CSV mapping; it returns headers, validation issues, count, and a bounded preview without database writes.
- `POST /api/sources/import` accepts the file/mapping, persists an idempotent source and normalized records, and returns either the imported or existing duplicate source.
- `GET /api/sources` lists sources; `GET /api/sources/{source_id}` returns details plus a bounded record preview.
- `POST /api/sources/{source_id}/retry` reprocesses the stored original upload; `DELETE /api/sources/{source_id}` removes its records and upload.

- [ ] Add failing tests for preview-without-persistence, source import/detail/list, duplicate detection, unsupported/oversized uploads, interrupted-import recovery, retry, and deletion cleanup.
- [ ] Run `python -m uv run --project . pytest tests/test_sources.py -q` and confirm expected failures before implementation.
- [ ] Add an additive SQLite migration for sources and records, foreign-key cleanup, state recovery, and SHA-256 canonical-content uniqueness.
- [ ] Add multipart upload handling, persistent upload storage, preview/import/source/retry/delete routes, and structured validation errors.
- [ ] Add and lock `python-multipart`; configure the existing Compose uploads volume and local environment path.
- [ ] Run source API tests and backend Ruff; require all passing.
- [ ] Commit as `feat: persist and manage support sources`.

### Task 3: Build the Persian knowledge import and inspection UI

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/strings.ts`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- API helpers expose preview, import, list/detail, retry, and delete operations using same-origin `/api` routes.
- Knowledge view provides format/sample guidance, file selection, CSV column mapping, validation preview, explicit import confirmation, source status/counts, detail preview, retry, and confirmed deletion.

- [ ] Add failing UI tests for Persian sample links, CSV mapping, preview/errors, import/list refresh, source details, retry, delete confirmation, and empty/loading states.
- [ ] Run `npm.cmd --prefix frontend run test -- --reporter=dot` and confirm the new UI assertions fail.
- [ ] Implement the knowledge workflow with keyboard-accessible labels and confirmation; keep all visible copy in `strings.ts` and every control functional.
- [ ] Rerun frontend tests, lint, and typecheck; require all passing.
- [ ] Commit as `feat: add Persian knowledge import workflow`.

### Task 4: Document, review, and hand off Stage 2

**Files:**
- Modify: `README.md`, `docs/CODE_MAP.md`, `docs/PROGRESS.md`, `docs/STAGE_CHECKLIST.md`
- Modify: this plan file

- [ ] Document the schemas, sample downloads, size limits, startup behavior, retry/delete workflow, and a manual Persian UI walkthrough.
- [ ] Run the full backend/frontend test suites, Ruff, frontend lint/typecheck/build, dependency lock check, and `docker compose config --quiet`.
- [ ] Run local API/UI smoke checks for preview, import, restart, duplicate import, retry, detail, and deletion.
- [ ] Review diffs and record any Docker/browser checks blocked by environment limitations.
- [ ] Update Stage 2 status only from observed results; leave Stage 3 unchecked.
- [ ] Commit as `feat: complete Stage 2 source import`.
