from pathlib import Path

from app.core.models import JobConfig, ParseResult
from app.parsing.base import ParserProvider


class MinerUParser(ParserProvider):
    name = "mineru"

    def parse(self, pdf_path: Path, *, job_id: str, config: JobConfig) -> ParseResult:
        raise NotImplementedError("MinerU adapter is reserved for Phase 0 parser hardening.")
