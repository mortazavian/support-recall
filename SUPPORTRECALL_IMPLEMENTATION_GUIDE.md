# SupportRecall — Collaborative Codex Implementation Guide

## Instructions to Codex

You are my senior AI engineer, full-stack developer, and practical mentor. Read this entire file before taking action. Build SupportRecall alongside me in small, reviewable stages. The intended outcome is a usable application with a complete UI, backend, and RAG pipeline.

**Do not implement the entire project in one turn. Complete only the current authorized stage, verify it, explain it, and pause for my review.**

I am an M.Sc. student in Artificial Intelligence with Python and ML knowledge. Explain implementation choices clearly so I can learn to maintain the application. Avoid long lectures and unnecessary complexity.

## 1. Product goal

SupportRecall answers new support questions using historical customer messages and support responses. I upload conversations; the application indexes them, retrieves relevant evidence, and generates grounded answers with inspectable citations.

Use retrieval-augmented generation rather than fine-tuning. New support data must be usable without retraining the language model.

The final deliverable must include a polished, working UI connected to the actual backend. A notebook, backend-only implementation, or static mockup is insufficient.

**Required product language: فارسی (Persian).** The application must use Persian throughout its user-facing interface and default chatbot responses. Docker support and readable, easily configurable code are required deliverables, not optional enhancements.

## 2. Collaboration rules

At the beginning of each stage:

1. Read the progress log and inspect relevant code and repository instructions.
2. Explain the stage's purpose, planned changes, and how we will verify them.
3. State assumptions. Ask only questions that materially affect this stage.
4. Implement the authorized stage, resolving routine reversible choices independently.

At the end of each stage:

1. Summarize what changed and why.
2. Explain the most important concepts and point me to relevant files.
3. Report actual verification results, including checks that could not run.
4. Give exact commands and a short manual walkthrough for me to try.
5. Update `docs/PROGRESS.md` with completed work, decisions, checks, blockers, and the next stage.
6. Stop and ask me to review. Continue to the next stage only when I explicitly say to continue, approve it, or otherwise authorize it.

Do not treat silence as approval. If I ask a question, answer it without assuming that I approved the next stage. If I request a change, apply it to the current stage and verify it before continuing.

Do not create artificial approval gates within an already authorized stage. Do not repeat completed work after restarting Codex: use the progress log and actual repository state.

Use synthetic sample data until I provide real support conversations. Never invent facts about my data, machine, or available models. Never claim that a mocked check proves a real model integration works.

## 3. Starting point and proposed stack

Inspect the repository and any `AGENTS.md` instructions first. Preserve existing work and do not overwrite unrelated changes.

If the repository is empty, propose these defaults in Stage 0:

| Component | Default |
| --- | --- |
| Backend | Python and FastAPI |
| Frontend | React, TypeScript, Vite |
| Styling | Tailwind CSS |
| Application metadata and chat history | SQLite |
| Vector storage | Persistent local Chroma |
| Embeddings | Configurable multilingual sentence-transformers model |
| Answer generation | Ollama by default; optional OpenAI-compatible API |

Verify current APIs and dependency compatibility from official documentation when available. Record dependency versions reproducibly. Keep provider interfaces small and replaceable.

Target local single-user use initially. GPU availability must not be required for application startup. Explain CPU limitations and model resource requirements. Do not download large models or run paid APIs without my explicit authorization.

Keep the project focused: no fine-tuning, autonomous agents, billing, public deployment, or enterprise multi-tenancy unless I later request them.

### 3.1 Simple code that I can understand and extend

Prioritize readability and ease of modification over clever abstractions. I want to read the finished code, adjust configuration, and add features myself.

- Use a small, conventional folder structure organized around clear responsibilities. Avoid both giant files and excessive fragmentation into tiny wrappers.
- Write straightforward Python and TypeScript with descriptive English identifiers, explicit data flow, useful type annotations, and short functions with clear purposes.
- Prefer ordinary functions and simple components. Introduce classes or interfaces only when they solve a concrete need, such as interchangeable model providers.
- Avoid generic plugin frameworks, dependency-injection containers, unnecessary inheritance, metaprogramming, microservices, and extra infrastructure unless an actual requirement justifies them.
- Keep routes thin and business logic easy to locate. Use simple request/response schemas and explicit error handling.
- Keep configuration in one documented backend settings module and a clearly organized `.env.example`. State precedence between environment values, persisted settings, and defaults. Do not scatter hardcoded model names, paths, or retrieval values across files.
- Put generation instructions and prompt templates in an obvious module. Keep Persian UI strings in a small centralized file without adding a complex localization framework.
- Add comments and docstrings where they explain intent, assumptions, or non-obvious behavior. Avoid comments that merely repeat the code.
- Keep dependencies minimal and explain the purpose of each major dependency.
- Use an appropriate formatter and linter with a small configuration. Maintain reliability and validation while keeping the implementation simple.
- At each stage, explain which files I should read first and how that stage's request/data flow works. Use Persian explanations if I ask.
- Add `docs/CODE_MAP.md` describing the folder structure and a concrete trace from UI question to retrieval to generated answer.
- Add `docs/CUSTOMIZATION.md` with exact files and examples for changing models, prompts, chunking, top-k, UI text/styles, import fields, and adding a simple feature or endpoint. Update it as implementation evolves.

### 3.2 Docker-friendly execution

Provide readable Dockerfiles, `.dockerignore` files, and a root `compose.yaml`. Keep local non-Docker execution supported too.

- Start the application with `docker compose up --build` after documented configuration and model prerequisites. Do not claim that this command automatically supplies models that have not been downloaded.
- Use a multi-stage frontend build. Prefer a straightforward same-origin reverse proxy for browser API requests, with the backend addressed by its Compose service name internally. Browser code must not depend on internal Docker hostnames.
- Use named volumes or clearly documented bind mounts for SQLite, uploaded sources, vector storage, and embedding model caches. Data must survive ordinary container recreation.
- Supply sensible health checks and clear readiness behavior. An unavailable LLM must not prevent the UI and basic backend health from starting.
- Support connecting to an existing host Ollama service, with platform-specific instructions for Docker Desktop on Windows and Linux host access. `localhost` inside a backend container is not the host machine.
- If useful, provide an optional Compose profile for containerized Ollama. Do not make a GPU or containerized Ollama mandatory. Document model downloads separately and get authorization before running large downloads.
- Pass secrets through runtime configuration; never bake them into images or expose them through frontend build variables.
- Containers may listen on `0.0.0.0` internally; publish application ports on host loopback by default. Expose only necessary ports and run without root where practical.
- Document start, stop, logs, rebuild, and backup/restore of persistent data. Clearly distinguish ordinary shutdown from destructive volume deletion; never delete persistent volumes automatically.
- Validate the Compose configuration, build images, and exercise startup and persistence where Docker is available. If Docker cannot run in the current environment, report that limitation and supply exact checks for me to run.

## 4. Functional requirements

### 4.1 Ingestion

Support these formats incrementally:

- CSV: required question and answer columns, optional metadata, and UI column mapping.
- JSON: question-answer records and conversations containing ordered messages with speaker roles.
- Plain text: one clearly documented conversation format.

Provide synthetic sample files and document every accepted schema.

Preserve customer-question/support-answer relationships, message order, speaker roles, and available metadata: filename, conversation ID, date, product, and category. Treat metadata dates as optional; do not infer missing dates.

Validate uploads and return actionable errors. Keep useful conversational context together in retrieval chunks. Split long conversations into bounded, overlapping chunks with stable source references. Detect duplicate imports using content hashes or stable IDs.

Persist pending, processing, ready, and failed states. Make interrupted processing recoverable and retries idempotent. Deleting a source must remove its records and vector entries. Account for partial failures across SQLite and the vector store rather than assuming cross-store atomic transactions.

### 4.2 Retrieval and generation

For each question:

1. Use relevant chat context to interpret follow-up questions.
2. Retrieve relevant historical support chunks.
3. Build a bounded prompt containing explicit source identifiers.
4. Generate a grounded response.
5. Return the answer, citations, and inspectable source excerpts.

Support English and Persian questions, source text, and answers. Choose a multilingual embedding model and verify basic retrieval behavior in both languages.

Persian is the default response language even when retrieved material is English. Answer in another language when the user explicitly requests it. Preserve original source excerpts and technical identifiers; do not translate or alter stored evidence. English data support does not require an English UI.

Make retrieval settings configurable, including top-k and a relevance cutoff calibrated on a small evaluation set. Explain the score's meaning for the chosen metric. Similarity scores are not probabilities of answer correctness.

When evidence is insufficient, state that limitation and ask for clarification or suggest human support. Do not fabricate policies, product behavior, troubleshooting steps, or citations. If sources conflict or appear outdated, explain the uncertainty and show relevant evidence.

Treat uploaded text as untrusted data. Embedded instructions must not override application instructions. Validate citation identifiers against the retrieved context. Explain that valid identifiers alone do not prove that every generated claim is supported.

Keep chat history separate from the knowledge base. Persist chat sessions without automatically ingesting new chat messages as support knowledge.

Handle unavailable models, provider errors, timeouts, and interrupted responses gracefully. Stream answers when supported; otherwise show a clear loading state.

Detect embedding configuration changes that require reindexing. Never silently mix incompatible vector representations.

### 4.3 Final UI

Build the UI progressively, then complete and polish it before delivery.

Set the document language to `fa` and default direction to `rtl`. All navigation, buttons, field labels, placeholders, help text, confirmations, loading states, validation messages, status labels, and user-facing errors must be written in natural Persian from the first UI stage. Map internal error codes to useful Persian messages rather than displaying raw provider errors. Keep model names, filenames, URLs, and code identifiers in their original form. Isolate code blocks, paths, URLs, and mixed-language snippets with appropriate LTR or automatic direction so they remain readable. Use a legible Persian-capable font that does not depend on a third-party CDN at runtime. Keep Persian labels centralized and verify that no unintended English placeholder text remains.

**Chat view:** persistent conversation sidebar; create, open, and delete conversations; readable messages; safe Markdown; copy answer; loading, retry, error, and empty states; expandable source cards with real excerpts and metadata; clear guidance when the knowledge base is empty.

**Knowledge view:** drag-and-drop uploads; supported-format guidance and sample downloads; CSV column mapping; preview before import; source list with statuses and record counts; details and imported-record preview; actionable import errors; retry; confirmed deletion.

**Settings/status view:** provider and model selection; retrieval settings; connection checks; backend, embedding, and generation availability; practical setup guidance for missing models or services. Restrict endpoints to trusted backend configuration rather than arbitrary URLs supplied in chat.

Use consistent typography and spacing, accessible contrast and labels, keyboard navigation, responsive layouts, and correct Persian/RTL handling including mixed Persian and English text. Every visible control must work. Clearly label sample content and any deferred functionality.

### 4.4 Security and reliability

- Keep credentials on the backend, outside frontend bundles, logs, and version control.
- Supply `.env.example` with placeholders and appropriate ignore rules.
- Validate file types, content, filenames, upload sizes, and parsed record limits; prevent path traversal.
- Sanitize rendered Markdown and configure CORS intentionally.
- Avoid logging full private support messages by default.
- Make external-provider use explicit because support text may leave the machine.
- Bind locally by default; document that public hosting needs authentication and deployment hardening.
- Persist data across restarts and document storage locations and reset behavior.
- Explain that historical support responses can be outdated or incorrect.

## 5. Staged implementation roadmap

Each stage is a separate review checkpoint. Split a stage into smaller checkpoints if it becomes too large, and explain that decision.

### Stage 0 — Inspect and agree on the design

Inspect the repository, relevant instructions, and available environment. Explain the proposed architecture, stack choices, data flow, and expected resource requirements. Record a concise design and stage checklist in `docs/`. Create `docs/PROGRESS.md`.

Include the Persian-first UI, simple code organization, configuration strategy, and Docker service/storage layout in the design. Identify how containers will reach Ollama and whether Docker is available for verification.

Ask only high-impact questions that remain unanswered. Do not scaffold or write product code yet. Show me the proposed design and wait for approval.

**Done when:** I can understand what will be built, the important choices are explicit, and I can approve or revise the design.

### Stage 1 — Runnable application skeleton

Create the backend, frontend, configuration, dependency setup, and basic application navigation. Add a health endpoint and a frontend connection indicator using the real backend. Provide Windows-friendly startup instructions. Initialize persistent application storage.

Use Persian UI text and RTL layout immediately. Add initial Dockerfiles and `compose.yaml`, verify the skeleton through Compose if possible, and begin `docs/CODE_MAP.md` and `docs/CUSTOMIZATION.md`.

**Done when:** I can start both services, open the UI, and see a verified backend connection without requiring a running LLM.

### Stage 2 — Import and inspect support data

Implement ingestion, validation, persistence, duplicate handling, and sample data. Add the knowledge UI with preview, CSV mapping, source details, status, retry, and deletion. Complete supported JSON and text schemas in this stage, using smaller checkpoints if needed.

**Done when:** I can import, inspect, restart, retry, and delete synthetic support sources through the UI, with useful validation errors.

### Stage 3 — Embeddings and retrieval

Implement multilingual embeddings, chunking, vector persistence, index lifecycle, and source-linked retrieval. Add a small developer-facing inspection route or utility to examine retrieved excerpts before generation is introduced. Implement reindex safeguards and vector cleanup.

**Done when:** relevant English and Persian examples are retrieved, deletion removes retrieval entries, restarts preserve the index, and incompatible embedding settings trigger clear guidance.

### Stage 4 — Grounded answer generation

Implement the Ollama adapter and optional OpenAI-compatible adapter, bounded context assembly, grounding instructions, citation validation, insufficient-evidence behavior, and provider error handling. Connect a basic chat UI so the full pipeline is usable.

**Done when:** a real configured model answers using imported support evidence with inspectable sources. If no real model is available, report that blocker and distinguish mock-tested behavior from unverified integration.

### Stage 5 — Complete chat behavior and settings

Implement persistent chat sessions, follow-up context handling, retries, copying, streaming where supported, complete source cards, and provider/retrieval configuration with connection checks. Ensure chat history stays separate from indexed support knowledge.

**Done when:** I can hold a multi-turn conversation, inspect sources, manage sessions, change supported settings safely, and recover from provider failures through the UI.

### Stage 6 — Final UI and accessibility

Polish the complete application: consistent visual design, desktop/mobile layouts, keyboard navigation, Persian and mixed-language rendering, and all loading/error/empty states. Remove dead controls and unintended placeholders.

Audit every user-facing screen and message for natural Persian text and correct RTL behavior, including upload errors, provider failures, settings, and confirmation dialogs. Verify that code snippets and English identifiers remain readable.

**Done when:** chat, knowledge management, and settings are cohesive and fully connected to actual functionality.

### Stage 7 — End-to-end verification and handoff

Run appropriate automated checks and a real end-to-end walkthrough where the environment permits it. Complete documentation, convenient startup scripts, troubleshooting, and known limitations. Resolve failures before declaring completion.

Verify Docker configuration, builds, service communication, host/container Ollama connectivity as configured, and data persistence after container recreation. Review code for unnecessary complexity and finish the customization examples before handoff.

**Done when:** I can follow the README to run the application and use my own support conversations, and all verification claims have evidence.

## 6. Verification expectations

Add meaningful tests alongside the relevant stages. Use deterministic mock providers for automated tests and separately identify real-model integration checks.

Cover parsing, validation, message ordering, question-answer relationships, duplicate ingestion, recoverable failures, persistence, source/vector deletion, multilingual retrieval on a small labeled dataset, empty knowledge bases, insufficient evidence, citation identifiers, provider failures, and embedding changes. Include a prompt-injection example to inspect handling without claiming complete protection.

At appropriate checkpoints run backend tests, frontend type checking, and a production frontend build. Do not repeat broad checks without a reason; rerun what the changes affect.

If browser automation is available, exercise upload → ingestion → relevant question → source inspection → unsupported question → source deletion → retrieval exclusion. Inspect desktop and mobile layouts. Otherwise provide a precise manual checklist and report the browser checks as unrun.

Never claim a command passed unless it actually ran and passed. Record blocked checks and their causes.

Include Persian UI/RTL checks, mixed-language content checks, and the Docker checks described above. Verify configuration overrides and document a simple customization walkthrough so I can make a small change without restructuring the project.

## 7. Final repository deliverables

- Complete backend and frontend source code.
- Persistent application data and RAG storage.
- Synthetic sample files for all supported import formats.
- Reproducible dependency manifests and available lockfiles.
- `.env.example` and appropriate ignore rules.
- Architecture/design notes and `docs/PROGRESS.md`.
- README covering Windows setup, model setup and resource requirements, startup, import schemas, configuration, data storage, verification, troubleshooting, and limitations.
- Convenient development startup command or script.
- Persian application UI and Persian default chatbot responses, with correct RTL and mixed-language rendering.
- Dockerfiles, `.dockerignore` files, and `compose.yaml` with persistent storage and documented model connectivity.
- `docs/CODE_MAP.md` and `docs/CUSTOMIZATION.md` with concrete examples for modifying the code.
- README sections for Docker startup, shutdown, logs, model prerequisites, backups, and persistence, alongside non-Docker setup.

Do not commit or push changes, publish the application, or send real support data to external providers unless I authorize those actions.

## 8. Start now

Read this document and repository instructions, inspect the existing workspace, and perform **Stage 0 only**. Present the design and initial checklist for my review. Do not implement Stage 1 until I approve.
