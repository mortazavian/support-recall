# SupportRecall stage checklist

Each stage is a separate review checkpoint. The next stage begins only after the user explicitly approves or otherwise authorizes it.

- [x] **Stage 0 — Inspect and agree on the design:** proposal reviewed and approved on 2026-10-30.
- [ ] **Stage 1 — Runnable application skeleton:** backend, frontend, Persian RTL shell, real health connection, persistent storage, configuration, Dockerfiles, Compose, and initial code/customization docs. Verify startup without an LLM.
- [ ] **Stage 2 — Import and inspect support data:** CSV with UI mapping, JSON, documented text format, validation, sample data, duplicate handling, persistence, retry, source details, and deletion.
- [ ] **Stage 3 — Embeddings and retrieval:** multilingual chunking/embedding, persistent source-linked retrieval, inspection utility, delete cleanup, bilingual evaluation, and embedding-change/reindex safeguards.
- [ ] **Stage 4 — Grounded answer generation:** Ollama and optional OpenAI-compatible adapters, bounded prompts, Persian defaults, citation validation, insufficient-evidence behavior, and graceful provider failures.
- [ ] **Stage 5 — Complete chat and settings:** persistent sessions, follow-up context, retry/copy/loading behavior, source cards, safe provider/retrieval settings, and readiness checks.
- [ ] **Stage 6 — Final UI and accessibility:** cohesive responsive layouts, keyboard access, complete Persian copy, RTL/mixed-language handling, and working controls and states.
- [ ] **Stage 7 — End-to-end verification and handoff:** relevant automated checks and real walkthrough, Docker/build/persistence verification, documentation, troubleshooting, and known limitations.

## Review rule

At the end of each authorized stage, update `docs/PROGRESS.md` with changes, decisions, actual checks, blockers, and the next stage. Give exact run commands and a short manual walkthrough. Stop for review before moving on.
