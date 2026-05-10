from pathlib import Path

from app.core.config import get_settings
from app.core.models import JobConfig, ParseResult, ParserProfile, ReviewMode
from app.parsing.base import ParserProvider
from app.parsing.fusion import PaperIRFusionEngine
from app.parsing.grobid_adapter import GrobidAdapter
from app.parsing.marker_adapter import MarkerAdapter
from app.parsing.pdffigures2_adapter import Pdffigures2Adapter
from app.parsing.pymupdf_parser import PyMuPDFParser


class PaperIREnsembleParser(ParserProvider):
    """Research-default parser profile entry point.

    The parser keeps PyMuPDF as preflight/fallback while opportunistically using
    GROBID, Marker and pdffigures2 when those local dependencies are available.
    """

    name = "paper_ir_ensemble"

    def parse(self, pdf_path: Path, *, job_id: str, config: JobConfig) -> ParseResult:
        settings = get_settings()
        result = PyMuPDFParser().parse(pdf_path, job_id=job_id, config=config)

        assets_dir = pdf_path.parent / settings.parser_assets_dir / job_id
        grobid_output = GrobidAdapter(
            base_url=settings.grobid_base_url,
            timeout_seconds=settings.grobid_timeout_seconds,
        ).parse(pdf_path)
        marker_enabled = (
            settings.marker_enabled and config.parser_profile != ParserProfile.COMMERCIAL_SAFE
        )
        marker_page_limit = self._marker_page_limit(
            config,
            page_count=result.paper_document.page_count,
        )
        if marker_page_limit is not None and marker_page_limit < result.paper_document.page_count:
            result.warnings.append(
                f"marker_partial_page_parse:{marker_page_limit}/{result.paper_document.page_count}"
            )
        marker_output = MarkerAdapter(
            enabled=marker_enabled,
            output_format=settings.marker_output_format,
            timeout_seconds=settings.marker_timeout_seconds,
            disable_image_extraction=settings.marker_disable_image_extraction,
            low_memory_mode=settings.marker_low_memory_mode,
        ).parse(
            pdf_path,
            assets_dir / "marker",
            page_limit=marker_page_limit,
        )
        pdffigures2_output = Pdffigures2Adapter(
            enabled=settings.pdffigures2_enabled,
            command=settings.pdffigures2_command,
        ).parse(pdf_path, assets_dir / "pdffigures2")

        if config.parser_profile == ParserProfile.COMMERCIAL_SAFE:
            result.warnings.append("commercial_safe_docling_not_connected_yet")
        if config.parser_profile == ParserProfile.HARD_CASE:
            result.warnings.extend(
                [
                    "hard_case_docling_not_connected_yet",
                    "hard_case_camelot_not_connected_yet",
                    "hard_case_mineru_not_connected_yet",
                ]
            )

        paper_ir = PaperIRFusionEngine().fuse(
            fallback_document=result.paper_document,
            parser_profile=config.parser_profile,
            grobid=grobid_output,
            marker=marker_output,
            pdffigures2=pdffigures2_output,
        )
        for warning in result.warnings:
            if warning not in paper_ir.parse_report.warnings:
                paper_ir.parse_report.warnings.append(warning)
        result.paper_ir = paper_ir
        result.warnings = paper_ir.parse_report.warnings
        result.provider = self.name
        return result

    def _marker_page_limit(self, config: JobConfig, *, page_count: int) -> int | None:
        if config.max_pages is not None:
            return min(config.max_pages, page_count)
        settings = get_settings()
        if config.review_mode == ReviewMode.QUICK_AUDIT:
            if settings.marker_quick_page_limit is None:
                return None
            return min(settings.marker_quick_page_limit, page_count)
        return None
