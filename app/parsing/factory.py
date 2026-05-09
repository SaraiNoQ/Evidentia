from app.parsing.base import ParserProvider
from app.parsing.grobid import GrobidReferenceParser
from app.parsing.mineru import MinerUParser
from app.parsing.pymupdf_parser import PyMuPDFParser


def get_parser(provider: str) -> ParserProvider:
    normalized = provider.lower()
    if normalized == "pymupdf":
        return PyMuPDFParser()
    if normalized == "mineru":
        return MinerUParser()
    if normalized == "grobid":
        return GrobidReferenceParser()
    raise ValueError(f"unsupported parser provider: {provider}")
