from pathlib import Path

from pytest import MonkeyPatch

from app.core.ids import new_id
from app.core.models import (
    JobConfig,
    PaperBlock,
    PaperBlockType,
    PaperMetadata,
    ParserProfile,
    ParserProvenance,
    ParserSource,
    ReviewMode,
    SectionNode,
)
from app.parsing.candidates import GrobidParseOutput, MarkerParseOutput, Pdffigures2ParseOutput
from app.parsing.ensemble import PaperIREnsembleParser
from app.parsing.fusion import PaperIRFusionEngine, _find_section_by_title
from app.parsing.grobid_adapter import GrobidTeiParser
from app.parsing.marker_adapter import MarkerAdapter
from app.parsing.pdffigures2_adapter import Pdffigures2Adapter
from app.parsing.pymupdf_parser import PyMuPDFParser


def test_grobid_tei_parser_extracts_skeleton() -> None:
    tei = """<?xml version="1.0" encoding="UTF-8"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader>
        <fileDesc>
          <titleStmt>
            <title>Verifier-Guided Paper Review</title>
            <author><persName><forename>Ada</forename><surname>Lovelace</surname></persName></author>
          </titleStmt>
          <sourceDesc>
            <biblStruct>
              <analytic><title>Evidence Grounded Agents</title></analytic>
              <monogr><imprint><date when="2025"/></imprint></monogr>
              <idno type="DOI">10.0000/example</idno>
            </biblStruct>
          </sourceDesc>
        </fileDesc>
        <profileDesc>
          <abstract><p>We study evidence grounded reviewing.</p></abstract>
        </profileDesc>
      </teiHeader>
      <text>
        <body>
          <div n="1"><head>Introduction</head>
            <p>Prior work <ref type="bibr" target="#b1">[1]</ref>.</p>
          </div>
          <div n="2"><head>Method</head><p>Method text.</p></div>
        </body>
        <back>
          <listBibl>
            <biblStruct xml:id="b1">
              <analytic>
                <title>Reference Title</title>
                <author><persName><forename>Jane</forename><surname>Smith</surname></persName></author>
              </analytic>
              <monogr><imprint><date when="2024"/></imprint></monogr>
              <idno type="DOI">10.1111/ref</idno>
            </biblStruct>
          </listBibl>
        </back>
      </text>
    </TEI>
    """

    output = GrobidTeiParser().parse(tei)

    assert output.metadata.title == "Verifier-Guided Paper Review"
    assert output.abstract == "We study evidence grounded reviewing."
    assert [section.title for section in output.sections] == ["Introduction", "Method"]
    assert output.references[0].title == "Reference Title"
    assert output.references[0].year == 2024
    assert output.citations[0].marker == "[1]"


def test_marker_json_payload_extracts_blocks() -> None:
    output = MarkerAdapter(enabled=True, output_format="json").parse_json_payload(
        {
            "markdown": "# Introduction\n\nWe propose a reviewer agent.",
            "children": [
                {"block_type": "heading", "text": "Introduction"},
                {"block_type": "paragraph", "text": "We propose a reviewer agent."},
            ],
        }
    )

    assert output.markdown
    assert [block.block_type for block in output.blocks] == [
        PaperBlockType.HEADING,
        PaperBlockType.PARAGRAPH,
    ]
    assert all(block.source_parser == ParserSource.MARKER for block in output.blocks)


def test_pdffigures2_json_payload_extracts_artifacts(tmp_path: Path) -> None:
    output = Pdffigures2Adapter(enabled=True, command="pdffigures2").parse_json_payload(
        [
            {"figType": "Figure", "name": "1", "caption": "Figure 1. System architecture."},
            {"figType": "Table", "name": "1", "caption": "Table 1. Main results."},
        ],
        tmp_path,
    )

    assert output.figures[0].caption == "Figure 1. System architecture."
    assert output.figures[0].source_parser == ParserSource.PDFFIGURES2
    assert output.tables[0].caption == "Table 1. Main results."
    assert output.tables[0].source_parser == ParserSource.PDFFIGURES2


def test_fusion_prefers_grobid_skeleton_and_adds_provider_sources(
    sample_pdf_path: Path,
) -> None:
    fallback = PyMuPDFParser().parse(sample_pdf_path, job_id="job_123", config=JobConfig())
    sections = [
        SectionNode(
            section_id=new_id("sec"),
            title="Introduction",
            normalized_title="introduction",
            level=1,
            source=ParserSource.GROBID,
            confidence=0.9,
        ),
        SectionNode(
            section_id=new_id("sec"),
            title="Experiments",
            normalized_title="experiments",
            level=1,
            source=ParserSource.GROBID,
            confidence=0.9,
        ),
    ]
    marker_block = PaperBlock(
        block_id=new_id("block"),
        block_type=PaperBlockType.PARAGRAPH,
        text="Marker recovered content.",
        markdown="Marker recovered content.",
        source_parser=ParserSource.MARKER,
        confidence=0.8,
        provenance=ParserProvenance(source_parser=ParserSource.MARKER, confidence=0.8),
    )
    pdffigures = Pdffigures2ParseOutput(
        figures=Pdffigures2Adapter(enabled=True, command="pdffigures2")
        .parse_json_payload(
            [{"figType": "Figure", "name": "2", "caption": "Figure 2. Recovered figure."}]
        )
        .figures
    )

    paper_ir = PaperIRFusionEngine().fuse(
        fallback_document=fallback.paper_document,
        parser_profile=ParserProfile.RESEARCH_DEFAULT,
        grobid=GrobidParseOutput(
            metadata=PaperMetadata(title="GROBID Title"),
            abstract="GROBID abstract.",
            sections=sections,
            references=[],
        ),
        marker=MarkerParseOutput(blocks=[marker_block]),
        pdffigures2=pdffigures,
    )

    assert paper_ir.metadata.title == "GROBID Title"
    assert [section.title for section in paper_ir.sections] == ["Introduction", "Experiments"]
    assert ParserSource.GROBID in paper_ir.parse_report.parser_sources
    assert ParserSource.MARKER in paper_ir.parse_report.parser_sources
    assert ParserSource.PDFFIGURES2 in paper_ir.parse_report.parser_sources
    assert ParserSource.FUSION in paper_ir.parse_report.parser_sources
    assert any(
        figure.caption == "Figure 2. Recovered figure." for figure in paper_ir.assets.figures
    )


def test_ensemble_keeps_pymupdf_fallback_when_providers_missing(
    monkeypatch: MonkeyPatch,
    sample_pdf_path: Path,
) -> None:
    monkeypatch.setattr(
        "app.parsing.ensemble.GrobidAdapter.parse",
        lambda _self, _pdf_path: GrobidParseOutput(warnings=["grobid_unavailable:test"]),
    )
    monkeypatch.setattr(
        "app.parsing.ensemble.MarkerAdapter.parse",
        lambda _self, _pdf_path, _output_dir, **_kwargs: MarkerParseOutput(
            warnings=["marker_unavailable"]
        ),
    )
    monkeypatch.setattr(
        "app.parsing.ensemble.Pdffigures2Adapter.parse",
        lambda _self, _pdf_path, _output_dir: Pdffigures2ParseOutput(
            warnings=["pdffigures2_unavailable"]
        ),
    )

    result = PaperIREnsembleParser().parse(
        sample_pdf_path,
        job_id="job_123",
        config=JobConfig(),
    )

    assert result.provider == "paper_ir_ensemble"
    assert result.paper_ir is not None
    assert ParserSource.PYMUPDF in result.paper_ir.parse_report.parser_sources
    assert ParserSource.FUSION in result.paper_ir.parse_report.parser_sources
    assert "grobid_unavailable:test" in result.warnings
    assert "marker_unavailable" in result.warnings
    assert "pdffigures2_unavailable" in result.warnings


def test_quick_audit_does_not_limit_marker_pages_by_default() -> None:
    limit = PaperIREnsembleParser()._marker_page_limit(
        JobConfig(review_mode=ReviewMode.QUICK_AUDIT),
        page_count=12,
    )

    assert limit is None


def test_explicit_max_pages_limits_marker_pages() -> None:
    limit = PaperIREnsembleParser()._marker_page_limit(
        JobConfig(max_pages=3),
        page_count=12,
    )

    assert limit == 3


def test_section_matching_normalizes_letter_prefix_and_ligature_spacing() -> None:
    sections = [
        SectionNode(
            section_id=new_id("sec"),
            title="C. Efficiency, Scalability, and Fairness in BFL Architectures",
            normalized_title="c. efficiency, scalability, and fairness in bfl architectures",
            level=2,
            source=ParserSource.GROBID,
            confidence=0.9,
        )
    ]

    match = _find_section_by_title(
        sections,
        "C. E ffi ciency, Scalability, and Fairness in BFL Architectures",
    )

    assert match is sections[0]
