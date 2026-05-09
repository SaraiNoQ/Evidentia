# Architecture Spec

## 1. Module Boundaries

The system is divided into stable backend modules:

- `api`: HTTP endpoints, request validation, response formatting.
- `core`: config, schemas, LLM adapter, tool registry, shared errors.
- `parsing`: PDF ingestion, MinerU, PyMuPDF fallback, GROBID metadata/reference extraction.
- `indexing`: chunking, internal retrieval indexes, pgvector writes, artifact indexing.
- `retrieval`: query planning, academic search adapters, deduplication, reranking.
- `agents`: LangGraph nodes for orchestrator, summarizer, claim miner, auditors, evidence answerer, meta-reviewer, report generator.
- `verification`: gates, evidence checker, hallucination checker, numeric checks.
- `reporting`: PAT-style Markdown, PDF export, evidence appendix, JSON trace.
- `workers`: job execution, retries, queue consumers, background tasks.

Frontend modules:

- upload and job creation.
- job dashboard.
- report viewer.
- evidence browser.
- issue cards.
- revision workflow.

## 2. LangGraph Workflow

LangGraph is the default agent DAG layer.

Rules:

- Each graph node has a single responsibility.
- Each node input and output must be typed.
- Nodes write durable results through service interfaces, not ad hoc file writes.
- Failed nodes return structured failure state and warnings.
- Partial reports are allowed when gates fail, but the failure must be visible in trace.

Default high-level graph:

```text
parse -> index -> summarize -> claim_mine -> retrieve_internal
      -> local_auditors -> question_tree -> evidence_answer
      -> gates -> meta_review -> report
```

External retrieval extends the graph:

```text
claim_mine -> query_plan -> academic_search -> external_evidence
           -> historian / baseline_scout / related_work_auditor
```

## 3. Store Boundaries

- PaperGraph stores paper structure and relationships.
- EvidenceStore stores paper, external, computed, and user evidence.
- IssueStore stores review concerns and recommended fixes.
- AgentRun stores prompt, model, input hash, output, tool calls, cost, warnings.
- ReportTrace stores final report sections and source ids.

Agents must not bypass these stores when generating final report content.

## 4. Reporting Boundary

Only Report Generator writes the human-facing report. It may only consume:

- verified issue set.
- EvidenceStore.
- PaperSummary.
- QuestionTree answers.
- gate status.
- AgentRun records.

No other agent should write final report prose.

