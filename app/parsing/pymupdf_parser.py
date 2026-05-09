from __future__ import annotations

import re
from pathlib import Path

import fitz

from app.core.ids import new_id
from app.core.models import (
    ArtifactType,
    CharSpan,
    Equation,
    Figure,
    JobConfig,
    PaperArtifact,
    PaperChunk,
    PaperDocument,
    ParseResult,
    Reference,
    Table,
)
from app.parsing.base import ParserProvider

SECTION_RE = re.compile(
    r"^(abstract|introduction|background|related work|method|methodology|approach|experiments?"
    r"|evaluation|results|discussion|limitations|conclusion|references|appendix|"
    r"\d+(\.\d+)*\s+[A-Z][A-Za-z0-9 ,:/()\-]{2,})$",
    re.IGNORECASE,
)
TABLE_RE = re.compile(r"^table\s+\d+[:.\s-]", re.IGNORECASE)
FIGURE_RE = re.compile(r"^(figure|fig\.)\s+\d+[:.\s-]", re.IGNORECASE)
EQUATION_RE = re.compile(r"^(equation|eq\.)\s+\d+[:.\s-]", re.IGNORECASE)


class PyMuPDFParser(ParserProvider):
    name = "pymupdf"

    def parse(self, pdf_path: Path, *, job_id: str, config: JobConfig) -> ParseResult:
        warnings: list[str] = []
        paper_id = new_id("paper")
        chunks: list[PaperChunk] = []
        tables: list[Table] = []
        figures: list[Figure] = []
        equations: list[Equation] = []
        references: list[Reference] = []
        sections: list[str] = []
        current_section = "Unknown"

        try:
            document = fitz.open(pdf_path)
        except Exception as exc:  # pragma: no cover - covered through API failure path
            raise ValueError(f"failed to open PDF: {exc}") from exc

        page_count = document.page_count
        max_pages = min(page_count, config.max_pages) if config.max_pages else page_count
        if page_count == 0:
            warnings.append("pdf_has_no_pages")

        metadata_title = (document.metadata or {}).get("title") or None

        for page_index in range(max_pages):
            page = document.load_page(page_index)
            page_number = page_index + 1
            text = page.get_text("text")
            if not text.strip():
                warnings.append(f"page_{page_number}_has_no_extractable_text")
                continue
            if len(text.strip()) < 100:
                warnings.append(f"page_{page_number}_has_low_text_density")

            current_section = self._extract_chunks_for_page(
                text=text,
                page_number=page_number,
                paper_id=paper_id,
                current_section=current_section,
                sections=sections,
                chunks=chunks,
            )
            self._extract_artifacts(
                text=text,
                page_number=page_number,
                paper_id=paper_id,
                section=current_section,
                tables=tables,
                figures=figures,
                equations=equations,
            )

        references.extend(
            self._extract_references(
                chunks=chunks,
                paper_id=paper_id,
            )
        )

        if not chunks:
            warnings.append("no_chunks_extracted")
        if not references:
            warnings.append("references_not_detected")

        parse_confidence = self._confidence(
            page_count=page_count,
            parsed_pages=max_pages,
            chunks=chunks,
            warnings=warnings,
        )
        paper = PaperDocument(
            paper_id=paper_id,
            job_id=job_id,
            title=metadata_title,
            page_count=page_count,
            sections=sections,
            chunks=chunks,
            tables=tables,
            figures=figures,
            equations=equations,
            references=references,
            parse_confidence=parse_confidence,
            warnings=warnings,
        )
        artifacts: dict[str, list[PaperArtifact]] = {
            ArtifactType.TABLE.value: list(tables),
            ArtifactType.FIGURE.value: list(figures),
            ArtifactType.EQUATION.value: list(equations),
        }
        return ParseResult(
            paper_document=paper,
            artifacts=artifacts,
            references=references,
            parse_confidence=parse_confidence,
            warnings=warnings,
            provider=self.name,
        )

    def _extract_chunks_for_page(
        self,
        *,
        text: str,
        page_number: int,
        paper_id: str,
        current_section: str,
        sections: list[str],
        chunks: list[PaperChunk],
    ) -> str:
        buffer: list[str] = []

        def flush_buffer() -> None:
            if not buffer:
                return
            paragraph = "\n".join(buffer).strip()
            buffer.clear()
            if not paragraph:
                return
            start = text.find(paragraph)
            end = start + len(paragraph) if start >= 0 else start
            chunks.append(
                PaperChunk(
                    chunk_id=new_id("chunk"),
                    paper_id=paper_id,
                    section_title=current_section,
                    text=paragraph,
                    page_start=page_number,
                    page_end=page_number,
                    char_span=CharSpan(start=max(start, 0), end=max(end, 0)),
                    confidence=0.75 if current_section == "Unknown" else 0.9,
                )
            )

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                flush_buffer()
                continue
            if self._looks_like_section(line):
                flush_buffer()
                current_section = self._normalize_section(line)
                if current_section not in sections:
                    sections.append(current_section)
                continue
            buffer.append(line)
        flush_buffer()
        return current_section

    def _extract_artifacts(
        self,
        *,
        text: str,
        page_number: int,
        paper_id: str,
        section: str,
        tables: list[Table],
        figures: list[Figure],
        equations: list[Equation],
    ) -> None:
        for line in (line.strip() for line in text.splitlines() if line.strip()):
            if TABLE_RE.match(line):
                tables.append(
                    Table(
                        artifact_id=new_id("artifact"),
                        paper_id=paper_id,
                        label=line.split(":", 1)[0][:80],
                        caption=line,
                        page=page_number,
                        section=section,
                        confidence=0.55,
                    )
                )
            elif FIGURE_RE.match(line):
                figures.append(
                    Figure(
                        artifact_id=new_id("artifact"),
                        paper_id=paper_id,
                        label=line.split(":", 1)[0][:80],
                        caption=line,
                        page=page_number,
                        section=section,
                        confidence=0.55,
                    )
                )
            elif EQUATION_RE.match(line):
                equations.append(
                    Equation(
                        artifact_id=new_id("artifact"),
                        paper_id=paper_id,
                        label=line.split(":", 1)[0][:80],
                        caption=line,
                        page=page_number,
                        section=section,
                        confidence=0.45,
                    )
                )

    def _extract_references(self, *, chunks: list[PaperChunk], paper_id: str) -> list[Reference]:
        references: list[Reference] = []
        in_references = False
        for chunk in chunks:
            if chunk.section_title.lower().startswith("references"):
                in_references = True
            if not in_references:
                continue
            for raw_reference in self._split_reference_text(chunk.text):
                references.append(
                    Reference(
                        reference_id=new_id("ref"),
                        paper_id=paper_id,
                        raw_text=raw_reference,
                    )
                )
        return references

    def _split_reference_text(self, text: str) -> list[str]:
        candidates = re.split(r"\n(?=\[\d+\]|\d+\.\s|[A-Z][A-Za-z-]+,\s)", text)
        return [candidate.strip() for candidate in candidates if len(candidate.strip()) > 20]

    def _looks_like_section(self, line: str) -> bool:
        if len(line) > 90:
            return False
        return bool(SECTION_RE.match(line.strip()))

    def _normalize_section(self, line: str) -> str:
        normalized = re.sub(r"\s+", " ", line.strip())
        return normalized[:120]

    def _confidence(
        self,
        *,
        page_count: int,
        parsed_pages: int,
        chunks: list[PaperChunk],
        warnings: list[str],
    ) -> float:
        if page_count == 0 or not chunks:
            return 0.0
        coverage = parsed_pages / page_count
        warning_penalty = min(0.5, len(warnings) * 0.04)
        return max(0.1, min(1.0, coverage - warning_penalty))
