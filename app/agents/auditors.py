import re
from collections.abc import Iterable

from app.agents.utils import completed_run, evidence_from_hit
from app.core.ids import new_id
from app.core.models import (
    AgentRun,
    Claim,
    ClaimType,
    EvidenceAnchor,
    EvidenceLevel,
    EvidenceSourceType,
    Issue,
    IssueSeverity,
    PaperDocument,
)
from app.indexing.internal import InternalPaperIndex


class LocalAuditors:
    def run(
        self,
        paper: PaperDocument,
        claims: list[Claim],
        index: InternalPaperIndex,
    ) -> tuple[list[Issue], list[AgentRun]]:
        issues: list[Issue] = []
        runs: list[AgentRun] = []
        for agent_name, agent_issues in (
            ("technical_soundness_auditor", self._technical_soundness(paper, claims, index)),
            ("experiment_auditor", self._experiment(paper, claims, index)),
            ("reproducibility_auditor", self._reproducibility(paper, index)),
            ("writing_presentation_auditor", self._writing(paper, index)),
            ("numeric_consistency_auditor", self._numeric(paper, index)),
        ):
            issues.extend(agent_issues)
            runs.append(
                completed_run(
                    job_id=paper.job_id,
                    agent_name=agent_name,
                    output_schema="list[Issue]",
                    evidence=[evidence for issue in agent_issues for evidence in issue.evidence],
                    issue_ids=[issue.issue_id for issue in agent_issues],
                    input_text=paper.paper_id,
                )
            )
        return issues, runs

    def _technical_soundness(
        self, paper: PaperDocument, claims: list[Claim], index: InternalPaperIndex
    ) -> list[Issue]:
        method_sections = self._sections_containing(paper, ("method", "approach", "architecture"))
        technical_claims = [claim for claim in claims if claim.claim_type == ClaimType.TECHNICAL]
        if technical_claims and not method_sections:
            evidence = self._evidence_for(index, technical_claims[0].text)
            return [
                self._issue(
                    title="Technical contribution claim lacks a detected method section",
                    severity=IssueSeverity.POSSIBLE,
                    dimension="technical_soundness",
                    description=(
                        "The local parser found technical contribution claims, but no method, "
                        "approach, or architecture section was detected in Paper IR."
                    ),
                    recommended_fix=(
                        "Add or clarify the method section and ensure the main technical mechanism "
                        "is easy to locate from headings and captions."
                    ),
                    evidence=evidence,
                    affected_claim_ids=[technical_claims[0].claim_id],
                )
            ]
        return []

    def _experiment(
        self, paper: PaperDocument, claims: list[Claim], index: InternalPaperIndex
    ) -> list[Issue]:
        experiment_sections = self._sections_containing(
            paper, ("experiment", "evaluation", "result")
        )
        empirical_claims = [claim for claim in claims if claim.claim_type == ClaimType.EMPIRICAL]
        text = self._paper_text(paper)
        issues: list[Issue] = []
        if empirical_claims and not experiment_sections:
            issues.append(
                self._issue(
                    title="Empirical claim lacks a detected experiment or evaluation section",
                    severity=IssueSeverity.POSSIBLE,
                    dimension="experiment",
                    description=(
                        "The paper appears to make empirical or benchmark claims, but the "
                        "parser did not detect an experiment, evaluation, or results section."
                    ),
                    recommended_fix=(
                        "Make the experimental protocol, datasets, metrics, and results "
                        "section explicit."
                    ),
                    evidence=self._evidence_for(index, empirical_claims[0].text),
                    affected_claim_ids=[empirical_claims[0].claim_id],
                )
            )
        if experiment_sections and not re.search(r"\b(baseline|compare|comparison)\b", text, re.I):
            issues.append(
                self._issue(
                    title="Experiment section does not mention baselines or comparisons",
                    severity=IssueSeverity.POSSIBLE,
                    dimension="experiment",
                    description=(
                        "An experiment-like section was detected, but no baseline or "
                        "comparison language was found in the local Paper IR text."
                    ),
                    recommended_fix=(
                        "State the compared baselines and justify why they are sufficient."
                    ),
                    evidence=self._evidence_for(index, "experiment evaluation result"),
                )
            )
        return issues

    def _reproducibility(self, paper: PaperDocument, index: InternalPaperIndex) -> list[Issue]:
        text = self._paper_text(paper)
        missing = []
        for label, pattern in (
            ("code availability", r"\b(code|repository|github)\b"),
            ("data availability", r"\b(dataset|data availability|data source)\b"),
            ("hyperparameters", r"\b(hyperparameter|learning rate|batch size|temperature)\b"),
            ("compute/model details", r"\b(gpu|cpu|compute|model version|api)\b"),
        ):
            if not re.search(pattern, text, re.I):
                missing.append(label)
        if len(missing) < 2:
            return []
        return [
            self._issue(
                title="Reproducibility details appear incomplete",
                severity=IssueSeverity.POSSIBLE,
                dimension="reproducibility",
                description=(
                    f"The local audit did not find explicit mentions of: {', '.join(missing)}."
                ),
                recommended_fix=(
                    "Add a reproducibility checklist covering code/data availability, key "
                    "hyperparameters, compute, model versions, seeds, and closed-API settings."
                ),
                evidence=self._evidence_for(index, "reproducibility code data hyperparameters"),
                missing_evidence=missing,
            )
        ]

    def _writing(self, paper: PaperDocument, index: InternalPaperIndex) -> list[Issue]:
        issues: list[Issue] = []
        required = ("abstract", "introduction", "conclusion")
        detected = {section.lower() for section in paper.sections}
        missing_sections = [
            section for section in required if not self._contains_any(detected, (section,))
        ]
        if missing_sections:
            issues.append(
                self._issue(
                    title="Common paper sections were not detected",
                    severity=IssueSeverity.POSSIBLE,
                    dimension="writing_presentation",
                    description=(
                        "The parser did not detect these common sections: "
                        f"{', '.join(missing_sections)}. This may reflect formatting "
                        "or structure issues."
                    ),
                    recommended_fix=(
                        "Use clear section headings so reviewers and automated tools can "
                        "locate the paper setup, contribution, and conclusion."
                    ),
                    evidence=self._evidence_for(index, "abstract introduction conclusion"),
                    missing_evidence=missing_sections,
                )
            )
        weak_captions = [
            artifact
            for artifact in [*paper.tables, *paper.figures]
            if not artifact.caption or len(artifact.caption) < 20
        ]
        if weak_captions:
            evidence = [
                evidence_from_hit(hit)
                for hit in index.search_artifacts("table figure caption", limit=3)
            ]
            issues.append(
                self._issue(
                    title="Some table or figure captions appear underspecified",
                    severity=IssueSeverity.MINOR,
                    dimension="writing_presentation",
                    description="One or more detected tables/figures have very short captions.",
                    recommended_fix=(
                        "Expand captions so they state the artifact purpose and key takeaway."
                    ),
                    evidence=evidence,
                )
            )
        return issues

    def _numeric(self, paper: PaperDocument, index: InternalPaperIndex) -> list[Issue]:
        text = self._paper_text(paper)
        percent_claims = re.findall(r"\b\d+(?:\.\d+)?\s*%", text)
        if percent_claims and not paper.tables:
            return [
                self._issue(
                    title="Numeric percentage claims lack detected table evidence",
                    severity=IssueSeverity.POSSIBLE,
                    dimension="numeric_consistency",
                    description=(
                        "Percentage values were found in text, but no tables were detected for "
                        "deterministic verification in Phase 1."
                    ),
                    recommended_fix=(
                        "Ensure numeric claims are traceable to tables or explicit calculations."
                    ),
                    evidence=self._evidence_for(index, percent_claims[0]),
                )
            ]
        return []

    def _issue(
        self,
        *,
        title: str,
        severity: IssueSeverity,
        dimension: str,
        description: str,
        recommended_fix: str,
        evidence: list[EvidenceAnchor],
        affected_claim_ids: list[str] | None = None,
        missing_evidence: list[str] | None = None,
    ) -> Issue:
        return Issue(
            issue_id=new_id("issue"),
            title=title,
            severity=severity,
            dimension=dimension,
            description=description,
            affected_claim_ids=affected_claim_ids or [],
            evidence=evidence,
            missing_evidence=missing_evidence or [],
            recommended_fix=recommended_fix,
            confidence=0.72 if evidence else 0.45,
            verified_by=[],
        )

    def _evidence_for(self, index: InternalPaperIndex, query: str) -> list[EvidenceAnchor]:
        evidence = [evidence_from_hit(hit) for hit in index.search(query, limit=2)]
        if evidence or not index.paper.chunks:
            return evidence
        chunk = index.paper.chunks[0]
        return [
            EvidenceAnchor(
                evidence_id=new_id("ev"),
                source_type=EvidenceSourceType.PAPER,
                source_id=chunk.chunk_id,
                page=chunk.page_start,
                section=chunk.section_title,
                quote=chunk.text[:500],
                confidence=0.45,
                evidence_level=EvidenceLevel.B,
            )
        ]

    def _sections_containing(self, paper: PaperDocument, needles: Iterable[str]) -> list[str]:
        return [
            section
            for section in paper.sections
            if any(needle in section.lower() for needle in needles)
        ]

    def _contains_any(self, values: set[str], needles: Iterable[str]) -> bool:
        return any(any(needle in value for value in values) for needle in needles)

    def _paper_text(self, paper: PaperDocument) -> str:
        return "\n".join(chunk.text for chunk in paper.chunks)
