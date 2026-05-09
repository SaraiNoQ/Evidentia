# Data Model Spec

## 1. Modeling Rules

- Pydantic models define API and agent contracts.
- Database tables should mirror durable domain concepts, not transient prompt shapes.
- All persisted records include `id`, `created_at`, and `updated_at` unless immutable event records.
- All ids use explicit prefixes.
- Confidence values are floats from `0.0` to `1.0`.
- Status and severity values use enums, not free text.

## 2. Core Models

Required MVP models:

- `JobConfig`
- `PaperDocument`
- `PaperChunk`
- `Table`
- `Figure`
- `Equation`
- `Reference`
- `Claim`
- `EvidenceAnchor`
- `Issue`
- `AgentRun`
- `GateStatus`
- `ReportTrace`

## 3. Evidence Fields

`EvidenceAnchor` must include:

- `evidence_id`
- `source_type`
- `source_id`
- `page`
- `section`
- `line_span`
- `artifact_id`
- `quote`
- `url`
- `confidence`
- `evidence_level`

`source_type` values:

- `paper`
- `external_paper`
- `code`
- `computed_check`
- `user_note`

`evidence_level` values:

- `A`: peer-reviewed or official benchmark source.
- `B`: arXiv, OpenReview, technical report.
- `C`: GitHub README, blog, unofficial docs.
- `D`: snippet or secondary summary.

## 4. Issue Fields

`Issue` must include:

- `issue_id`
- `title`
- `severity`
- `dimension`
- `description`
- `affected_claim_ids`
- `evidence`
- `counter_evidence`
- `missing_evidence`
- `recommended_fix`
- `confidence`
- `verified_by`
- `gate_status`

`severity` values:

- `fatal`
- `major`
- `moderate`
- `minor`
- `possible`

## 5. AgentRun Fields

`AgentRun` must include:

- `agent_run_id`
- `job_id`
- `agent_name`
- `prompt_version`
- `model_name`
- `input_hash`
- `output_schema`
- `output_json_uri`
- `tool_calls`
- `evidence_ids`
- `issue_ids`
- `token_usage`
- `cost_estimate`
- `status`
- `warnings`

## 6. ReportTrace

ReportTrace links final report prose back to source records.

Required fields:

- `report_id`
- `job_id`
- `format`
- `section_key`
- `source_issue_ids`
- `source_evidence_ids`
- `source_agent_run_ids`
- `generated_text_hash`
- `gate_status_snapshot`

