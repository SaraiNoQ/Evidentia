from pathlib import Path

from app.core.models import JobConfig, ParserProfile, TextBasedPdfStatus
from app.parsing.paper_ir import paper_document_to_ir, render_canonical_markdown
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


def test_paper_document_converts_to_paper_ir_and_canonical_markdown(
    sample_pdf_path: Path,
) -> None:
    result = PyMuPDFParser().parse(sample_pdf_path, job_id="job_123", config=JobConfig())

    paper_ir = paper_document_to_ir(
        result.paper_document,
        parser_profile=ParserProfile.RESEARCH_DEFAULT,
    )
    markdown = render_canonical_markdown(paper_ir)

    assert paper_ir.paper_id == result.paper_document.paper_id
    assert paper_ir.sections
    assert paper_ir.blocks
    assert paper_ir.assets.figures
    assert paper_ir.assets.tables
    assert paper_ir.parse_report.text_based_pdf == TextBasedPdfStatus.TEXT_BASED
    assert "paper_ir_v0_2_built_from_pymupdf_fallback" in paper_ir.parse_report.warnings
    assert "# Untitled Paper" in markdown
    assert "## References" in markdown
    assert "Figure 1: Overview" in markdown
