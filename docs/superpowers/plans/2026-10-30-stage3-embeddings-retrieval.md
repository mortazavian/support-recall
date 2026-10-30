# Stage 3: Embeddings and Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Index imported Persian and English support conversations as persistent, source-linked vectors and let developers inspect the most relevant excerpts.

**Architecture:** A small standard-library Ollama client generates vectors with `embeddinggemma:latest`. Chroma stores vectors and chunk metadata under the configured persistent vector directory; SQLite remains the source of truth for source and record data. Import and retry finish only after indexing succeeds, while a local inspection API and explicit reindex command support retrieval checks and model changes.

**Tech Stack:** Python 3.14, FastAPI, SQLite, Chroma, Ollama `/api/embed`, pytest, Ruff, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-30-stage3-embeddings-retrieval-design.md`

## Global Constraints

- Keep the existing FastAPI, SQLite, Chroma, and React/Vite stack.
- Use `embeddinggemma:latest` as the default model through the configured local Ollama URL.
- Split each conversation at 1,200 characters with 150 characters of overlap, preferring whitespace boundaries.
- Bound inspection results to 1–10; return source-linked excerpts and vector distance without generating an answer.
- Keep source records and uploads if embedding fails; mark the source retryable.
- Remove vectors before deleting the SQLite source and its upload.
- Store model identity and vector dimension; reject mismatches until explicit reindexing.
- Keep backend health and startup independent of Ollama; do not download models on startup.
- Use Persian for user-facing errors; keep API fields and identifiers in English.
- Keep implementation small: one Ollama client, one chunker, and focused retrieval functions.

## Review Focus

1. Persian Unicode and long messages at chunk boundaries remain intact — Task 1 test `test_long_persian_text_keeps_all_characters_and_limits_chunks`.
2. Ollama returns missing, malformed, non-finite, or mixed-dimension vectors — Task 1 test `test_embed_rejects_invalid_vector_responses`.
3. Ollama is unavailable during an import, then returns before retry — Task 2 test `test_failed_index_can_be_retried_without_duplicate_vectors`.
4. A model or vector dimension changes while an old Chroma collection exists — Task 3 test `test_inspect_requires_reindex_after_embedding_profile_changes`.
5. A query is blank or asks for an invalid result count — Task 3 test `test_inspect_rejects_blank_query_and_out_of_range_limit`.

---

### Task 1: Add readable chunking and Ollama embeddings

**Files:**
- Create: `backend/app/retrieval/__init__.py`
- Create: `backend/app/retrieval/chunking.py`
- Create: `backend/app/retrieval/embeddings.py`
- Modify: `backend/app/settings.py`
- Test: `backend/tests/test_chunking.py`
- Test: `backend/tests/test_embeddings.py`

**Interfaces:**
- `chunk_conversation(messages: Sequence[Message], max_chars: int = 1200, overlap_chars: int = 150) -> list[str]` formats messages in order with `Customer:` and `Support:` labels, then chunks without joining conversations.
- `OllamaEmbedder(base_url: str, model: str, timeout_seconds: float = 30.0)` exposes `embed(texts: Sequence[str]) -> list[list[float]]` and raises `EmbeddingError(code: str, message: str)` for connection and response errors.
- `Settings` adds `ollama_base_url`, `embedding_model`, and optional `vector_path`, with defaults `http://localhost:11434`, `embeddinggemma:latest`, and `<data_dir>/vectors`; its `vector_dir` property resolves the path.

- [x] **Step 1: Write failing chunking tests** for message order and speaker labels, empty input, ordinary short text, 1,200-character bounds, 150-character overlap, and Persian text retained across whitespace boundaries.
- [x] **Step 2: Run the chunk tests and confirm they fail** because `app.retrieval.chunking` does not exist.

Run from `backend/`: `python -m uv run --project . pytest tests/test_chunking.py -q`
Expected: collection fails with the missing module/function.

- [x] **Step 3: Implement `chunk_conversation`** with explicit defaults, message labels, whitespace-aware character splitting, and no cross-conversation state.
- [x] **Step 4: Run chunk tests and confirm they pass.**
- [x] **Step 5: Write failing Ollama client tests** using a local HTTP stub for the request path and payload, successful batch response, count mismatch, malformed JSON, mixed vector dimensions, non-finite values, timeout, and connection failure.
- [x] **Step 6: Run the embedding tests and confirm they fail** because `OllamaEmbedder` is not implemented.

Run from `backend/`: `python -m uv run --project . pytest tests/test_embeddings.py -q`
Expected: collection fails with the missing module/class.

- [x] **Step 7: Implement `OllamaEmbedder.embed`** with `urllib.request`, a 32-text request batch, timeout, vector validation, and stable Persian-facing errors; read the endpoint and model from `Settings`.
- [x] **Step 8: Run both test files and Ruff.**

Run from `backend/`: `python -m uv run --project . pytest tests/test_chunking.py tests/test_embeddings.py -q` and `python -m uv run --project . ruff check app tests`.
Expected: all focused tests pass and Ruff reports no issues.

- [x] **Step 9: Commit** as `feat: add Ollama embeddings and conversation chunking`.

### Task 2: Persist vectors and connect source lifecycle

**Files:**
- Create: `backend/app/retrieval/index.py`
- Modify: `backend/app/settings.py`
- Modify: `backend/app/sources.py`
- Modify: `backend/app/main.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/requirements.lock`
- Test: `backend/tests/test_retrieval_index.py`
- Modify: `backend/tests/test_sources.py`

**Interfaces:**
- `VectorIndex(vector_dir: Path, embedding_model: str, embedder: OllamaEmbedder)` owns one persistent Chroma collection.
- `VectorIndex.index_source(database_path: Path, source_id: str) -> int` reads normalized SQLite records, chunks and upserts them with deterministic IDs, and returns the indexed chunk count.
- `VectorIndex.delete_source(source_id: str) -> None` deletes all entries for that source.
- `VectorIndex.search(query: str, limit: int = 5) -> list[dict[str, object]]` returns ordered chunk text, metadata, and cosine distance.
- `create_app(settings: Settings | None = None, *, vector_index: VectorIndex | None = None) -> FastAPI` allows deterministic index injection in tests while production constructs it from settings.
- Source import, retry, and delete functions receive the index instance; `ready` is set only after successful vector indexing.

- [x] **Step 1: Add failing persistent-index tests** for deterministic chunk IDs, source and record metadata (omitting unavailable optional values), successful search, persistence after reopening the client, deletion, and profile metadata containing model and dimension.
- [x] **Step 2: Add the source lifecycle regression tests** for import ready-after-index, index failure leaving a retryable source and intact records/upload, and delete preserving the source when vector deletion fails.
- [x] **Step 3: Run the focused tests and confirm they fail** because `app.retrieval.index.VectorIndex` and the source lifecycle integration are missing.

Run from `backend/`: `python -m uv run --project . pytest tests/test_retrieval_index.py tests/test_sources.py -q`
Expected: collection or assertions fail on the missing index implementation.

- [x] **Step 4: Add Chroma as a bounded runtime dependency** with `python -m uv add --project . "chromadb>=1.0,<2.0"`, then regenerate the lock and hash-pinned requirements export.
- [x] **Step 5: Implement `VectorIndex`** with a persistent client, cosine distance, deterministic chunk IDs, 32-text Ollama batches, per-source cleanup before upsert, and profile checks.
- [x] **Step 6: Integrate indexing with import, retry, restart recovery, and deletion** so partial vectors are removed before retry and vectors are deleted before source rows/uploads.
- [x] **Step 7: Inject `VectorIndex` through `create_app`** and update existing source tests to use a deterministic embedder/index; verify app startup and `/api/health` still work when Ollama is unavailable.
- [x] **Step 8: Run focused source/index tests, the full backend suite, and Ruff.**

Run from `backend/`: `python -m uv run --project . pytest tests/test_retrieval_index.py tests/test_sources.py -q`, then `python -m uv run --project . pytest -q`, then `python -m uv run --project . ruff check app tests`.
Expected: all tests pass and Ruff reports no issues.

- [x] **Step 9: Commit** as `feat: persist source-linked retrieval vectors`.

### Task 3: Add inspection API and guarded reindex command

**Files:**
- Create: `backend/app/routes/retrieval.py`
- Create: `backend/app/retrieval/reindex.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/retrieval/index.py`
- Test: `backend/tests/test_retrieval_api.py`
- Test: `backend/tests/test_reindex.py`

**Interfaces:**
- `POST /api/retrieval/inspect` accepts `{ "query": string, "limit": integer }`; default limit is 5, allowed range is 1–10.
- The response contains `results`, each with `source_id`, `filename`, `record_id`, `conversation_id`, `position`, `product`, `category`, `excerpt`, and `distance`.
- `VectorIndex.rebuild(database_path: Path, *, confirmed: bool) -> int` clears and reindexes vectors only; it refuses to replace the collection unless `confirmed` is true.
- `python -m app.retrieval.reindex --confirm` is the explicit rebuild command.

- [x] **Step 1: Write failing API tests** for Persian and English queries returning source-linked excerpts, blank query rejection, limit bounds, provider errors, and model/dimension mismatch returning `reindex_required` with a Persian message.
- [x] **Step 2: Write failing reindex tests** proving missing confirmation preserves vectors, confirmed reindex rebuilds all ready sources, and a failed rebuild leaves SQLite records/uploads intact.
- [x] **Step 3: Run API and reindex tests and confirm they fail** because routes and command are absent.

Run from `backend/`: `python -m uv run --project . pytest tests/test_retrieval_api.py tests/test_reindex.py -q`
Expected: collection fails with the missing route/command.

- [x] **Step 4: Implement the inspection route** with bounded Pydantic inputs, database lookup for source filenames, stable errors, and no generation calls.
- [x] **Step 5: Implement collection-profile checks and explicit reindexing** so changed model identity or dimensions blocks search/indexing until the confirmed command rebuilds the collection.
- [x] **Step 6: Run API, reindex, source, and index tests, the full backend suite, and Ruff.**

Run from `backend/`: `python -m uv run --project . pytest tests/test_retrieval_api.py tests/test_reindex.py tests/test_retrieval_index.py tests/test_sources.py -q`, then `python -m uv run --project . pytest -q`, then `python -m uv run --project . ruff check app tests`.
Expected: all tests pass and Ruff reports no issues.

- [x] **Step 7: Commit** as `feat: add retrieval inspection and reindex safeguards`.

### Task 4: Add bilingual evaluation and Stage 3 operating guidance

**Files:**
- Create: `backend/tests/fixtures/retrieval_evaluation.json`
- Create: `backend/scripts/evaluate_retrieval.py`
- Modify: `.env.example`
- Modify: `compose.yaml`
- Modify: `README.md`
- Modify: `docs/PROGRESS.md`
- Modify: `docs/STAGE_CHECKLIST.md`
- Test: `backend/tests/test_retrieval_evaluation.py`

**Interfaces:**
- `python -m uv run --project . python scripts/evaluate_retrieval.py` evaluates the fixture against the configured Ollama model and exits nonzero if an expected supporting conversation is not in the top three.
- The fixture covers Persian, English, and cross-language support queries with synthetic content and stable expected conversation IDs.
- Compose sets `SUPPORTRECALL_VECTOR_DIR=/app/vectors`; `.env.example` documents the model name and Ollama URL without requiring a model download at startup.

- [x] **Step 1: Write a failing fixture-validation test** for non-empty Persian and English query sets, distinct expected conversation IDs, and top-three evaluation configuration.
- [x] **Step 2: Run the fixture test and confirm it fails** because the fixture and evaluator are missing.
- [x] **Step 3: Add synthetic bilingual support conversations and queries** that require both same-language and cross-language retrieval.
- [x] **Step 4: Implement the evaluation script** to build a temporary Chroma index, call the configured Ollama model, report each ranked hit and recall@3, then remove only its temporary data.
- [x] **Step 5: Run the fixture test and Ruff, then run the real-model evaluation** against the locally available `embeddinggemma:latest`; if a target is missed, inspect the rankings and improve chunking or retrieval without weakening the expected matches.

Run from `backend/`: `python -m uv run --project . pytest tests/test_retrieval_evaluation.py -q`, `python -m uv run --project . ruff check app tests scripts`, and `python -m uv run --project . python scripts/evaluate_retrieval.py`.
Expected: fixture checks pass, Ruff reports no issues, and every expected conversation appears in the top three.

- [x] **Step 6: Update Compose and `.env.example`** with the persistent vector path and configurable local Ollama embedding model.
- [x] **Step 7: Update README, progress, and checklist** with Stage 3 scope, exact run/evaluation/reindex commands, provider failure behavior, and the manual Persian/English walkthrough. Mark Stage 2 approved and Stage 3 complete; leave Stage 4 unchecked.
- [x] **Step 8: Run the complete backend tests, Ruff, lock/export checks, Compose validation, Docker builds, and manual API walkthrough.**

Run from `backend/`: `python -m uv run --project . pytest -q`, `python -m uv run --project . ruff check app tests scripts`, and `python -m uv lock --check`; regenerate the export with `python -m uv export --project . --locked --no-dev --format requirements-txt --no-emit-project --output-file requirements.lock`, then confirm `git diff --exit-code -- requirements.lock`; from the repository root run `docker compose config --quiet` and `docker compose build`.
Expected: all commands exit successfully; the walkthrough retrieves Persian and English fixtures, reports Ollama unavailable without taking down health, persists vectors across backend restart, and no longer returns a deleted source.

- [x] **Step 9: Commit** as `docs: complete Stage 3 retrieval handoff`.
