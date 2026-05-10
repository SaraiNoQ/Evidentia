#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

JAR_PATH = Path("/opt/pdffigures2/pdffigures2.jar")
LIB_GLOB = "/opt/pdffigures2/lib/*"
MAIN_CLASS = "org.allenai.pdffigures2.FigureExtractorBatchCli"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("-m", "--metadata-json", required=True)
    parser.add_argument("-d", "--output-dir", required=True)
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir)
    metadata_json = Path(args.metadata_json)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_json.parent.mkdir(parents=True, exist_ok=True)

    if not JAR_PATH.exists():
        print("pdffigures2 jar is not installed in this image", file=sys.stderr)
        return 127

    with tempfile.TemporaryDirectory() as tmp:
        input_dir = Path(tmp) / "input"
        data_prefix = output_dir / "data"
        image_prefix = output_dir / "figure"
        stats_path = output_dir / "stats.json"
        input_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, input_dir / pdf_path.name)

        command = [
            "java",
            "-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider",
            "-cp",
            f"{JAR_PATH}:{LIB_GLOB}",
            MAIN_CLASS,
            str(input_dir),
            "-s",
            str(stats_path),
            "-m",
            str(image_prefix),
            "-d",
            str(data_prefix),
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            print(completed.stderr or completed.stdout, file=sys.stderr)
            return completed.returncode

    figures = []
    for path in sorted(output_dir.glob("data*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            figures.extend(payload)
        elif isinstance(payload, dict):
            figures.append(payload)

    metadata_json.write_text(json.dumps(figures, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
