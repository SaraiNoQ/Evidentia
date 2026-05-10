# Technical Stack

## 1. Stack Summary

AI Reviewer Agent uses a Python-first backend, LangGraph-based agent orchestration, PostgreSQL-backed persistence, and a Next.js product frontend. The stack is chosen to support long-running evidence-driven review jobs, structured agent state, traceable reports, and a gradual path from local MVP to product workflow.

| Layer | Default Choice | Role |
|---|---|---|
| Backend | Python + FastAPI | HTTP API, job lifecycle, service boundary |
| Agent orchestration | LangGraph | Multi-agent DAG, state transitions, retry and partial outputs |
| Storage | PostgreSQL + pgvector | Jobs, Paper IR, claims, evidence, issues, reports, MVP vector search |
| Cache / queue | Redis | Job queue, cache, locks, transient run state |
| Frontend | Next.js + React + TypeScript | Dashboard, report viewer, evidence browser, revision workflow |
| Python tooling | uv + ruff + pytest + mypy | Dependency management, linting, testing, type checking |
| Parsing | GROBID + Marker + pdffigures2 + PyMuPDF | Paper skeleton, content flow, figure/table assets, fallback page extraction |
| LLM integration | OpenAI-compatible adapter | DeepSeek V4 Pro, GPT-5.5, and future provider routing |
| Reporting | Markdown first, PDF later | PAT-style report, evidence appendix, JSON trace |

## 2. Backend

Default: `Python + FastAPI`.

Backend responsibilities:

- Upload, job creation, status, and report export APIs.
- JobConfig validation.
- Parser, retrieval, agent, verification, and reporting service wiring.
- Persistence boundaries for Paper IR, EvidenceStore, IssueStore, AgentRun, and ReportTrace.
- Authentication and workspace boundaries in later product phases.

Why:

- Python has the strongest ecosystem for PDF parsing, LLM orchestration, academic retrieval, numerical checks, and scientific tooling.
- FastAPI gives typed request/response models that align with Pydantic schemas.
- It supports both CLI/local MVP and service deployment without changing domain models.

Alternatives:

- Node.js is reserved for frontend and UI-side tooling.
- A pure CLI prototype can exist, but must use the same core schemas and services.

## 3. Agent Orchestration

Default: `LangGraph`.

LangGraph responsibilities:

- Represent the review workflow as explicit graph nodes.
- Pass typed state between Parser, Summarizer, Claim Miner, Auditors, Evidence Answerer, Meta-Reviewer, and Report Generator.
- Support retries, partial outputs, failed node handling, and checkpointing.
- Keep agent outputs schema-first and traceable.

Rules:

- LangGraph nodes must not write final report text directly unless the node is Report Generator.
- Specialist agents write structured outputs to EvidenceStore, IssueStore, AgentRun, or intermediate graph state.
- Meta-Reviewer may merge and calibrate issues, but cannot introduce facts not present in stores.

Future option:

- Temporal can be introduced later for production-grade durable workflow scheduling, but it is not the MVP default.

## 4. Storage

Default: `PostgreSQL + pgvector + Redis`.

PostgreSQL stores:

- users and workspaces in later phases.
- jobs and job events.
- paper documents, chunks, artifacts, references.
- claims, evidence anchors, issues.
- agent runs, gate statuses, report traces.

pgvector stores:

- chunk embeddings.
- artifact embeddings.
- external paper summary embeddings.
- evidence retrieval vectors.

Redis stores:

- job queue and worker coordination.
- transient caches.
- search result cache keys.
- distributed locks for one-job-one-run guarantees.

Future option:

- Qdrant or Milvus may replace pgvector only when vector scale or retrieval features exceed PostgreSQL/pgvector capacity.

## 5. Frontend

Default: `Next.js + React + TypeScript`, with `pnpm` as package manager.

Frontend responsibilities:

- Job dashboard.
- Upload workflow.
- PAT-style report viewer.
- Evidence browser.
- Issue cards.
- Gate status and trace inspection.
- Ask the Reviewer and Revision Loop in later phases.

UI component library:

- Not fixed for MVP.
- Choose during Phase 4 based on interaction complexity and design direction.

Rules:

- The frontend must never invent report content.
- The frontend renders report, issue, evidence, and trace data returned by backend APIs.
- Evidence links and gate warnings must remain visible in report browsing flows.

## 6. Parsing

Default parser profile: `research_default`.

Responsibilities:

- GROBID: paper metadata, abstract, section tree, references, and citation contexts.
- Marker: research-default content flow, canonical markdown candidate, equations, inline math, basic tables, and images.
- pdffigures2: figure/table captions, labels, image crops, and caption-object binding.
- PyMuPDF: text-based PDF preflight, fallback text extraction, embedded images, and debug artifacts.
- PaperIR renderer: canonical markdown generation from internal structure.

Later additions:

- Docling for structure validation and commercial-safe parsing profile.
- Camelot for table repair on low-confidence experiment tables.
- MinerU for hard-case formulas, complex tables and multi-column fallback.

Rules:

- Parser output must include confidence and warnings.
- Low-confidence pages must not silently pass as reliable evidence.
- Parsed chunks must preserve page and section anchors whenever possible.
- Pure-text LLM agents consume `canonical_paper.md` first; PaperIR remains the trace and evidence structure.
- Quick audit does not mean partial PDF parsing; `canonical_paper.md` should represent the full manuscript unless the user explicitly sets `max_pages`.
- Marker is acceptable for internal research; commercial self-hosting requires licensing or switching to the commercial-safe profile.

## 7. Retrieval

MVP:

- PostgreSQL full-text search or local BM25 implementation.
- pgvector semantic retrieval over PaperChunk and artifacts.
- Artifact lookup for tables, figures, equations, and references.

Retrieval-enhanced phase:

- arXiv.
- Semantic Scholar or OpenAlex.
- CrossRef.
- OpenReview.
- ACL Anthology.
- Papers with Code.
- DBLP.
- GitHub Search for lower-confidence implementation evidence.

Rules:

- External evidence must record source, query id, URL, retrieval time, and evidence level.
- Major novelty/baseline concerns should rely on Level A/B evidence.
- External search can be disabled or anonymized for confidential manuscripts.

## 8. LLM and Model Routing

Default: OpenAI-compatible adapter.

Supported provider pattern:

- DeepSeek V4 Pro.
- GPT-5.5.
- Gemini, Claude, or local models when exposed through compatible adapters.

MVP DeepSeek defaults, following the OpenAI-compatible DeepSeek API documented at <https://api-docs.deepseek.com/>:

- `AI_REVIEWER_LLM_BASE_URL=https://api.deepseek.com`
- `AI_REVIEWER_LLM_MODEL=deepseek-v4-pro`
- `AI_REVIEWER_LLM_API_KEY` is read only from environment or `.env`; never commit it.
- Missing keys fall back to deterministic local understanding so parser and API tests remain stable.

Rules:

- Provider-specific code must stay behind the adapter.
- Agent prompts must be versioned.
- Every model call must record model name, prompt version, input hash, token usage, warnings, and output schema validation result.
- Manuscript and retrieved text are untrusted data and must not override system policy.

## 9. Testing and Quality

Python:

- `uv` for dependency and lock management.
- `ruff` for linting and formatting.
- `pytest` for unit, integration, and regression tests.
- `mypy` for static type checking.

Frontend:

- `pnpm`.
- TypeScript strict mode.
- ESLint and Prettier.
- Component tests and Playwright checks when UI exists.

Minimum CI gate:

- lint.
- type check.
- unit tests.
- key integration tests.
- schema validation tests.

## 10. Deployment Path

MVP local development:

- FastAPI backend.
- LangGraph worker process.
- PostgreSQL with pgvector.
- Redis.
- local filesystem object storage.

Later production:

- Docker Compose for local parity.
- S3-compatible object storage.
- separate API and worker processes.
- managed PostgreSQL/Redis.
- observability for job duration, token usage, parser warnings, gate failures, and report generation failures.
