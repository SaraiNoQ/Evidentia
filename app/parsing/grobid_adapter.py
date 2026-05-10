from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from app.core.ids import new_id
from app.core.models import (
    CitationContext,
    PaperMetadata,
    ParserSource,
    ReferenceRecord,
    SectionNode,
)
from app.parsing.candidates import GrobidParseOutput

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


class GrobidClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def process_fulltext_document(self, pdf_path: Path) -> str:
        url = f"{self.base_url}/api/processFulltextDocument"
        with pdf_path.open("rb") as pdf_file:
            files = {"input": (pdf_path.name, pdf_file, "application/pdf")}
            data = {
                "consolidateHeader": "0",
                "consolidateCitations": "0",
                "includeRawCitations": "1",
            }
            response = httpx.post(url, files=files, data=data, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.text


class GrobidTeiParser:
    def parse(self, tei_xml: str) -> GrobidParseOutput:
        try:
            root = ET.fromstring(tei_xml)
        except ET.ParseError as exc:
            return GrobidParseOutput(warnings=[f"grobid_tei_parse_failed:{exc}"])

        metadata = PaperMetadata(
            title=self._first_non_empty_text(
                root,
                [
                    ".//tei:titleStmt/tei:title",
                    ".//tei:sourceDesc//tei:analytic/tei:title",
                    ".//tei:sourceDesc//tei:monogr/tei:title",
                ],
            ),
            authors=self._authors(root),
            affiliations=self._affiliations(root),
            keywords=self._keywords(root),
            doi=self._first_text(root, ".//tei:idno[@type='DOI']"),
        )
        abstract = self._joined_text(root, ".//tei:profileDesc/tei:abstract")
        if not abstract:
            abstract = self._abstract_from_body(root)
        sections = self._sections(root)
        references = self._references(root)
        citations = self._citations(root, references)
        return GrobidParseOutput(
            metadata=metadata,
            abstract=abstract,
            sections=sections,
            references=references,
            citations=citations,
        )

    def _sections(self, root: ET.Element) -> list[SectionNode]:
        sections: list[SectionNode] = []
        for div in root.findall(".//tei:text/tei:body//tei:div", TEI_NS):
            head = div.find("tei:head", TEI_NS)
            title = self._element_text(head)
            if not title:
                continue
            if self._should_skip_section_title(title):
                continue
            section = SectionNode(
                section_id=new_id("sec"),
                title=title,
                normalized_title=self._normalize_title(title),
                level=self._level(div),
                source=ParserSource.GROBID,
                confidence=0.85,
            )
            sections.append(section)
        return sections

    def _references(self, root: ET.Element) -> list[ReferenceRecord]:
        references: list[ReferenceRecord] = []
        bibl_structs = root.findall(".//tei:listBibl/tei:biblStruct", TEI_NS)
        for index, bibl in enumerate(bibl_structs, start=1):
            raw = self._element_text(bibl) or f"Reference {index}"
            title = self._first_text(bibl, ".//tei:title")
            authors = [
                author
                for author in (
                    self._element_text(author_el)
                    for author_el in bibl.findall(".//tei:author", TEI_NS)
                )
                if author
            ]
            year = self._year(bibl)
            doi = self._first_text(bibl, ".//tei:idno[@type='DOI']")
            references.append(
                ReferenceRecord(
                    bib_id=new_id("bib"),
                    raw=raw,
                    title=title,
                    authors=authors,
                    year=year,
                    doi=doi,
                    citation_markers=[f"[{index}]"],
                )
            )
        return references

    def _citations(
        self,
        root: ET.Element,
        references: list[ReferenceRecord],
    ) -> list[CitationContext]:
        citations: list[CitationContext] = []
        reference_by_index = {
            str(index): reference for index, reference in enumerate(references, start=1)
        }
        for ref in root.findall(".//tei:ref[@type='bibr']", TEI_NS):
            marker = self._element_text(ref)
            target = (ref.attrib.get("target") or "").lstrip("#b")
            reference = reference_by_index.get(target)
            if marker:
                citations.append(
                    CitationContext(
                        citation_id=new_id("citation"),
                        marker=marker,
                        bib_id=reference.bib_id if reference else None,
                        context=marker,
                        source_parser=ParserSource.GROBID,
                        confidence=0.75 if reference else 0.5,
                    )
                )
        return citations

    def _authors(self, root: ET.Element) -> list[str]:
        return [
            text
            for text in (
                self._element_text(author)
                for author in root.findall(".//tei:titleStmt//tei:author", TEI_NS)
            )
            if text
        ]

    def _affiliations(self, root: ET.Element) -> list[str]:
        return [
            text
            for text in (
                self._element_text(affiliation)
                for affiliation in root.findall(".//tei:affiliation", TEI_NS)
            )
            if text
        ]

    def _keywords(self, root: ET.Element) -> list[str]:
        return [
            text
            for text in (
                self._element_text(term)
                for term in root.findall(".//tei:keywords//tei:term", TEI_NS)
            )
            if text
        ]

    def _should_skip_section_title(self, title: str) -> bool:
        normalized = " ".join(title.split())
        return len(normalized) <= 2

    def _year(self, element: ET.Element) -> int | None:
        for date in element.findall(".//tei:date", TEI_NS):
            value = date.attrib.get("when") or date.attrib.get("notBefore")
            if value and len(value) >= 4 and value[:4].isdigit():
                return int(value[:4])
        return None

    def _level(self, div: ET.Element) -> int:
        number = div.attrib.get("n") or ""
        if number:
            return number.count(".") + 1
        return 1

    def _first_text(self, root: ET.Element, path: str) -> str | None:
        return self._element_text(root.find(path, TEI_NS))

    def _first_non_empty_text(self, root: ET.Element, paths: list[str]) -> str | None:
        for path in paths:
            text = self._first_text(root, path)
            if text:
                return text
        return None

    def _joined_text(self, root: ET.Element, path: str) -> str | None:
        element = root.find(path, TEI_NS)
        return self._element_text(element)

    def _abstract_from_body(self, root: ET.Element) -> str | None:
        for paragraph in root.findall(".//tei:text/tei:body//tei:p", TEI_NS):
            text = self._element_text(paragraph)
            if not text:
                continue
            normalized = text.strip()
            lowered = normalized.lower()
            if lowered.startswith("abstract"):
                abstract = (
                    normalized.removeprefix("Abstract")
                    .removeprefix("ABSTRACT")
                    .lstrip(":-—– ")
                    .strip()
                    or normalized
                )
                abstract = abstract.split("Index Terms")[0].strip()
                abstract = abstract.split("Index terms")[0].strip()
                return abstract
        return None

    def _element_text(self, element: ET.Element | None) -> str | None:
        if element is None:
            return None
        text = " ".join(part.strip() for part in element.itertext() if part.strip())
        return text or None

    def _normalize_title(self, title: str) -> str:
        return " ".join(title.lower().split())


class GrobidAdapter:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self.client = GrobidClient(base_url=base_url, timeout_seconds=timeout_seconds)
        self.parser = GrobidTeiParser()

    def parse(self, pdf_path: Path) -> GrobidParseOutput:
        try:
            tei = self.client.process_fulltext_document(pdf_path)
        except Exception as exc:
            return GrobidParseOutput(warnings=[f"grobid_unavailable:{exc}"])
        output = self.parser.parse(tei)
        output.warnings.append("grobid_connected")
        return output
