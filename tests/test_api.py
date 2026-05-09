import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_create_job_parses_pdf_and_exposes_trace(
    client: TestClient,
    sample_pdf_path: Path,
) -> None:
    response = client.post(
        "/api/jobs",
        files={"file": ("sample.pdf", sample_pdf_path.read_bytes(), "application/pdf")},
        data={
            "config_json": json.dumps({"review_mode": "quick_audit", "parser_provider": "pymupdf"})
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["job_id"].startswith("job_")
    assert payload["status"] == "completed"
    assert payload["paper_ir_path"].endswith("paper_ir.json")
    assert payload["trace_path"].endswith("trace.json")

    status_response = client.get(f"/api/jobs/{payload['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] == "completed"

    trace_response = client.get(f"/api/jobs/{payload['job_id']}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()["data"]
    assert trace["schema_version"] == "paper_ir.v0.1"
    assert trace["parser_provider"] == "pymupdf"
    assert trace["paper_document"]["chunks"]
    assert trace["summary"]
    assert trace["claims"]
    assert trace["agent_runs"]


def test_local_full_audit_exposes_issues_and_evidence(
    client: TestClient,
    sample_pdf_path: Path,
) -> None:
    response = client.post(
        "/api/jobs",
        files={"file": ("sample.pdf", sample_pdf_path.read_bytes(), "application/pdf")},
        data={
            "config_json": json.dumps(
                {"review_mode": "local_full_audit", "parser_provider": "pymupdf"}
            )
        },
    )
    assert response.status_code == 200
    job_id = response.json()["data"]["job_id"]

    issues_response = client.get(f"/api/jobs/{job_id}/issues")

    assert issues_response.status_code == 200
    issues = issues_response.json()["data"]["items"]
    assert issues
    assert all(issue["evidence"] for issue in issues)

    evidence_response = client.get(f"/api/jobs/{job_id}/issues/{issues[0]['issue_id']}/evidence")
    assert evidence_response.status_code == 200
    assert evidence_response.json()["data"]["evidence"]


def test_invalid_file_type_returns_error(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_report_endpoint_is_reserved_for_later_phase(
    client: TestClient,
    sample_pdf_path: Path,
) -> None:
    create_response = client.post(
        "/api/jobs",
        files={"file": ("sample.pdf", sample_pdf_path.read_bytes(), "application/pdf")},
    )
    job_id = create_response.json()["data"]["job_id"]

    response = client.get(f"/api/jobs/{job_id}/report?format=markdown")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_not_ready"
