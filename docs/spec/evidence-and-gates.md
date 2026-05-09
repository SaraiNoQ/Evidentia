# Evidence and Gates Spec

## 1. Evidence Classes

Evidence types:

- Paper evidence: manuscript quote, page, section, line span, table, figure, equation, appendix.
- External evidence: paper, benchmark page, OpenReview submission, arXiv, GitHub, official docs.
- Computed evidence: deterministic checks over tables, numbers, rankings, and consistency.
- User evidence: user-supplied clarification or extra material.

## 2. EvidenceStore Rules

- Every evidence item has stable id, source type, source id, quote or computed result, confidence, and locator.
- Paper evidence must include page or artifact id when available.
- External evidence must include URL, source, retrieval query id, retrieval timestamp, and evidence level.
- Computed evidence must include input ids and calculation method.

## 3. IssueStore Rules

- Major/fatal issues require at least one evidence item.
- Issues without enough evidence must be `possible`.
- Counter-evidence must be preserved.
- Recommended fix is required for major/fatal issues.

## 4. Quality Gates

Required MVP gates:

- Parsing Gate.
- Claim Coverage Gate.
- Evidence Gate.
- Numeric Gate.
- Hallucination Gate.
- Actionability Gate.

Retrieval-enhanced gate:

- Retrieval Gate.

Optional later gates:

- Conflict Gate.
- Privacy Gate.
- Cost Gate.

## 5. Gate Failure Behavior

- Gate failures must be written to gate status.
- Failed gates may produce partial reports.
- The report must explain failed gates and missing evidence.
- Failed gates must not be hidden in UI or report export.

## 6. Hallucination Gate

The final report is invalid if it contains:

- unsupported paper title.
- unsupported baseline.
- unsupported dataset.
- unsupported metric.
- unsupported numeric result.
- unsupported theorem/equation/table reference.
- unsupported external citation.

All such entities must resolve to PaperGraph, EvidenceStore, IssueStore, External Evidence Store, computed checks, or user context.

