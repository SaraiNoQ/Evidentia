from pathlib import Path

from app.core.models import JobConfig, ParseResult
from app.parsing.base import ParserProvider


class GrobidReferenceParser(ParserProvider):
    name = "grobid"

    def parse(self, pdf_path: Path, *, job_id: str, config: JobConfig) -> ParseResult:
        raise NotImplementedError("GROBID adapter is reserved for metadata/reference enrichment.")
