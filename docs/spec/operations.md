# Operations Spec

## 1. Local Services

MVP local stack:

- FastAPI backend.
- LangGraph worker process.
- PostgreSQL with pgvector.
- Redis.
- local filesystem object storage.

Frontend:

- Next.js development server.

## 2. Environment Variables

Required categories:

- database URL.
- Redis URL.
- object storage path.
- LLM provider keys.
- parser configuration.
- retrieval API keys.
- retention default.
- log level.

Secrets must not be committed.

## 3. Workers and Jobs

Rules:

- Long-running review jobs run outside request handlers.
- Workers acquire jobs through Redis-backed queue or equivalent queue abstraction.
- Job retries are limited and stage-aware.
- Failed stages record structured errors and warnings.
- Partial reports are preferred over silent failure when enough evidence exists.

## 4. Observability

Track:

- job duration by stage.
- parser confidence.
- agent run duration.
- token usage and cost estimate.
- retrieval query count.
- gate failures.
- report generation failures.

## 5. Cost Controls

Every job should support:

- retrieval budget.
- agent budget.
- token budget.
- max external papers to read.
- max retries per node.

Budget exhaustion should produce a partial report with explicit warnings.

## 6. Deployment Path

MVP:

- local services and documented env vars.

Next:

- Docker Compose for backend, worker, Postgres, Redis, and frontend.

Production later:

- managed PostgreSQL/Redis.
- S3-compatible object storage.
- separate API and worker scaling.
- centralized logs and metrics.

