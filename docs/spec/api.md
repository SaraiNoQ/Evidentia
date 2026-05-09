# API Spec

Current implemented API reference:

- [../API.md](../API.md)

Bruno collection for local API development:

- [../../bruno/AI Reviewer Agent/README.md](../../bruno/AI%20Reviewer%20Agent/README.md)

## 1. API Style

The backend exposes REST APIs through FastAPI. Request and response bodies use JSON except file upload endpoints.

Rules:

- Use plural resource names: `/api/jobs`, `/api/reports`, `/api/issues`.
- Use snake_case for JSON fields.
- Use stable ids with prefixes, e.g. `job_`, `paper_`, `claim_`, `ev_`, `issue_`, `run_`.
- All timestamps use ISO 8601 UTC.
- Long-running work is asynchronous and returns a `job_id`.

## 2. Response Envelope

Success:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_123"
  }
}
```

Error:

```json
{
  "error": {
    "code": "invalid_job_config",
    "message": "Human-readable error.",
    "details": {}
  },
  "meta": {
    "request_id": "req_123"
  }
}
```

## 3. Core Endpoints

Required MVP endpoints:

- `GET /health`: health check.
- `POST /api/jobs`: create job with PDF and JobConfig.
- `GET /api/jobs/{job_id}`: get job status.
- `GET /api/jobs/{job_id}/report?format=markdown`: download report.
- `GET /api/jobs/{job_id}/trace`: download JSON trace.
- `GET /api/jobs/{job_id}/issues`: list issues.
- `GET /api/jobs/{job_id}/issues/{issue_id}/evidence`: get evidence card.

Later endpoints:

- `POST /api/jobs/{job_id}/ask`: Ask the Reviewer.
- `POST /api/revisions`: create revision comparison job.
- `GET /api/revisions/{revision_id}`: get revision status/result.

## 4. Status Values

Job status values:

- `created`
- `parsing`
- `indexing`
- `summarizing`
- `claim_mining`
- `retrieval`
- `auditing`
- `question_answering`
- `verifying`
- `reporting`
- `completed`
- `partial_report`
- `failed`

## 5. Pagination

List endpoints use:

- `limit`
- `cursor`

Response metadata includes:

- `next_cursor`
- `has_more`

## 6. Error Codes

Common error codes:

- `invalid_job_config`
- `unsupported_file_type`
- `parse_failed`
- `job_not_found`
- `report_not_ready`
- `gate_failed`
- `external_retrieval_disabled`
- `schema_validation_failed`
- `internal_error`
