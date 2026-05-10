from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://models.datalab.to"
MODEL_CACHE_DIR = Path(
    os.environ.get("MODEL_CACHE_DIR")
    or os.environ.get("SURYA_MODEL_CACHE_DIR")
    or "/app/var/model-cache/datalab/models"
)
MODELS = [
    "layout/2025_09_23",
    "text_recognition/2025_09_23",
    "text_detection/2025_05_07",
    "table_recognition/2025_02_18",
    "ocr_error_detection/2025_02_18",
]
CHUNK_SIZE = 1024 * 1024
PART_SIZE = 32 * 1024 * 1024
PARALLEL_WORKERS = int(os.environ.get("MARKER_MODEL_DOWNLOAD_WORKERS", "8"))
PARALLEL_THRESHOLD = 50 * 1024 * 1024
RETRIES = 4
HEADERS = {
    "User-Agent": "curl/8.14.1",
    "Accept": "*/*",
}


def main() -> int:
    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"model_cache_dir={MODEL_CACHE_DIR}", flush=True)
    for model_path in MODELS:
        download_model(model_path)
    print("marker_model_preload_complete", flush=True)
    return 0


def download_model(model_path: str) -> None:
    target_dir = MODEL_CACHE_DIR / model_path
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_url = f"{BASE_URL}/{model_path}/manifest.json"
    manifest_path = target_dir / "manifest.json"
    manifest = fetch_json(manifest_url)
    files = manifest["files"]
    print(f"\n[{model_path}] files={len(files)}", flush=True)
    for name in files:
        download_file(f"{BASE_URL}/{model_path}/{name}", target_dir / name)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_json(url: str) -> dict[str, object]:
    for attempt in range(1, RETRIES + 1):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - network preflight should retry transient failures.
            print(f"  retry {attempt}/{RETRIES} manifest: {exc}", file=sys.stderr, flush=True)
            if attempt == RETRIES:
                raise
            time.sleep(min(30, attempt * 5))
    raise RuntimeError(f"failed to fetch manifest: {url}")


def download_file(url: str, target: Path) -> None:
    expected_size = remote_size(url)
    if target.exists() and expected_size is not None and target.stat().st_size == expected_size:
        print(f"  ok {target.name} {format_bytes(expected_size)}", flush=True)
        return

    if expected_size is not None and expected_size >= PARALLEL_THRESHOLD:
        download_file_parallel(url, target, expected_size)
        return

    part = target.with_suffix(target.suffix + ".part")
    existing = part.stat().st_size if part.exists() else 0
    if target.exists() and (expected_size is None or target.stat().st_size != expected_size):
        target.replace(part)
        existing = part.stat().st_size

    for attempt in range(1, RETRIES + 1):
        try:
            stream_download(url, part, existing, expected_size)
            if expected_size is not None and part.stat().st_size != expected_size:
                actual_size = part.stat().st_size
                raise RuntimeError(
                    f"size mismatch for {target.name}: got {actual_size}, want {expected_size}"
                )
            part.replace(target)
            print(f"  done {target.name} {format_bytes(target.stat().st_size)}", flush=True)
            return
        except Exception as exc:  # noqa: BLE001 - downloader reports and retries transient failures.
            existing = part.stat().st_size if part.exists() else 0
            print(f"  retry {attempt}/{RETRIES} {target.name}: {exc}", file=sys.stderr, flush=True)
            if attempt == RETRIES:
                raise
            time.sleep(min(30, attempt * 5))


def download_file_parallel(url: str, target: Path, expected_size: int) -> None:
    part_dir = target.parent / f".{target.name}.parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    if part.exists():
        part.unlink()

    ranges = []
    start = 0
    index = 0
    while start < expected_size:
        end = min(start + PART_SIZE - 1, expected_size - 1)
        ranges.append((index, start, end))
        start = end + 1
        index += 1

    print(
        f"  parallel {target.name} {len(ranges)} parts x {format_bytes(PART_SIZE)} "
        f"workers={PARALLEL_WORKERS}",
        flush=True,
    )
    completed = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = [
            executor.submit(download_range, url, part_dir / f"{idx:05d}.part", start, end)
            for idx, start, end in ranges
        ]
        for future in as_completed(futures):
            future.result()
            completed += 1
            if completed == len(ranges) or completed % 5 == 0:
                downloaded = sum(path.stat().st_size for path in part_dir.glob("*.part"))
                print_progress(target.name, downloaded, expected_size)

    with part.open("wb") as output:
        for idx, start, end in ranges:
            chunk_path = part_dir / f"{idx:05d}.part"
            expected_part_size = end - start + 1
            if not chunk_path.exists() or chunk_path.stat().st_size != expected_part_size:
                raise RuntimeError(f"incomplete part {chunk_path.name} for {target.name}")
            with chunk_path.open("rb") as chunk:
                while data := chunk.read(CHUNK_SIZE):
                    output.write(data)

    if part.stat().st_size != expected_size:
        raise RuntimeError(
            f"size mismatch for {target.name}: got {part.stat().st_size}, want {expected_size}"
        )
    part.replace(target)
    for chunk_path in part_dir.glob("*.part"):
        chunk_path.unlink()
    part_dir.rmdir()
    print(f"  done {target.name} {format_bytes(target.stat().st_size)}", flush=True)


def download_range(url: str, target: Path, start: int, end: int) -> None:
    expected_size = end - start + 1
    if target.exists() and target.stat().st_size == expected_size:
        return
    temp = target.with_suffix(target.suffix + ".tmp")
    headers = {**HEADERS, "Range": f"bytes={start}-{end}"}
    for attempt in range(1, RETRIES + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=180) as response:
                if response.status != 206:
                    raise RuntimeError(f"range request returned HTTP {response.status}")
                with temp.open("wb") as handle:
                    while chunk := response.read(CHUNK_SIZE):
                        handle.write(chunk)
            if temp.stat().st_size != expected_size:
                actual_size = temp.stat().st_size
                raise RuntimeError(
                    f"part size mismatch {target.name}: got {actual_size}, want {expected_size}"
                )
            temp.replace(target)
            return
        except Exception as exc:  # noqa: BLE001 - per-part retries handle transient network failures.
            if temp.exists():
                temp.unlink()
            print(
                f"  retry {attempt}/{RETRIES} part {target.name}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            if attempt == RETRIES:
                raise
            time.sleep(min(30, attempt * 5))


def remote_size(url: str) -> int | None:
    request = Request(url, headers=HEADERS, method="HEAD")
    for attempt in range(1, RETRIES + 1):
        try:
            with urlopen(request, timeout=60) as response:
                size = response.headers.get("content-length")
                return int(size) if size else None
        except Exception as exc:  # noqa: BLE001 - HEAD requests can fail transiently.
            print(
                f"  retry {attempt}/{RETRIES} head {Path(url).name}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            if attempt == RETRIES:
                raise
            time.sleep(min(30, attempt * 5))
    return None


def stream_download(url: str, part: Path, existing: int, expected_size: int | None) -> None:
    headers = {}
    mode = "wb"
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"

    request = Request(url, headers={**HEADERS, **headers})
    try:
        response = urlopen(request, timeout=120)
    except HTTPError as exc:
        if exc.code == 416:
            return
        if exc.code == 200 and existing > 0:
            existing = 0
            mode = "wb"
            response = urlopen(Request(url, headers=HEADERS), timeout=120)
        else:
            raise
    except URLError:
        raise

    total = expected_size or int(response.headers.get("content-length", "0") or 0)
    downloaded = existing
    last_report = time.monotonic()
    with response, part.open(mode + "") as handle:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_report >= 10:
                print_progress(part.name, downloaded, total)
                last_report = now
    print_progress(part.name, downloaded, total)


def print_progress(name: str, downloaded: int, total: int) -> None:
    if total:
        pct = downloaded / total * 100
        print(f"  {name} {format_bytes(downloaded)}/{format_bytes(total)} {pct:.1f}%", flush=True)
    else:
        print(f"  {name} {format_bytes(downloaded)}", flush=True)


def format_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f}{unit}"
        amount /= 1024
    return f"{value}B"


if __name__ == "__main__":
    raise SystemExit(main())
