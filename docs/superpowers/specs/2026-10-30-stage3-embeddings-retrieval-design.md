# Stage 3 Design: Embeddings and Retrieval

## Intent

Let a support operator search imported conversations in Persian or English and inspect the matching source excerpts. Stage 3 prepares reliable evidence retrieval for the answer-generation work planned in Stage 4.

## Goals

- Split each normalized support conversation into bounded, readable chunks while preserving message order, speaker labels, and source references.
- Generate multilingual vectors through the local Ollama `/api/embed` endpoint, using `embeddinggemma:latest` by default.
- Store vectors and chunk metadata in the existing persistent Chroma volume. SQLite remains authoritative for imported sources and normalized conversations.
- Make source imports ready only after their vectors are stored. A provider failure leaves the source retryable and shows a useful Persian error.
- Remove a source's vectors when the source is deleted, and make retries safe after partial indexing or a restart.
- Add a small inspection endpoint that returns the best matching excerpts with source and conversation details, without generating an answer.
- Evaluate retrieval against synthetic Persian and English support examples using the locally available embedding model.
- Detect an embedding model or vector-size change and give clear reindex instructions instead of mixing incompatible vectors.

## Non-goals

- Chat, answer generation, prompt construction, or citations in generated answers; these belong to Stage 4.
- A search screen in the Persian UI; Stage 3 exposes a developer-facing inspection endpoint and documents how to use it.
- Cloud embedding services, rerankers, hybrid keyword search, a background job queue, or a configurable provider framework.
- Requiring Ollama for application startup or health checks. Source indexing and retrieval report a Persian provider error while Ollama is unavailable.

## Constraints

- Keep the existing FastAPI, SQLite, Chroma, and React/Vite stack.
- Keep source records and uploads intact when embedding fails; retry must be able to rebuild the vectors from the stored source.
- Preserve existing upload limits and source lifecycle behavior.
- Use Persian for user-facing errors and keep API field names and identifiers stable in English.
- Keep implementation small and explicit: one Ollama embedding client, one chunker, and focused indexing/retrieval functions.
- Do not download a model as part of normal application startup.

## Approaches considered

1. **Ollama embeddings with Chroma — selected.** This uses the existing Ollama URL configuration and the `embeddinggemma:latest` model already available on the development machine. It avoids adding a large Python ML runtime and keeps the implementation small. Indexing requires the configured local Ollama service.
2. **Sentence Transformers with Chroma.** This would run inside the backend and avoid a separate Ollama process, but it adds a heavier Python dependency and model-cache lifecycle. The user selected the Ollama approach for simpler code and dependencies.
3. **Remote embedding API.** This would send support content outside the local machine, so it does not fit the project's local-first handling of support data.

## Design

### Embedding and configuration

- Reuse `OLLAMA_BASE_URL`; add `SUPPORTRECALL_EMBEDDING_MODEL`, defaulting to `embeddinggemma:latest`.
- Send batches of text to Ollama's `POST /api/embed` endpoint and validate that the response contains one finite, non-empty vector per input, with a consistent dimension.
- Keep the Ollama client synchronous and small, using the Python standard library. Run the blocking import/indexing work off the async request loop.
- The backend, database health endpoint, and UI remain available when Ollama is down. Index and inspection operations return an actionable Persian error.

### Chunking and indexing

- Render messages in their original order with stable customer/support speaker labels. Keep product, category, date, and conversation identifiers as metadata instead of mixing them into the searchable text.
- Split each conversation independently at a 1,200-character limit with 150 characters of overlap, preferring whitespace boundaries. Never join separate conversations into one chunk.
- Use deterministic chunk IDs based on source ID, support-record position, and chunk number. Store `source_id`, record ID, conversation ID, position, and available metadata with each Chroma entry.
- Before reindexing a source, remove its old chunks. Add new vectors in bounded batches and mark the source ready only after all batches succeed. If a batch fails, mark the source failed and leave retry able to replace any partial vectors.
- On deletion, remove Chroma entries before deleting the SQLite source and its upload. A failed vector deletion keeps the source record so the operation can be retried.

### Compatibility and reindexing

- Store the configured embedding model name and observed vector dimension with the persistent collection profile.
- If an existing collection profile does not match the configured model or vector dimension, block new indexing and searches with a Persian `reindex_required` message. Never add vectors with a different representation to the same collection.
- Provide an explicit backend reindex command that rebuilds vectors from ready SQLite records. It must require an explicit confirmation flag before replacing the existing vector index; source files and records remain untouched.

### Inspection API and evaluation

- Add `POST /api/retrieval/inspect` with a Persian or English query and a bounded result count (1–10).
- Return ranked excerpts, vector distance, source ID and filename, conversation ID, record position, product, and category. This endpoint inspects retrieval only and does not call a generation model.
- Add synthetic bilingual fixtures and an evaluation command. Include same-language and cross-language queries; each expected supporting conversation should appear in the top three results on the configured local model.
- Unit tests should use a small deterministic embedder fixture so the backend suite does not require a running Ollama service. The real-model evaluation remains an explicit local command.

### Failure handling

- Map connection errors, missing models, malformed responses, and vector-store failures to stable error codes and readable Persian messages.
- Interrupted imports already become retryable after restart. On retry, deterministic IDs and source-level cleanup remove any partial vectors before indexing again.
- Source deletion and vector cleanup must be covered together so removed conversations cannot remain searchable.

## Review and rollout

Stage 2 PR #1 remains open. Stage 3 will be developed on a branch based on `stage2-support-data`, keeping its changes reviewable as a separate stacked checkpoint. Its pull request should target `stage2-support-data` until Stage 2 is merged.

## Calls made for this design

- The user selected Ollama `embeddinggemma:latest` to keep the Python implementation and dependencies small.
- Chunk size and overlap are set to 1,200 and 150 characters, respectively, as a readable initial bound for the locally available embedding model; bilingual evaluation may justify tuning them.
- The inspection surface is an API endpoint rather than another UI. The existing knowledge page already owns source management; this endpoint is for checking retrieval before Stage 4.
- Reindexing is an explicit CLI operation with a confirmation flag, not an automatic startup action, to prevent silent loss of the current vector index.

## Reference

- [Ollama embedding API](https://docs.ollama.com/api/embed)
