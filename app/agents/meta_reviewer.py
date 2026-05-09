from app.agents.utils import completed_run
from app.core.models import AgentRun, Issue, IssueSeverity, PaperDocument


class MetaReviewer:
    agent_name = "meta_reviewer"

    def run(self, paper: PaperDocument, issues: list[Issue]) -> tuple[list[Issue], AgentRun]:
        deduped: dict[tuple[str, str], Issue] = {}
        for issue in issues:
            key = (issue.dimension, issue.title.lower())
            if key not in deduped:
                deduped[key] = self._calibrate(issue)
            else:
                existing = deduped[key]
                existing.evidence.extend(issue.evidence)
                existing.missing_evidence.extend(issue.missing_evidence)
        verified = list(deduped.values())
        for issue in verified:
            if self.agent_name not in issue.verified_by:
                issue.verified_by.append(self.agent_name)
        run = completed_run(
            job_id=paper.job_id,
            agent_name=self.agent_name,
            output_schema="list[Issue]",
            evidence=[evidence for issue in verified for evidence in issue.evidence],
            issue_ids=[issue.issue_id for issue in verified],
            input_text=" ".join(issue.title for issue in issues),
        )
        return verified, run

    def _calibrate(self, issue: Issue) -> Issue:
        if issue.severity in {IssueSeverity.FATAL, IssueSeverity.MAJOR} and not issue.evidence:
            issue.severity = IssueSeverity.POSSIBLE
            issue.missing_evidence.append("major_or_fatal_issue_missing_evidence")
        if not issue.evidence and issue.severity != IssueSeverity.POSSIBLE:
            issue.severity = IssueSeverity.POSSIBLE
        return issue
