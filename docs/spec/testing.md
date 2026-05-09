# Testing Spec

## 1. Test Layers

Use four layers:

- Unit tests.
- Integration tests.
- Golden regression fixtures.
- Evaluation tests.

All Python tests use `pytest`.

## 2. Unit Tests

Required unit coverage:

- Pydantic schema validation.
- JobConfig validation.
- parser warning generation.
- chunk anchoring.
- reference normalization.
- numeric calculations.
- gate pass/fail logic.
- hallucination checker entity matching.
- report schema validation.

## 3. Integration Tests

Required integration paths:

- PDF to Paper IR.
- Paper IR to internal indexes.
- Paper IR to ClaimGraph.
- ClaimGraph to local agent DAG.
- IssueStore to PAT-style report.
- gate failure to partial report.
- JSON trace export.

## 4. Golden Fixtures

Maintain fixture papers with expected:

- major claims.
- tables and numeric cells.
- known numeric inconsistencies.
- known missing baselines.
- expected evidence anchors.
- expected report sections.

Golden fixture changes require review because they define expected behavior.

## 5. Evaluation Tests

Compare:

- single-prompt baseline.
- no-external-retrieval variant.
- no-baseline-scout variant.
- full multi-agent system.

Track:

- human issue recall.
- evidence precision.
- hallucination rate.
- severity calibration.
- baseline discovery rate.
- numeric audit accuracy.
- actionability score.
- false positive burden.

## 6. CI Minimum Gate

Before merge:

- `uv sync` succeeds.
- `ruff check` succeeds.
- `ruff format --check` succeeds.
- `mypy` succeeds for typed backend packages.
- `pytest` succeeds for required unit and integration tests.

