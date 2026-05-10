import re

from app.core.ids import new_id
from app.core.models import (
    FigureArtifactV2,
    PaperAssetInventory,
    PaperBlock,
    PaperBlockType,
    PaperDocument,
    PaperIR,
    PaperMetadata,
    ParseReport,
    ParserProfile,
    ParserProvenance,
    ParserSource,
    ReferenceRecord,
    SectionNode,
    TableArtifactV2,
    TextBasedPdfStatus,
)


def paper_document_to_ir(
    paper: PaperDocument,
    *,
    parser_profile: ParserProfile,
    source_parser: ParserSource = ParserSource.PYMUPDF,
) -> PaperIR:
    """Build PaperIR v0.2 from the current PyMuPDF fallback PaperDocument."""

    section_by_title: dict[str, SectionNode] = {}
    blocks: list[PaperBlock] = []

    for title in paper.sections or ["Unknown"]:
        section_node = SectionNode(
            section_id=new_id("sec"),
            title=title,
            normalized_title=_normalize_title(title),
            level=_section_level(title),
            source=source_parser,
            confidence=0.65,
        )
        section_by_title[title] = section_node

    for chunk in paper.chunks:
        section = section_by_title.get(chunk.section_title)
        if section is None:
            section = SectionNode(
                section_id=new_id("sec"),
                title=chunk.section_title,
                normalized_title=_normalize_title(chunk.section_title),
                level=_section_level(chunk.section_title),
                source=source_parser,
                confidence=0.45,
            )
            section_by_title[chunk.section_title] = section

        block = PaperBlock(
            block_id=new_id("block"),
            block_type=PaperBlockType.PARAGRAPH,
            section_id=section.section_id,
            text=chunk.text,
            markdown=chunk.text,
            source_parser=source_parser,
            confidence=chunk.confidence,
            provenance=ParserProvenance(
                source_parser=source_parser,
                source_id=chunk.chunk_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                confidence=chunk.confidence,
            ),
        )
        blocks.append(block)
        section.block_ids.append(block.block_id)

    references = [
        ReferenceRecord(
            bib_id=new_id("bib"),
            raw=reference.raw_text,
            title=reference.title,
            authors=reference.authors,
            year=reference.year,
            doi=reference.doi,
            url=reference.url,
        )
        for reference in paper.references
    ]

    figures = [
        FigureArtifactV2(
            figure_id=new_id("figure"),
            label=figure.label,
            caption=figure.caption,
            section_id=_section_id_for_title(section_by_title, figure.section),
            source_parser=source_parser,
            caption_confidence=figure.confidence,
        )
        for figure in paper.figures
    ]
    tables = [
        TableArtifactV2(
            table_id=new_id("table"),
            label=table.label,
            caption=table.caption,
            cells=table.cells,
            section_id=_section_id_for_title(section_by_title, table.section),
            source_parser=source_parser,
            confidence=table.confidence,
        )
        for table in paper.tables
    ]

    parse_report = ParseReport(
        text_based_pdf=_text_based_status(paper),
        page_count=paper.page_count,
        parsed_pages=len({chunk.page_start for chunk in paper.chunks}),
        section_coverage=1.0 if paper.sections else 0.0,
        reference_coverage=1.0 if paper.references else 0.0,
        table_confidence=_average([table.confidence for table in paper.tables]),
        figure_caption_alignment_confidence=_average(
            [figure.confidence for figure in paper.figures]
        ),
        equation_confidence=_average([equation.confidence for equation in paper.equations]),
        parser_profile=parser_profile,
        parser_sources=[source_parser],
        warnings=[
            *paper.warnings,
            "paper_ir_v0_2_built_from_pymupdf_fallback",
            "grobid_marker_pdffigures2_not_connected_yet",
        ],
    )

    return PaperIR(
        paper_id=paper.paper_id,
        metadata=PaperMetadata(title=paper.title),
        abstract=_extract_abstract(blocks, section_by_title),
        sections=list(section_by_title.values()),
        blocks=blocks,
        references=references,
        assets=PaperAssetInventory(figures=figures, tables=tables, equations=[], images=[]),
        parse_report=parse_report,
    )


def render_canonical_markdown(paper_ir: PaperIR) -> str:
    lines: list[str] = []
    title = paper_ir.metadata.title or "Untitled Paper"
    lines.extend([f"# {title}", ""])

    if paper_ir.metadata.authors:
        lines.extend(["## Authors", "", ", ".join(paper_ir.metadata.authors), ""])

    if paper_ir.abstract:
        lines.extend(["## Abstract", "", paper_ir.abstract, ""])

    block_by_id = {block.block_id: block for block in paper_ir.blocks}
    rendered_abstract = False
    for section in paper_ir.sections:
        if section.normalized_title == "abstract" and paper_ir.abstract:
            rendered_abstract = True
            continue
        heading_level = min(section.level + 1, 6)
        lines.extend([f"{'#' * heading_level} {section.title}", ""])
        for block_id in section.block_ids:
            block = block_by_id.get(block_id)
            if block is None:
                continue
            if rendered_abstract and section.normalized_title == "abstract":
                continue
            lines.extend([block.markdown or block.text, ""])
        for table in paper_ir.assets.tables:
            if table.section_id == section.section_id:
                lines.extend(_render_table(table))
        for figure in paper_ir.assets.figures:
            if figure.section_id == section.section_id:
                lines.extend(_render_figure(figure))

    if paper_ir.references:
        lines.extend(["## References", ""])
        for index, reference in enumerate(paper_ir.references, start=1):
            lines.extend([f"[{index}] {reference.raw}", ""])

    return "\n".join(lines).strip() + "\n"


def _render_table(table: TableArtifactV2) -> list[str]:
    lines = []
    if table.caption:
        lines.extend([f"**{table.caption}**", ""])
    if table.html:
        lines.extend([table.html, ""])
    elif table.markdown:
        lines.extend([table.markdown, ""])
    elif table.cells:
        lines.extend(_cells_to_markdown(table.cells))
    return lines


def _render_figure(figure: FigureArtifactV2) -> list[str]:
    alt = figure.caption or figure.label or figure.figure_id
    image_path = figure.image_path or ""
    lines = [f"![{alt}]({image_path})", ""]
    if figure.caption:
        lines.extend([f"**{figure.caption}**", ""])
    return lines


def _cells_to_markdown(cells: list[list[str]]) -> list[str]:
    if not cells:
        return []
    width = max(len(row) for row in cells)
    padded = [row + [""] * (width - len(row)) for row in cells]
    header = "| " + " | ".join(padded[0]) + " |"
    separator = "| " + " | ".join(["---"] * width) + " |"
    body = ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return [header, separator, *body, ""]


def _extract_abstract(blocks: list[PaperBlock], sections: dict[str, SectionNode]) -> str | None:
    abstract_section_ids = {
        section.section_id
        for section in sections.values()
        if section.normalized_title == "abstract"
    }
    abstract_blocks = [block.text for block in blocks if block.section_id in abstract_section_ids]
    if not abstract_blocks:
        return None
    return "\n\n".join(abstract_blocks)


def _section_id_for_title(sections: dict[str, SectionNode], title: str | None) -> str | None:
    if title is None:
        return None
    section = sections.get(title)
    return section.section_id if section else None


def _normalize_title(title: str) -> str:
    normalized = re.sub(r"^\d+(\.\d+)*\s+", "", title.strip().lower())
    return re.sub(r"\s+", " ", normalized)


def _section_level(title: str) -> int:
    match = re.match(r"^(\d+(?:\.\d+)*)\s+", title.strip())
    if not match:
        return 1
    return match.group(1).count(".") + 1


def _text_based_status(paper: PaperDocument) -> TextBasedPdfStatus:
    if paper.page_count == 0 or not paper.chunks:
        return TextBasedPdfStatus.UNSUPPORTED_SCANNED
    parsed_pages = len({chunk.page_start for chunk in paper.chunks})
    coverage = parsed_pages / max(paper.page_count, 1)
    if coverage < 0.5:
        return TextBasedPdfStatus.LOW_TEXT
    return TextBasedPdfStatus.TEXT_BASED


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
