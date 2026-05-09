from pathlib import Path

from app.core.models import JobConfig
from app.parsing.pymupdf_parser import PyMuPDFParser


def test_pymupdf_parser_extracts_traceable_paper_ir(sample_pdf_path: Path) -> None:
    parser = PyMuPDFParser()

    result = parser.parse(sample_pdf_path, job_id="job_123", config=JobConfig())

    assert result.provider == "pymupdf"
    assert result.paper_document.paper_id.startswith("paper_")
    assert result.paper_document.page_count == 1
    assert result.paper_document.chunks
    assert all(chunk.page_start >= 1 for chunk in result.paper_document.chunks)
    assert "Abstract" in result.paper_document.sections
    assert result.paper_document.figures
    assert result.paper_document.tables
    assert result.paper_document.references
    assert result.parse_confidence > 0
