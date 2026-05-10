# AI Reviewer Agent Roadmap

## 1. Roadmap Overview

This roadmap turns the PRD, system design, and agent map into an implementation sequence for AI Reviewer Agent. The delivery order is intentionally conservative:

1. Build a reliable local review loop first.
2. Add evidence stores, gates, PAT-style reporting, and traceability.
3. Add external retrieval and Baseline Scout after the local loop is stable.
4. Productize with exports, dashboard, Ask the Reviewer, and Revision Loop.

The first usable MVP should prove the core claim of the system: a PDF can be parsed into Paper IR, audited by multiple local agents, grounded in evidence, and exported as a PAT-style Markdown report plus JSON trace.

## 2. Delivery Principles

- Local loop before external search: do not depend on academic search quality before parsing, Paper IR, internal retrieval, and agent contracts are stable.
- Evidence before writing: every major/fatal issue must be backed by paper, computed, or external evidence before it reaches the final report.
- Schema before prompts: define shared data models and JSON contracts before optimizing prompt wording.
- Gates before polish: quality gates and hallucination checks are MVP functionality, not post-launch cleanup.
- Trace before UI: JSON trace, AgentRun logs, EvidenceStore, and IssueStore must exist before dashboard work.
- PAT-style report as default: human-facing output should use Summary, Strengths, Weaknesses, and section-level Potential Issues And Suggestions.
- Model-agnostic implementation: DeepSeek V4 Pro, GPT-5.5, and other backends should route through the same OpenAI-compatible adapter.

## 3. Milestone Timeline

| Phase | Milestone | Primary Outcome | Depends On |
|---|---|---|---|
| Phase 0 | Project Scaffold and Paper IR Kernel | PDF becomes traceable Paper IR | None |
| Phase 1 | Local Full Audit Loop | Internal multi-agent audit produces issue list | Phase 0 |
| Phase 2 | Evidence, Gates and PAT-style Report | Markdown report and JSON trace are evidence-gated | Phase 1 |
| Phase 3 | External Retrieval and Baseline Scout | Novelty/baseline issues use external evidence | Phase 2 |
| Phase 4 | Product Workflow and Revision Loop | User-facing workflow, exports, issue tracking | Phase 3 for full mode; Phase 2 for local mode |

## 4. Phase 0: Project Scaffold and Paper IR Kernel

### Goal

Create the technical foundation: a Python/FastAPI project skeleton, provider-neutral LLM adapter, job config model, PDF parsing pipeline, and Paper IR data structures.

### Deliverables

- Python/FastAPI backend scaffold.
- LangGraph agent orchestration baseline.
- PostgreSQL + pgvector + Redis service baseline.
- `docs/TECH-STACK.md` and `docs/spec/` engineering specification baseline.
- Core schemas for JobConfig, PaperDocument, PaperChunk, Table, Figure, Equation, Reference, EvidenceAnchor, Claim, Issue, and AgentRun.
- OpenAI-compatible LLM adapter with model profile routing.
- PDF parser producing sections, chunks, artifacts, references, parse confidence, and warnings.
- Initial object storage layout for uploaded PDFs and parsed artifacts.
- Minimal CLI or API entrypoint for parsing a sample PDF.

### Core Tasks

- Define Pydantic models for the core data structures described in `docs/SYSTEM-DESIGN.md` and `docs/spec/data-model.md`.
- Use uv, ruff, pytest, and mypy as the Python engineering baseline.
- Implement config loading for model provider, parser settings, object storage path, and review mode.
- Implement PDF ingestion and local file persistence.
- Use MinerU as the primary parser, PyMuPDF for page coordinates/fallback, and GROBID for metadata/references.
- Extract section headings, paragraph chunks, references, tables, figures, equations, algorithms, and appendix when available.
- Record parse warnings for low-confidence pages, missing references, failed table extraction, and low text density.
- Add unit tests for schema validation, chunk anchoring, parse warnings, and artifact extraction.

### Dependencies

- Python runtime and dependency management.
- PostgreSQL with pgvector and Redis.
- Parser choice and local installation path.
- Basic storage path for uploaded and parsed files.
- No external academic retrieval required.

### Exit Criteria

- A sample PDF can be uploaded or passed through a local command.
- The system writes a PaperDocument with section/chunk/artifact/reference records.
- Every chunk has at least page and section anchors when parser output supports them.
- Parse warnings are recorded and exposed to later phases.
- Phase 0 unit tests pass.

### Main Risks

- PDF parsing quality is lower than expected.
- Table and equation extraction are unreliable on complex papers.
- Parser dependencies are heavy or platform-specific.

### Mitigations

- Keep parser interface pluggable.
- Store raw parser outputs for debugging.
- Allow partial Paper IR with explicit parse warnings.
- Add later VLM fallback only after the base parser contract is stable.

## 5. Phase 1: Local Full Audit Loop

### Phase 1.5 Completed: PaperIR-first Parser Upgrade

The PDF parser has been upgraded from PyMuPDF-only fallback to a PaperIR-first canonical parser pipeline:

- Define PaperIR v0.2 as the authoritative parsing representation.
- Render `canonical_paper.md` from PaperIR, not directly from a third-party parser.
- Use `research_default` profile for internal research: GROBID + Marker + pdffigures2 + PyMuPDF.
- Keep `commercial_safe` profile available for later: GROBID + Docling + pdffigures2 + PyMuPDF.
- Persist `paper_ir.json`, `canonical_paper.md`, and `parse_report.json`.
- Add parse gates for text-based PDF status, section coverage, reference coverage, table confidence, figure/caption confidence and equation confidence.
- Treat scanned PDFs as unsupported until OCR is intentionally added.

Current smoke target: CPFL.pdf parses with GROBID, Marker and pdffigures2 connected, no Marker `<content-ref>` placeholders in canonical Markdown, and PaperIR preserving parser source trace.

### Phase 1.6: Markdown-first Global Understanding

Before deeper reviewer agents rely on LLM reasoning, pure-text LLM support should start from canonical Markdown:

- Expose `GET /api/jobs/{job_id}/markdown` for JSON envelope and `?raw=true` for `text/markdown`.
- Add `MarkdownUnderstandingAgent` that reads `canonical_paper.md` plus parse summary, not full PaperIR JSON.
- Write `PaperUnderstanding` and its `AgentRun` into `trace.json`.
- Use OpenAI-compatible LLM adapter with DeepSeek defaults and deterministic fallback when no API key is configured.
- Keep PaperIR as trace, parser provenance, section map, references, assets and future evidence anchor structure.

### Goal

Run a local multi-agent audit without external retrieval. The system should summarize the paper, extract claims, audit internal consistency, and produce an initial issue list with paper evidence anchors.

### Deliverables

- Lightweight DAG Orchestrator.
- Internal BM25, vector, and artifact retrieval minimum viable implementation.
- Paper Summarizer.
- Claim Miner.
- Technical Soundness Auditor.
- Experiment Auditor.
- Reproducibility Auditor.
- Writing and Presentation Auditor.
- Numeric Consistency Auditor.
- Question Tree Generator.
- Evidence Answering Agent.
- Meta-Reviewer skeleton.
- Local Quick Audit and Local Full Audit modes.

### Core Tasks

- Implement internal indexes over PaperChunk and artifacts.
- Implement a tool interface for agents to retrieve relevant paper evidence.
- Implement JSON output schemas and validation for each local agent.
- Implement Claim Miner to extract novelty, technical, theory, empirical, efficiency, privacy, safety, and reproducibility claims.
- Implement Numeric Consistency Auditor with deterministic calculations for averages, absolute/relative improvements, ranking, and best/second-best highlighting.
- Implement Question Tree generation from extracted claims and review dimensions.
- Implement Evidence Answering Agent to answer supported, partially_supported, unsupported, contradicted, or unclear.
- Implement Meta-Reviewer skeleton to merge duplicate local findings and downgrade unsupported issues.
- Add integration tests from Paper IR to initial issue list.

### Dependencies

- Phase 0 Paper IR and parser warnings.
- Internal retrieval index over chunks and artifacts.
- LLM adapter and schema validation.

### Exit Criteria

- A parsed PDF can run through Local Full Audit without external search.
- The system outputs a structured issue list with paper evidence anchors.
- Each major claim is assigned to at least one relevant local auditor.
- Numeric claims are checked or explicitly marked uncheckable.
- Agent JSON outputs are schema-validated.

### Main Risks

- Agents produce generic comments instead of evidence-specific issues.
- Claim Miner misses central contribution claims.
- Numeric auditor cannot parse enough table content.

### Mitigations

- Make evidence anchors mandatory in issue schemas.
- Add golden fixtures with expected major claims.
- Route low-confidence table parsing into warnings and manual verification.

## 6. Phase 2: Evidence, Gates and PAT-style Report

### Goal

Turn local audit output into a reliable evidence-gated report. This is the first MVP-quality milestone: Markdown PAT-style report plus JSON trace.

### Deliverables

- EvidenceStore.
- IssueStore.
- AgentRun log.
- Evidence Cards.
- Quality Gates: parsing, claim coverage, evidence, numeric, hallucination, actionability.
- PAT-style report schema.
- Markdown report export.
- JSON trace export.
- Partial report behavior when gates fail.

### Core Tasks

- Persist paper evidence, computed evidence, issues, agent runs, warnings, and gate statuses.
- Implement Evidence Gate: major/fatal issues require paper or computed evidence in this phase.
- Implement Hallucination Gate: final report cannot introduce papers, baselines, datasets, equations, tables, or numbers outside trace.
- Implement Actionability Gate: every major/fatal issue requires a concrete recommended fix.
- Implement Report Generator for PAT-style output:
  - Summary.
  - Strengths.
  - Weaknesses.
  - Potential Issues And Suggestions grouped by section/page range.
  - Potential Mistakes and Improvements.
  - Minor Corrections and Typos.
  - Evidence Appendix.
- Implement JSON trace export for Paper IR, claims, evidence, issues, agent runs, and gate status.
- Add integration tests for partial report on gate failure.

### Dependencies

- Phase 1 structured issue list.
- Stable EvidenceAnchor, Issue, and AgentRun schemas.
- Internal retrieval evidence anchors.

### Exit Criteria

- A sample PDF produces a PAT-style Markdown report and JSON trace.
- Major/fatal issues without evidence are blocked or downgraded.
- Final report contains no unsupported citations, baselines, datasets, equations, tables, or numbers.
- Section-level report groups include page ranges and issue locations.
- Partial report clearly states failed gates and missing evidence.

### Main Risks

- Report Generator compresses detailed issues into generic bullets.
- Hallucination Gate is too weak to catch unsupported generated facts.
- Gate failures make the report too sparse.

### Mitigations

- Generate from IssueStore rather than raw paper text.
- Validate report entities against PaperGraph, EvidenceStore, and computed checks.
- Allow possible/manual-verification sections for weakly supported concerns.

## 7. Phase 3: External Retrieval and Baseline Scout

### Goal

Add retrieval-augmented novelty, related work, and baseline auditing. This phase creates the PAT/ScholarPeer-style “comprehensive reviewer” feel while preserving evidence controls.

### Deliverables

- Query Planner.
- Academic search adapters.
- Metadata normalization and deduplication.
- Reranker.
- External Paper Reader.
- External Evidence Store.
- Evidence level classification A-D.
- Field Historian.
- Baseline Scout.
- Related Work Auditor.
- External evidence appendix.
- Retrieval Gate.

### Core Tasks

- Generate problem, method, dataset, benchmark, claim, baseline, and negative queries.
- Add source adapters for arXiv, Semantic Scholar or OpenAlex, CrossRef, OpenReview, ACL Anthology, Papers with Code, DBLP, GitHub Search, and conference proceedings where available.
- Normalize title, authors, venue, year, URL, abstract, source, query id, and cutoff-date compliance.
- Deduplicate search results and rerank by comparability.
- Implement evidence levels:
  - Level A: peer-reviewed papers and official benchmark pages.
  - Level B: arXiv, OpenReview submissions, technical reports.
  - Level C: GitHub README, blogs, unofficial docs.
  - Level D: snippets and secondary summaries.
- Implement Field Historian to map research lineage and closest method families.
- Implement Baseline Scout to identify missing baselines, weak comparisons, missing datasets/metrics, and unfair comparison risks.
- Implement Related Work Auditor to detect missing research branches and poorly positioned closest work.
- Update Hallucination Gate so external paper references must exist in External Evidence Store.

### Dependencies

- Phase 2 EvidenceStore, IssueStore, gates, report generation, and JSON trace.
- External search API keys or offline fixtures.
- Cutoff date and external retrieval permissions from JobConfig.

### Exit Criteria

- Novelty and baseline findings include search query ids and external evidence ids.
- Reference papers in the report come only from External Evidence Store.
- Major novelty/baseline concerns are not based solely on Level C/D evidence.
- Baseline Audit mode works as a standalone review mode.
- Retrieval Gate records query coverage and failed searches.

### Main Risks

- Search APIs are noisy, rate-limited, or unavailable.
- Baseline Scout over-reports weakly related papers.
- Confidential manuscripts may leak details through exact search queries.

### Mitigations

- Cache search results and support offline fixtures.
- Require direct comparability rationale for baseline severity.
- Support paraphrased queries, external retrieval off mode, and query logs for user inspection.

## 8. Phase 4: Product Workflow and Revision Loop

### Goal

Turn the validated review engine into a usable product workflow with job status, exports, issue tracking, and multi-version revision support.

### Deliverables

- Job dashboard.
- Job status API.
- Report export API.
- PDF report export.
- Optional annotated PDF.
- Ask the Reviewer.
- Revision Loop.
- Venue profiles.
- Retention policy.
- Budget and token tracking.

### Core Tasks

- Expose job lifecycle states: created, parsing, indexing, summarizing, claim_mining, retrieval, auditing, question_answering, verifying, reporting, completed, partial_report, failed.
- Implement dashboard views for stage, agent status, parse warnings, claim count, issue count, retrieval count, and gate status.
- Implement report downloads for Markdown, PDF, JSON trace, and optional annotated PDF.
- Implement Issue Cards with resolved, ignored, needs_more_work, and ask_followup states.
- Implement Ask the Reviewer constrained to EvidenceStore, IssueStore, user-provided new context, and JSON trace.
- Implement Revision Loop:
  - upload v1 and v2.
  - map old issues to new paper evidence.
  - classify resolved, partially resolved, unresolved, and new issue.
- Implement venue profiles for default review dimensions, checklist expectations, and output wording.
- Add retention policy and per-job cost/token tracking.

### Dependencies

- Phase 2 for local-only product workflow.
- Phase 3 for full retrieval-enhanced workflow.
- Stable report and trace format.

### Exit Criteria

- User can upload a paper, monitor job status, download report, inspect issue evidence, and export trace.
- Ask the Reviewer does not introduce facts outside evidence or user-provided context.
- Revision Loop compares two versions and reports issue resolution status.
- Product workflow handles failed gates and partial reports transparently.

### Main Risks

- UI work distracts from core review quality.
- Ask the Reviewer becomes an unrestricted chatbot.
- Revision matching is unreliable when sections move or text changes heavily.

### Mitigations

- Keep UI utilitarian and evidence-first.
- Enforce retrieval and evidence constraints in Ask the Reviewer.
- Use claim ids, evidence anchors, text similarity, and section mapping for revision issue matching.

## 9. Cross-Cutting Workstreams

### Evaluation and Fixtures

- Build a small golden paper set with expected claims, tables, known inconsistencies, missing baselines, evidence anchors, and report sections.
- Compare single-prompt baseline, no-external-retrieval variant, no-baseline-scout variant, and full system.
- Track human issue recall, evidence precision, hallucination rate, severity calibration, baseline discovery rate, numeric audit accuracy, actionability score, and false positive burden.

### Privacy and Security

- Treat manuscript and retrieved text as untrusted data.
- Add prompt injection defense in all agent prompts.
- Support anonymization before remote LLM calls.
- Keep external query logs inspectable.
- Keep manuscript retention configurable.

### Observability and Cost

- Track model name, prompt version, input hash, tool calls, token usage, cost estimate, warnings, and output schema validation for every AgentRun.
- Track parser confidence, retrieval coverage, gate status, and report generation warnings per job.
- Support retrieval budget, agent budget, token budget, and per-job cost reporting.

### Prompt and Schema Governance

- Version all agent prompts.
- Validate every agent output against JSON schema.
- Keep report generation downstream of IssueStore and EvidenceStore.
- Add regression tests whenever prompt versions change.

## 10. Acceptance Criteria

The MVP is acceptable when:

- PDF is parsed into Paper IR with parse confidence and warnings.
- Major contribution claims are detected and assigned to relevant auditors.
- Local Full Audit produces evidence-anchored issues.
- Numeric claims are checked or explicitly marked uncheckable.
- EvidenceStore, IssueStore, AgentRun log, and gate status are persisted.
- PAT-style Markdown report and JSON trace can be exported.
- Major/fatal issues without evidence are blocked, downgraded, or marked for manual verification.
- Final report does not introduce facts outside PaperGraph, EvidenceStore, IssueStore, computed checks, or AgentRun records.

The retrieval-enhanced system is acceptable when:

- Novelty and baseline findings include external evidence ids and query logs.
- External paper references in the report come only from External Evidence Store.
- Major novelty/baseline concerns rely on Level A/B evidence or are explicitly marked as weaker evidence.
- Baseline Audit mode can run independently.

The product workflow is acceptable when:

- Users can upload a PDF, inspect job status, download report and JSON trace, and inspect issue evidence.
- Partial reports clearly identify failed gates.
- Ask the Reviewer remains evidence-constrained.
- Revision Loop classifies old issues as resolved, partially resolved, unresolved, or newly introduced.

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| PDF parsing quality is poor | Bad evidence anchors and weak report quality | Parser abstraction, parse warnings, partial report, later VLM fallback |
| Agents hallucinate facts | Unsupported review criticisms | EvidenceStore-only report generation and Hallucination Gate |
| Claim Miner misses central claims | Incomplete audit coverage | Golden fixtures, claim coverage gate, summarizer cross-check |
| Numeric tables are hard to parse | Weak computed evidence | Explicit uncheckable state, table confidence, manual verification section |
| External search is noisy | False missing-baseline accusations | Reranking, direct comparability rationale, evidence levels |
| Search leaks private paper details | Confidentiality risk | Query anonymization, external retrieval off mode, query logs |
| UI ships before review engine is reliable | Product looks usable but gives shallow feedback | Phase 4 depends on Phase 2 local MVP |
| Prompt changes regress quality | Unstable behavior | Prompt versioning, schema validation, regression fixtures |
