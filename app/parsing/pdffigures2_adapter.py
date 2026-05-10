import json
import shutil
import subprocess
from pathlib import Path

from app.core.ids import new_id
from app.core.models import FigureArtifactV2, ParserSource, TableArtifactV2
from app.parsing.candidates import Pdffigures2ParseOutput


class Pdffigures2Adapter:
    def __init__(self, *, enabled: bool, command: str) -> None:
        self.enabled = enabled
        self.command = command

    def parse(self, pdf_path: Path, output_dir: Path) -> Pdffigures2ParseOutput:
        if not self.enabled:
            return Pdffigures2ParseOutput(warnings=["pdffigures2_disabled"])
        executable = shutil.which(self.command)
        if executable is None:
            return Pdffigures2ParseOutput(warnings=["pdffigures2_unavailable"])
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "pdffigures2.json"
        command = [executable, str(pdf_path), "-m", str(json_path), "-d", str(output_dir)]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except Exception as exc:
            return Pdffigures2ParseOutput(warnings=[f"pdffigures2_failed:{exc}"])
        if completed.returncode != 0:
            return Pdffigures2ParseOutput(
                warnings=[f"pdffigures2_failed:{completed.stderr.strip()}"]
            )
        if not json_path.exists():
            return Pdffigures2ParseOutput(warnings=["pdffigures2_no_output"])
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return Pdffigures2ParseOutput(warnings=["pdffigures2_invalid_output"])
        output = self.parse_json_payload(payload, output_dir)
        output.warnings.append("pdffigures2_connected")
        return output

    def parse_json_payload(
        self,
        payload: list[object],
        output_dir: Path | None = None,
    ) -> Pdffigures2ParseOutput:
        figures: list[FigureArtifactV2] = []
        tables: list[TableArtifactV2] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            caption = self._string(item.get("caption"))
            label = self._string(item.get("name")) or self._string(item.get("figType"))
            item_type = (self._string(item.get("figType")) or "Figure").lower()
            image_path = self._image_path(item, output_dir)
            if "table" in item_type:
                tables.append(
                    TableArtifactV2(
                        table_id=new_id("table"),
                        label=label,
                        caption=caption,
                        source_parser=ParserSource.PDFFIGURES2,
                        confidence=0.8 if caption else 0.55,
                    )
                )
            else:
                figures.append(
                    FigureArtifactV2(
                        figure_id=new_id("figure"),
                        label=label,
                        caption=caption,
                        image_path=image_path,
                        source_parser=ParserSource.PDFFIGURES2,
                        caption_confidence=0.8 if caption else 0.55,
                    )
                )
        return Pdffigures2ParseOutput(figures=figures, tables=tables)

    def _string(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _image_path(self, item: dict[object, object], output_dir: Path | None) -> str | None:
        render_url = self._string(item.get("renderURL")) or self._string(item.get("imageText"))
        if render_url:
            return render_url
        if output_dir is None:
            return None
        name = self._string(item.get("name"))
        if not name:
            return None
        matches = sorted(output_dir.glob(f"*{name}*"))
        return str(matches[0]) if matches else None
