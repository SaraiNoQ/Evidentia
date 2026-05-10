from pathlib import Path

from app.core.ids import new_id
from app.core.models import JobConfig, JobRecord, JobStatus, PaperIR, PaperTrace, utc_now


class LocalJobRepository:
    """Filesystem-backed repository for the Phase 0 local loop."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.uploads_root = self.root / "uploads"
        self.parsed_root = self.root / "parsed"
        self.jobs_root = self.root / "jobs"
        for path in (self.uploads_root, self.parsed_root, self.jobs_root):
            path.mkdir(parents=True, exist_ok=True)

    def create_job(self, config: JobConfig, pdf_bytes: bytes, filename: str) -> JobRecord:
        job_id = new_id("job")
        upload_dir = self.uploads_root / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "paper.pdf"
        upload_path = upload_dir / safe_name
        upload_path.write_bytes(pdf_bytes)
        record = JobRecord(
            job_id=job_id,
            status=JobStatus.CREATED,
            config=config,
            upload_path=upload_path,
        )
        self.save_job(record)
        return record

    def save_job(self, record: JobRecord) -> None:
        record.updated_at = utc_now()
        self._job_path(record.job_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")

    def get_job(self, job_id: str) -> JobRecord | None:
        path = self._job_path(job_id)
        if not path.exists():
            return None
        return JobRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def mark_status(
        self,
        record: JobRecord,
        status: JobStatus,
        *,
        error: str | None = None,
        warnings: list[str] | None = None,
    ) -> JobRecord:
        record.status = status
        if error is not None:
            record.error = error
        if warnings is not None:
            record.warnings = warnings
        self.save_job(record)
        return record

    def save_paper_ir(self, record: JobRecord, paper_ir: PaperIR) -> Path:
        parsed_dir = self.parsed_root / record.job_id
        parsed_dir.mkdir(parents=True, exist_ok=True)
        path = parsed_dir / "paper_ir.json"
        path.write_text(paper_ir.model_dump_json(indent=2), encoding="utf-8")
        record.paper_ir_path = path
        self.save_job(record)
        return path

    def save_canonical_markdown(self, record: JobRecord, markdown: str) -> Path:
        parsed_dir = self.parsed_root / record.job_id
        parsed_dir.mkdir(parents=True, exist_ok=True)
        path = parsed_dir / "canonical_paper.md"
        path.write_text(markdown, encoding="utf-8")
        record.canonical_markdown_path = path
        self.save_job(record)
        return path

    def load_canonical_markdown(self, job_id: str) -> str | None:
        record = self.get_job(job_id)
        if (
            record is None
            or record.canonical_markdown_path is None
            or not record.canonical_markdown_path.exists()
        ):
            return None
        return record.canonical_markdown_path.read_text(encoding="utf-8")

    def save_parse_report(self, record: JobRecord, paper_ir: PaperIR) -> Path:
        parsed_dir = self.parsed_root / record.job_id
        parsed_dir.mkdir(parents=True, exist_ok=True)
        path = parsed_dir / "parse_report.json"
        path.write_text(paper_ir.parse_report.model_dump_json(indent=2), encoding="utf-8")
        record.parse_report_path = path
        self.save_job(record)
        return path

    def save_trace(self, record: JobRecord, trace: PaperTrace) -> Path:
        parsed_dir = self.parsed_root / record.job_id
        parsed_dir.mkdir(parents=True, exist_ok=True)
        path = parsed_dir / "trace.json"
        path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
        record.trace_path = path
        self.save_job(record)
        return path

    def load_trace(self, job_id: str) -> PaperTrace | None:
        record = self.get_job(job_id)
        if record is None or record.trace_path is None or not record.trace_path.exists():
            return None
        return PaperTrace.model_validate_json(record.trace_path.read_text(encoding="utf-8"))

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_root / f"{job_id}.json"
