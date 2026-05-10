import json
import re
import shutil
import subprocess
from html import unescape
from pathlib import Path
from typing import Any

from app.core.ids import new_id
from app.core.models import (
    PaperBlock,
    PaperBlockType,
    ParserProvenance,
    ParserSource,
)
from app.parsing.candidates import MarkerParseOutput


class MarkerAdapter:
    def __init__(
        self,
        *,
        enabled: bool,
        output_format: str,
        timeout_seconds: float = 120.0,
        disable_image_extraction: bool = True,
        low_memory_mode: bool = True,
    ) -> None:
        self.enabled = enabled
        self.output_format = output_format
        self.timeout_seconds = timeout_seconds
        self.disable_image_extraction = disable_image_extraction
        self.low_memory_mode = low_memory_mode

    def parse(
        self,
        pdf_path: Path,
        output_dir: Path,
        *,
        page_limit: int | None = None,
    ) -> MarkerParseOutput:
        if not self.enabled:
            return MarkerParseOutput(warnings=["marker_disabled"])
        cli_output = self._run_cli(pdf_path, output_dir, page_limit=page_limit)
        if cli_output is not None:
            return cli_output
        return MarkerParseOutput(warnings=["marker_unavailable"])

    def parse_json_payload(self, payload: dict[str, object]) -> MarkerParseOutput:
        markdown = self._extract_markdown(payload)
        blocks = self._blocks_from_payload(payload, markdown)
        return MarkerParseOutput(markdown=markdown, blocks=blocks)

    def _run_cli(
        self,
        pdf_path: Path,
        output_dir: Path,
        *,
        page_limit: int | None,
    ) -> MarkerParseOutput | None:
        executable = shutil.which("marker_single")
        if executable is None:
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            executable,
            str(pdf_path),
            "--output_dir",
            str(output_dir),
            "--output_format",
            self.output_format,
            "--disable_ocr",
            "--disable_tqdm",
        ]
        if self.disable_image_extraction:
            command.append("--disable_image_extraction")
        if self.low_memory_mode:
            command.extend(
                [
                    "--disable_multiprocessing",
                    "--layout_batch_size",
                    "1",
                    "--detection_batch_size",
                    "1",
                    "--ocr_error_batch_size",
                    "1",
                    "--recognition_batch_size",
                    "1",
                    "--equation_batch_size",
                    "1",
                    "--table_rec_batch_size",
                    "1",
                ]
            )
        if page_limit is not None and page_limit > 0:
            command.extend(["--page_range", f"0-{page_limit - 1}"])
        stdout_path = output_dir / "marker.stdout.log"
        stderr_path = output_dir / "marker.stderr.log"
        try:
            with (
                stdout_path.open("w", encoding="utf-8") as stdout,
                stderr_path.open(
                    "w",
                    encoding="utf-8",
                ) as stderr,
            ):
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    timeout=self.timeout_seconds,
                )
        except subprocess.TimeoutExpired:
            return MarkerParseOutput(warnings=[f"marker_timeout:{self.timeout_seconds}s"])
        except Exception as exc:
            return MarkerParseOutput(warnings=[f"marker_failed:{type(exc).__name__}:{exc}"])

        diagnostics = self._truncate(self._read_diagnostics(stderr_path, stdout_path))
        if completed.returncode != 0:
            if completed.returncode == 137:
                return MarkerParseOutput(warnings=["marker_failed:out_of_memory_or_killed"])
            if completed.returncode == 143:
                return MarkerParseOutput(warnings=["marker_failed:terminated"])
            if completed.returncode < 0:
                return MarkerParseOutput(warnings=[f"marker_failed:signal:{-completed.returncode}"])
            return MarkerParseOutput(warnings=[f"marker_failed:{diagnostics}"])

        json_files = sorted(output_dir.rglob("*.json"))
        markdown_files = sorted(output_dir.rglob("*.md"))
        if not json_files and not markdown_files:
            return MarkerParseOutput(warnings=["marker_no_output"])
        try:
            return self._parse_outputs(json_files=json_files, markdown_files=markdown_files)
        except Exception as exc:
            return MarkerParseOutput(
                warnings=[f"marker_output_parse_failed:{type(exc).__name__}:{exc}"]
            )

    def _parse_outputs(
        self,
        *,
        json_files: list[Path],
        markdown_files: list[Path],
    ) -> MarkerParseOutput:
        if json_files:
            payload = json.loads(json_files[0].read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                output = self.parse_json_payload(payload)
                output.warnings.append("marker_connected")
                return output
        if markdown_files:
            markdown = markdown_files[0].read_text(encoding="utf-8")
            return MarkerParseOutput(
                markdown=markdown,
                blocks=self._blocks_from_markdown(markdown),
                warnings=["marker_connected"],
            )
        return MarkerParseOutput(warnings=["marker_no_output"])

    def _truncate(self, value: str, *, limit: int = 600) -> str:
        if len(value) <= limit:
            return value
        return f"{value[:limit]}..."

    def _read_diagnostics(self, stderr_path: Path, stdout_path: Path) -> str:
        for path in (stderr_path, stdout_path):
            if path.exists():
                value = path.read_text(encoding="utf-8", errors="replace").strip()
                if value:
                    return value
        return ""

    def _extract_markdown(self, payload: dict[str, object]) -> str | None:
        for key in ("markdown", "text", "html"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _blocks_from_payload(
        self,
        payload: dict[str, object],
        markdown: str | None,
    ) -> list[PaperBlock]:
        blocks = self._flatten_blocks(payload)
        if blocks:
            return blocks
        return self._blocks_from_markdown(markdown or "")

    def _flatten_blocks(self, node: dict[str, Any]) -> list[PaperBlock]:
        blocks: list[PaperBlock] = []
        block_type = str(node.get("block_type") or "")
        if self._is_content_block(block_type):
            text = self._child_text(node)
            if text:
                blocks.append(self._block(text, block_type))

        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    blocks.extend(self._flatten_blocks(child))
        return blocks

    def _is_content_block(self, block_type: str) -> bool:
        normalized = block_type.lower()
        if normalized in {"document", "page", "pageheader", "pagefooter"}:
            return False
        if normalized in {"text", "sectionheader", "listgroup", "table", "equation", "code"}:
            return True
        return any(
            token in normalized
            for token in ("text", "section", "list", "table", "equation", "caption")
        )

    def _child_text(self, child: dict[str, Any]) -> str | None:
        for key in ("text", "markdown"):
            value = child.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_text(value)
        html = child.get("html")
        if isinstance(html, str) and html.strip():
            return self._html_to_text(html)
        return None

    def _html_to_text(self, value: str) -> str | None:
        value = re.sub(r"<content-ref\b[^>]*>\s*</content-ref>", " ", value)
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", " ", value)
        return self._normalize_text(unescape(value))

    def _normalize_text(self, value: str) -> str | None:
        text = re.sub(r"[ \t\r\f\v]+", " ", value)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = text.strip()
        if not text or text.startswith("<content-ref"):
            return None
        return text

    def _blocks_from_markdown(self, markdown: str) -> list[PaperBlock]:
        blocks = []
        for paragraph in [part.strip() for part in markdown.split("\n\n") if part.strip()]:
            block_type = "heading" if paragraph.startswith("#") else "paragraph"
            blocks.append(self._block(paragraph, block_type))
        return blocks

    def _block(self, text: str, block_type: object) -> PaperBlock:
        normalized_type = str(block_type or "").lower()
        paper_block_type = (
            PaperBlockType.HEADING
            if "heading" in normalized_type or "section" in normalized_type
            else PaperBlockType.PARAGRAPH
        )
        return PaperBlock(
            block_id=new_id("block"),
            block_type=paper_block_type,
            text=text,
            markdown=text,
            source_parser=ParserSource.MARKER,
            confidence=0.7,
            provenance=ParserProvenance(
                source_parser=ParserSource.MARKER,
                confidence=0.7,
            ),
        )
