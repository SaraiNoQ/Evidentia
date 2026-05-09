import json
from typing import Annotated, Any, cast

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import ValidationError

from app.agents.orchestrator import LocalAuditOrchestrator
from app.api.envelope import error_response, success
from app.core.config import Settings
from app.core.models import JobConfig, JobRecord, JobStatus, PaperTrace, ReviewMode
from app.core.repository import LocalJobRepository
from app.parsing.factory import get_parser

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("")
async def create_job(
    request: Request,
    file: Annotated[UploadFile, File()],
    config_json: Annotated[str | None, Form()] = None,
) -> dict[str, Any] | Any:
    if not _is_pdf(file):
        return error_response(
            code="unsupported_file_type",
            message="Only PDF uploads are supported.",
            request=request,
            status_code=415,
            details={"filename": file.filename, "content_type": file.content_type},
        )

    config = _parse_config(config_json)
    if isinstance(config, ValidationError):
        return error_response(
            code="invalid_job_config",
            message="JobConfig validation failed.",
            request=request,
            status_code=422,
            details={"errors": config.errors()},
        )
    if isinstance(config, json.JSONDecodeError):
        return error_response(
            code="invalid_job_config",
            message="config_json must be valid JSON.",
            request=request,
            status_code=422,
            details={"error": str(config)},
        )

    repository = _repository(request)
    settings = _settings(request)
    pdf_bytes = await file.read()
    record = repository.create_job(config, pdf_bytes, file.filename or "paper.pdf")
    repository.mark_status(record, JobStatus.PARSING)

    try:
        parser = get_parser(config.parser_provider or settings.parser_provider)
        parse_result = parser.parse(record.upload_path, job_id=record.job_id, config=config)
        paper_ir_path = repository.save_paper_ir(record, parse_result.paper_document)
        record.trace_path = repository.parsed_root / record.job_id / "trace.json"

        audit_result = None
        if config.review_mode in {ReviewMode.QUICK_AUDIT, ReviewMode.LOCAL_FULL_AUDIT}:
            audit_result = LocalAuditOrchestrator().run(parse_result.paper_document)

        record.status = JobStatus.COMPLETED
        record.warnings = parse_result.warnings + (audit_result.warnings if audit_result else [])
        trace = PaperTrace(
            schema_version=settings.schema_version,
            job=record,
            parser_provider=parse_result.provider,
            job_config=config,
            paper_document=parse_result.paper_document,
            generated_files={
                "upload_pdf": str(record.upload_path),
                "paper_ir": str(paper_ir_path),
                "trace": str(record.trace_path),
            },
            warnings=record.warnings,
            summary=audit_result.summary if audit_result else None,
            claims=audit_result.claims if audit_result else [],
            questions=audit_result.questions if audit_result else [],
            evidence_answers=audit_result.evidence_answers if audit_result else [],
            issues=audit_result.issues if audit_result else [],
            agent_runs=audit_result.agent_runs if audit_result else [],
            retrieval_hits=audit_result.retrieval_hits if audit_result else [],
        )
        repository.save_trace(record, trace)
    except Exception as exc:  # noqa: BLE001 - API converts parser/provider failures into job state.
        repository.mark_status(record, JobStatus.FAILED, error=str(exc))
        return error_response(
            code="parse_failed",
            message="PDF parsing failed.",
            request=request,
            status_code=422,
            details={"job_id": record.job_id, "error": str(exc)},
        )

    refreshed = repository.get_job(record.job_id) or record
    return success(_job_payload(refreshed), request)


@router.get("/{job_id}")
def get_job(job_id: str, request: Request) -> dict[str, Any] | Any:
    record = _repository(request).get_job(job_id)
    if record is None:
        return _job_not_found(job_id, request)
    return success(_job_payload(record), request)


@router.get("/{job_id}/trace")
def get_trace(job_id: str, request: Request) -> dict[str, Any] | Any:
    repository = _repository(request)
    if repository.get_job(job_id) is None:
        return _job_not_found(job_id, request)
    trace = repository.load_trace(job_id)
    if trace is None:
        return error_response(
            code="report_not_ready",
            message="Trace is not ready for this job.",
            request=request,
            status_code=409,
            details={"job_id": job_id},
        )
    return success(trace.model_dump(mode="json"), request)


@router.get("/{job_id}/issues")
def list_issues(job_id: str, request: Request) -> dict[str, Any] | Any:
    repository = _repository(request)
    if repository.get_job(job_id) is None:
        return _job_not_found(job_id, request)
    trace = repository.load_trace(job_id)
    issues = trace.issues if trace else []
    return success(
        {
            "items": [issue.model_dump(mode="json") for issue in issues],
            "next_cursor": None,
            "has_more": False,
        },
        request,
    )


@router.get("/{job_id}/issues/{issue_id}/evidence")
def get_issue_evidence(job_id: str, issue_id: str, request: Request) -> dict[str, Any] | Any:
    repository = _repository(request)
    if repository.get_job(job_id) is None:
        return _job_not_found(job_id, request)
    trace = repository.load_trace(job_id)
    issues = trace.issues if trace else []
    for issue in issues:
        if issue.issue_id == issue_id:
            return success(
                {
                    "issue_id": issue_id,
                    "evidence": [evidence.model_dump(mode="json") for evidence in issue.evidence],
                },
                request,
            )
    return error_response(
        code="issue_not_found",
        message="Issue was not found for this job.",
        request=request,
        status_code=404,
        details={"job_id": job_id, "issue_id": issue_id},
    )


@router.get("/{job_id}/report")
def get_report(job_id: str, request: Request, format: str = "markdown") -> Any:
    if _repository(request).get_job(job_id) is None:
        return _job_not_found(job_id, request)
    return error_response(
        code="report_not_ready",
        message="Reviewer report generation starts in Phase 2.",
        request=request,
        status_code=409,
        details={"job_id": job_id, "format": format},
    )


def _parse_config(config_json: str | None) -> JobConfig | ValidationError | json.JSONDecodeError:
    if not config_json:
        return JobConfig()
    try:
        payload = json.loads(config_json)
    except json.JSONDecodeError as exc:
        return exc
    try:
        return JobConfig.model_validate(payload)
    except ValidationError as exc:
        return exc


def _is_pdf(file: UploadFile) -> bool:
    filename = (file.filename or "").lower()
    return filename.endswith(".pdf") or file.content_type == "application/pdf"


def _repository(request: Request) -> LocalJobRepository:
    return cast(LocalJobRepository, request.app.state.jobs)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _job_not_found(job_id: str, request: Request) -> Any:
    return error_response(
        code="job_not_found",
        message="Job was not found.",
        request=request,
        status_code=404,
        details={"job_id": job_id},
    )


def _job_payload(record: JobRecord) -> dict[str, Any]:
    return {
        "job_id": record.job_id,
        "status": record.status,
        "warnings": record.warnings,
        "error": record.error,
        "upload_path": str(record.upload_path),
        "paper_ir_path": str(record.paper_ir_path) if record.paper_ir_path else None,
        "trace_path": str(record.trace_path) if record.trace_path else None,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
