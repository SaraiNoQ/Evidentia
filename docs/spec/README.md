# Spec Directory

This directory contains the engineering and maintenance specifications for AI Reviewer Agent. These specs are binding for implementation unless a later design document explicitly supersedes them.

## Spec Map

- [architecture.md](architecture.md): module boundaries, LangGraph workflow, service responsibilities.
- [api.md](api.md): REST API conventions, lifecycle endpoints, response envelopes, errors.
- [data-model.md](data-model.md): Pydantic and database model conventions.
- [agent-contracts.md](agent-contracts.md): agent input/output contracts and LangGraph node rules.
- [prompt-guidelines.md](prompt-guidelines.md): prompt versioning, safety, evidence-grounding, PAT-style report prompts.
- [evidence-and-gates.md](evidence-and-gates.md): EvidenceStore, IssueStore, evidence classes, quality gates.
- [testing.md](testing.md): unit, integration, golden fixture, eval, and CI standards.
- [coding-standards.md](coding-standards.md): Python and TypeScript code style and maintenance rules.
- [privacy-security.md](privacy-security.md): manuscript privacy, prompt injection, retention, external search safety.
- [operations.md](operations.md): local development, environment variables, services, workers, observability.

## Maintenance Rules

- Any new backend module must update `architecture.md` if it changes module boundaries.
- Any new public endpoint must update `api.md`.
- Any new persisted object or enum must update `data-model.md`.
- Any new agent or changed agent output must update `agent-contracts.md` and `prompt-guidelines.md`.
- Any new quality gate or evidence type must update `evidence-and-gates.md`.
- Any bug fix caused by missing coverage should add a test rule or fixture to `testing.md`.
- Any new secret, external service, retention behavior, or remote model behavior must update `privacy-security.md` and `operations.md`.

## Project Defaults

- Backend: Python + FastAPI.
- Agent orchestration: LangGraph.
- Storage: PostgreSQL + pgvector + Redis.
- Frontend: Next.js + React + TypeScript.
- Python tooling: uv + ruff + pytest + mypy.
- Parser stack: MinerU + PyMuPDF + GROBID.
- LLM adapter: OpenAI-compatible provider routing.

