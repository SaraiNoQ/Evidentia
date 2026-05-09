from abc import ABC, abstractmethod
from pathlib import Path

from app.core.models import JobConfig, ParseResult


class ParserProvider(ABC):
    name: str

    @abstractmethod
    def parse(self, pdf_path: Path, *, job_id: str, config: JobConfig) -> ParseResult:
        raise NotImplementedError
