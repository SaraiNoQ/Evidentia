import hashlib

from app.core.ids import new_id
from app.core.models import AgentRun, AgentRunStatus, EvidenceAnchor, RetrievalHit


def completed_run(
    *,
    job_id: str,
    agent_name: str,
    output_schema: str,
    evidence: list[EvidenceAnchor] | None = None,
    issue_ids: list[str] | None = None,
    warnings: list[str] | None = None,
    input_text: str = "",
) -> AgentRun:
    return AgentRun(
        agent_run_id=new_id("run"),
        job_id=job_id,
        agent_name=agent_name,
        prompt_version="deterministic.v0.1",
        model_name="deterministic",
        input_hash=hashlib.sha256(input_text.encode("utf-8")).hexdigest()[:16],
        output_schema=output_schema,
        evidence_ids=[item.evidence_id for item in evidence or []],
        issue_ids=issue_ids or [],
        status=AgentRunStatus.COMPLETED,
        warnings=warnings or [],
    )


def evidence_from_hit(hit: RetrievalHit, *, confidence: float = 0.75) -> EvidenceAnchor:
    return hit.to_evidence(confidence=confidence)
