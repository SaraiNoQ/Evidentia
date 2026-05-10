import re

from app.core.ids import new_id
from app.core.models import (
    PaperBlock,
    PaperDocument,
    PaperIR,
    PaperMetadata,
    ParseReport,
    ParserProfile,
    ParserSource,
    SectionNode,
)
from app.parsing.candidates import (
    GrobidParseOutput,
    MarkerParseOutput,
    Pdffigures2ParseOutput,
)
from app.parsing.paper_ir import paper_document_to_ir


class PaperIRFusionEngine:
    """Merge parser candidates into the project-owned PaperIR representation."""

    def fuse(
        self,
        *,
        fallback_document: PaperDocument,
        parser_profile: ParserProfile,
        grobid: GrobidParseOutput | None = None,
        marker: MarkerParseOutput | None = None,
        pdffigures2: Pdffigures2ParseOutput | None = None,
    ) -> PaperIR:
        paper_ir = paper_document_to_ir(
            fallback_document,
            parser_profile=parser_profile,
            source_parser=ParserSource.PYMUPDF,
        )
        paper_ir.parse_report.warnings = [
            warning
            for warning in paper_ir.parse_report.warnings
            if warning != "grobid_marker_pdffigures2_not_connected_yet"
        ]
        self._add_source(paper_ir.parse_report, ParserSource.FUSION)

        self._merge_grobid(paper_ir, grobid)
        self._merge_marker(paper_ir, marker)
        self._merge_pdffigures2(paper_ir, pdffigures2)
        self._refresh_report(paper_ir, parser_profile)
        paper_ir.parse_report.warnings = _dedupe(paper_ir.parse_report.warnings)
        return paper_ir

    def _merge_grobid(self, paper_ir: PaperIR, grobid: GrobidParseOutput | None) -> None:
        if grobid is None:
            paper_ir.parse_report.warnings.append("grobid_unavailable")
            paper_ir.parse_report.warnings.append("using_pymupdf_fallback_sections")
            paper_ir.parse_report.warnings.append("using_pymupdf_fallback_references")
            return

        paper_ir.parse_report.warnings.extend(grobid.warnings)
        if _has_unavailable_warning(grobid.warnings):
            paper_ir.parse_report.warnings.append("using_pymupdf_fallback_sections")
            paper_ir.parse_report.warnings.append("using_pymupdf_fallback_references")
            return

        self._add_source(paper_ir.parse_report, ParserSource.GROBID)
        paper_ir.metadata = self._merged_metadata(paper_ir.metadata, grobid.metadata)
        if grobid.abstract:
            paper_ir.abstract = grobid.abstract
        if grobid.sections:
            self._replace_sections(paper_ir, grobid.sections)
        if grobid.references:
            paper_ir.references = grobid.references
        else:
            paper_ir.parse_report.warnings.append("using_pymupdf_fallback_references")
        paper_ir.citations = grobid.citations

    def _merge_marker(self, paper_ir: PaperIR, marker: MarkerParseOutput | None) -> None:
        if marker is None:
            paper_ir.parse_report.warnings.append("marker_unavailable")
            return

        paper_ir.parse_report.warnings.extend(marker.warnings)
        if _has_unavailable_warning(marker.warnings):
            return

        if marker.blocks:
            self._add_source(paper_ir.parse_report, ParserSource.MARKER)
            self._replace_or_append_marker_blocks(paper_ir, marker.blocks)
        paper_ir.assets.tables.extend(marker.tables)
        paper_ir.assets.figures.extend(marker.figures)
        paper_ir.assets.images.extend(marker.images)

    def _merge_pdffigures2(
        self,
        paper_ir: PaperIR,
        pdffigures2: Pdffigures2ParseOutput | None,
    ) -> None:
        if pdffigures2 is None:
            paper_ir.parse_report.warnings.append("pdffigures2_unavailable")
            return

        paper_ir.parse_report.warnings.extend(pdffigures2.warnings)
        if _has_unavailable_warning(pdffigures2.warnings):
            return

        if pdffigures2.figures or pdffigures2.tables:
            self._add_source(paper_ir.parse_report, ParserSource.PDFFIGURES2)
        for figure in pdffigures2.figures:
            existing = [item.caption for item in paper_ir.assets.figures]
            if not _caption_exists(figure.caption, existing):
                paper_ir.assets.figures.append(figure)
        for table in pdffigures2.tables:
            existing = [item.caption for item in paper_ir.assets.tables]
            if not _caption_exists(table.caption, existing):
                paper_ir.assets.tables.append(table)

    def _replace_sections(self, paper_ir: PaperIR, grobid_sections: list[SectionNode]) -> None:
        old_sections = paper_ir.sections
        old_blocks = list(paper_ir.blocks)
        new_sections = [section.model_copy(update={"block_ids": []}) for section in grobid_sections]
        paper_ir.sections = new_sections

        for block in old_blocks:
            target = self._best_section_for_block(block, old_sections, new_sections)
            block.section_id = target.section_id
            target.block_ids.append(block.block_id)
        for table in paper_ir.assets.tables:
            table.section_id = self._remapped_artifact_section_id(
                table.section_id,
                old_sections,
                new_sections,
            )
        for figure in paper_ir.assets.figures:
            figure.section_id = self._remapped_artifact_section_id(
                figure.section_id,
                old_sections,
                new_sections,
            )

    def _replace_or_append_marker_blocks(
        self,
        paper_ir: PaperIR,
        marker_blocks: list[PaperBlock],
    ) -> None:
        if not paper_ir.sections:
            return
        fallback_block_ids = {
            block.block_id
            for block in paper_ir.blocks
            if block.source_parser == ParserSource.PYMUPDF
        }
        if fallback_block_ids:
            paper_ir.blocks = [
                block for block in paper_ir.blocks if block.block_id not in fallback_block_ids
            ]
            for section in paper_ir.sections:
                section.block_ids = [
                    block_id for block_id in section.block_ids if block_id not in fallback_block_ids
                ]

        current_section: SectionNode | None = None
        assigned_count = 0
        pending_blocks: list[PaperBlock] = []
        for block in marker_blocks:
            if block.block_type.value == "heading":
                match = _find_section_by_title(paper_ir.sections, block.text)
                if match is not None:
                    current_section = match
                elif self._is_missing_top_level_section(block.text, paper_ir):
                    current_section = self._insert_marker_section(
                        paper_ir,
                        block.text,
                        after_section=current_section,
                    )
                continue
            if self._should_skip_front_matter_block(block, paper_ir):
                continue
            if current_section is None:
                pending_blocks.append(block)
                continue
            block.section_id = current_section.section_id
            paper_ir.blocks.append(block)
            current_section.block_ids.append(block.block_id)
            assigned_count += 1

        if assigned_count == 0 and pending_blocks:
            fallback_section = paper_ir.sections[0]
            for block in pending_blocks:
                block.section_id = fallback_section.section_id
                paper_ir.blocks.append(block)
                fallback_section.block_ids.append(block.block_id)

    def _is_missing_top_level_section(self, title: str, paper_ir: PaperIR) -> bool:
        normalized = _normalize_title(title)
        if not normalized or normalized == "references":
            return False
        if paper_ir.metadata.title and normalized == _normalize_title(paper_ir.metadata.title):
            return False
        if normalized in {"require", "requires"}:
            return False
        return re.match(r"^[IVX]+\.\s+\S+", title.strip()) is not None

    def _insert_marker_section(
        self,
        paper_ir: PaperIR,
        title: str,
        *,
        after_section: SectionNode | None,
    ) -> SectionNode:
        section = SectionNode(
            section_id=new_id("sec"),
            title=title,
            normalized_title=_normalize_title(title),
            level=1,
            source=ParserSource.MARKER,
            confidence=0.75,
        )
        if after_section is None:
            paper_ir.sections.append(section)
            return section
        for index, existing in enumerate(paper_ir.sections):
            if existing.section_id == after_section.section_id:
                paper_ir.sections.insert(index + 1, section)
                return section
        paper_ir.sections.append(section)
        return section

    def _should_skip_front_matter_block(self, block: PaperBlock, paper_ir: PaperIR) -> bool:
        text = " ".join(block.text.split()).lower()
        if not text:
            return True
        if paper_ir.abstract and text.startswith("abstract"):
            return True
        if text.startswith("index terms") or text.startswith("keywords"):
            return True
        if text.startswith("received ") or "digital object identifier" in text:
            return True
        if text.startswith("the authors are with"):
            return True
        return "all rights reserved" in text and "ieee" in text

    def _best_section_for_block(
        self,
        block: PaperBlock,
        old_sections: list[SectionNode],
        new_sections: list[SectionNode],
    ) -> SectionNode:
        old_section = next(
            (section for section in old_sections if section.section_id == block.section_id),
            None,
        )
        if old_section is not None:
            match = _find_section_by_title(new_sections, old_section.title)
            if match is not None:
                return match
        return new_sections[0]

    def _remapped_artifact_section_id(
        self,
        section_id: str | None,
        old_sections: list[SectionNode],
        new_sections: list[SectionNode],
    ) -> str | None:
        if section_id is None:
            return None
        old_section = next(
            (section for section in old_sections if section.section_id == section_id),
            None,
        )
        if old_section is None:
            return None
        match = _find_section_by_title(new_sections, old_section.title)
        return match.section_id if match is not None else None

    def _merged_metadata(self, current: PaperMetadata, candidate: PaperMetadata) -> PaperMetadata:
        return PaperMetadata(
            title=candidate.title or current.title,
            authors=candidate.authors or current.authors,
            affiliations=candidate.affiliations or current.affiliations,
            keywords=candidate.keywords or current.keywords,
            venue=candidate.venue or current.venue,
            year=candidate.year or current.year,
            doi=candidate.doi or current.doi,
        )

    def _refresh_report(self, paper_ir: PaperIR, parser_profile: ParserProfile) -> None:
        report = paper_ir.parse_report
        report.parser_profile = parser_profile
        report.section_coverage = 1.0 if paper_ir.sections else 0.0
        report.reference_coverage = 1.0 if paper_ir.references else 0.0
        report.table_confidence = _average([table.confidence for table in paper_ir.assets.tables])
        report.figure_caption_alignment_confidence = _average(
            [figure.caption_confidence for figure in paper_ir.assets.figures]
        )
        report.equation_confidence = _average(
            [equation.confidence for equation in paper_ir.assets.equations]
        )

    def _add_source(self, report: ParseReport, source: ParserSource) -> None:
        if source not in report.parser_sources:
            report.parser_sources.append(source)


def _find_section_by_title(
    sections: list[SectionNode],
    title: str,
) -> SectionNode | None:
    normalized = _normalize_title(title)
    for section in sections:
        section_normalized = _normalize_title(section.title or section.normalized_title)
        if section_normalized == normalized:
            return section
    for section in sections:
        section_normalized = _normalize_title(section.title or section.normalized_title)
        if section_normalized in normalized or normalized in section_normalized:
            return section
    return None


def _first_section_id(sections: list[SectionNode]) -> str | None:
    return sections[0].section_id if sections else None


def _has_unavailable_warning(warnings: list[str]) -> bool:
    return any(
        warning.startswith(("grobid_unavailable", "marker_unavailable", "pdffigures2_unavailable"))
        or warning.endswith("_disabled")
        for warning in warnings
    )


def _caption_exists(caption: str | None, existing_captions: list[str | None]) -> bool:
    if not caption:
        return False
    normalized = _normalize_title(caption)
    return any(_normalize_title(existing or "") == normalized for existing in existing_captions)


def _normalize_title(title: str) -> str:
    normalized = re.sub(r"^#+\s*", "", title.strip().lower())
    normalized = (
        normalized.replace("ﬀ", "ff")
        .replace("ﬁ", "fi")
        .replace("ﬂ", "fl")
        .replace("ﬃ", "ffi")
        .replace("ﬄ", "ffl")
    )
    normalized = re.sub(r"\b([a-z])\s+(ffi|ffl|ff|fi|fl)\s+([a-z])", r"\1\2\3", normalized)
    normalized = re.sub(r"^\d+(\.\d+)*\s+", "", normalized)
    normalized = re.sub(r"^[ivxlcdm]+\.\s+", "", normalized)
    normalized = re.sub(r"^[a-z]\.\s+", "", normalized)
    normalized = re.sub(r"^\d+\)\s+", "", normalized)
    return re.sub(r"\s+", " ", normalized)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
