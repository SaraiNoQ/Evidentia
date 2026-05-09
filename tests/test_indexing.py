from pathlib import Path

from app.core.models import JobConfig, PaperDocument
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


def test_internal_index_returns_evidence_anchored_hits(sample_pdf_path: Path) -> None:
    paper = _parse_sample(sample_pdf_path)
    index = InternalPaperIndex(paper)

    hits = index.search("reviewer workflow parser output", limit=3)

    assert hits
    assert hits[0].source_id.startswith(("chunk_", "artifact_"))
    assert hits[0].page == 1
    assert hits[0].section
    assert hits[0].quote
    assert hits[0].score > 0


def test_artifact_retrieval_searches_captions(sample_pdf_path: Path) -> None:
    paper = _parse_sample(sample_pdf_path)
    index = InternalPaperIndex(paper)

    hits = index.search_artifacts("parser output fields", limit=2)

    assert hits
    assert hits[0].artifact_id is not None
    assert "Parser output" in hits[0].quote
