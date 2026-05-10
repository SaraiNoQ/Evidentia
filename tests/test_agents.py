import asyncio
from pathlib import Path

from app.agents.claim_miner import ClaimMiner
from app.agents.markdown_understanding import MarkdownUnderstandingAgent
from app.agents.meta_reviewer import MetaReviewer
from app.agents.orchestrator import LocalAuditOrchestrator
from app.agents.question_answering import EvidenceAnsweringAgent, QuestionTreeGenerator
from app.core.config import Settings
from app.core.ids import new_id
from app.core.models import (
    Issue,
    IssueSeverity,
    JobConfig,
    PaperDocument,
)
from app.indexing.internal import InternalPaperIndex
from app.parsing.pymupdf_parser import PyMuPDFParser


def _parse_sample(sample_pdf_path: Path) -> PaperDocument:
    return (
        PyMuPDFParser()
        .parse(
            sample_pdf_path,
            job_id="job_123",
            config=JobConfig(),
        )
        .paper_document
    )


def test_claim_miner_extracts_schema_valid_claims(sample_pdf_path: Path) -> None:
    paper = _parse_sample(sample_pdf_path)
    index = InternalPaperIndex(paper)

    claims, run = ClaimMiner().run(paper, index)

    assert claims
    assert all(claim.claim_id.startswith("claim_") for claim in claims)
    assert all(claim.evidence for claim in claims)
    assert run.agent_name == "claim_miner"


def test_evidence_answer_uses_allowed_states(sample_pdf_path: Path) -> None:
    paper = _parse_sample(sample_pdf_path)
    index = InternalPaperIndex(paper)
    claims, _ = ClaimMiner().run(paper, index)
    questions, _ = QuestionTreeGenerator().run(paper, claims)

    answers, run = EvidenceAnsweringAgent().run(paper, questions, claims, index)

    assert answers
    assert {answer.answer for answer in answers} <= {
        "supported",
        "partially_supported",
        "unsupported",
        "contradicted",
        "unclear",
    }
    assert run.agent_name == "evidence_answering_agent"


def test_meta_reviewer_downgrades_unsupported_major_issue(sample_pdf_path: Path) -> None:
    paper = _parse_sample(sample_pdf_path)
    issue = Issue(
        issue_id=new_id("issue"),
        title="Unsupported major issue",
        severity=IssueSeverity.MAJOR,
        dimension="technical_soundness",
        description="No evidence attached.",
        recommended_fix="Attach evidence or downgrade the concern.",
        confidence=0.5,
    )

    issues, _ = MetaReviewer().run(paper, [issue])

    assert issues[0].severity == IssueSeverity.POSSIBLE
    assert "major_or_fatal_issue_missing_evidence" in issues[0].missing_evidence


def test_local_audit_orchestrator_outputs_issues_and_agent_runs(sample_pdf_path: Path) -> None:
    paper = _parse_sample(sample_pdf_path)

    result = LocalAuditOrchestrator().run(paper)

    assert result.summary is not None
    assert result.claims
    assert result.questions
    assert result.evidence_answers
    assert result.issues
    assert {run.agent_name for run in result.agent_runs} >= {
        "paper_summarizer",
        "claim_miner",
        "technical_soundness_auditor",
        "experiment_auditor",
        "reproducibility_auditor",
        "writing_presentation_auditor",
        "numeric_consistency_auditor",
        "question_tree_generator",
        "evidence_answering_agent",
        "meta_reviewer",
    }


def test_markdown_understanding_agent_uses_deterministic_fallback() -> None:
    markdown = """# Test Paper

## Abstract

This paper proposes a Markdown-first reviewer workflow.

## 1 Introduction

We propose a canonical markdown understanding step before detailed review.
"""

    understanding, run = asyncio.run(
        MarkdownUnderstandingAgent(Settings(llm_api_key=None)).run(
            job_id="job_123", markdown=markdown, paper_ir=None
        )
    )

    assert understanding.global_summary
    assert understanding.source == "deterministic"
    assert run.agent_name == "markdown_understanding_agent"
    assert "llm_api_key_missing_using_deterministic_fallback" in run.warnings
