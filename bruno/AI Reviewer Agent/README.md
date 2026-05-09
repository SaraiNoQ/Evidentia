# AI Reviewer Agent Bruno Collection

This collection targets the local FastAPI backend.

## 1. Start Backend

From the project root:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 2. Open In Bruno

In Bruno Desktop:

1. Choose `Open Collection`.
2. Select this directory:

```text
bruno/AI Reviewer Agent
```

3. Select the `Local` environment.
4. Set `sample_pdf_path` to an absolute PDF path on your machine.

## 3. Recommended Flow

1. Run `Health Check`.
2. Run `Create Local Full Audit Job`.
3. The post-response script stores `job_id`.
4. Run `Get Trace`.
5. Run `List Issues`.
6. The post-response script stores the first `issue_id`.
7. Run `Get Issue Evidence`.

`Get Report Placeholder` is expected to return `409 report_not_ready` until Phase 2 report generation is implemented.

## 4. CLI Note

No local `bru` / `bruno` CLI was detected when this collection was created, so CLI scripts are not added yet. Once `@usebruno/cli` is installed, this collection can be run from the command line with `bru run`.
