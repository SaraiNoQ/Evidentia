import pytest
from pydantic import ValidationError

from app.core.models import (
    CharSpan,
    EvidenceAnchor,
    EvidenceLevel,
    EvidenceSourceType,
    JobConfig,
    PaperChunk,
    ReviewMode,
)


def test_job_config_defaults() -> None:
    config = JobConfig()

    assert config.review_mode == ReviewMode.QUICK_AUDIT
    assert config.parser_provider == "pymupdf"
    assert config.external_retrieval_enabled is False


def test_job_config_rejects_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        JobConfig.model_validate({"review_mode": "invalid"})


def test_id_prefix_validation() -> None:
    with pytest.raises(ValidationError):
        PaperChunk(
            chunk_id="bad_123",
            paper_id="paper_123",
            section_title="Introduction",
            text="body",
            page_start=1,
            page_end=1,
        )


def test_char_span_order_validation() -> None:
    with pytest.raises(ValidationError):
        CharSpan(start=10, end=3)


def test_evidence_anchor_schema() -> None:
    anchor = EvidenceAnchor(
        evidence_id="ev_123",
        source_type=EvidenceSourceType.PAPER,
        source_id="chunk_123",
        page=1,
        section="Introduction",
        quote="quoted evidence",
        confidence=0.8,
        evidence_level=EvidenceLevel.B,
    )

    assert anchor.evidence_id == "ev_123"
    assert anchor.confidence == 0.8
