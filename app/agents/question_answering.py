from app.agents.utils import completed_run, evidence_from_hit
from app.core.ids import new_id
from app.core.models import (
    AgentRun,
    Claim,
    EvidenceAnswer,
    EvidenceAnswerState,
    PaperDocument,
    QuestionNode,
)
from app.indexing.internal import InternalPaperIndex


class QuestionTreeGenerator:
    agent_name = "question_tree_generator"

    def run(self, paper: PaperDocument, claims: list[Claim]) -> tuple[list[QuestionNode], AgentRun]:
        questions = [
            QuestionNode(
                question_id=new_id("question"),
                claim_id=claim.claim_id,
                question=(
                    f"Is this {claim.claim_type.value} claim directly supported by paper evidence?"
                ),
                dimension=claim.claim_type.value,
                evidence_ids=[evidence.evidence_id for evidence in claim.evidence],
            )
            for claim in claims
        ]
        run = completed_run(
            job_id=paper.job_id,
            agent_name=self.agent_name,
            output_schema="list[QuestionNode]",
            evidence=[evidence for claim in claims for evidence in claim.evidence],
            input_text=" ".join(claim.text for claim in claims),
        )
        return questions, run


class EvidenceAnsweringAgent:
    agent_name = "evidence_answering_agent"

    def run(
        self,
        paper: PaperDocument,
        questions: list[QuestionNode],
        claims: list[Claim],
        index: InternalPaperIndex,
    ) -> tuple[list[EvidenceAnswer], AgentRun]:
        claim_by_id = {claim.claim_id: claim for claim in claims}
        answers: list[EvidenceAnswer] = []
        for question in questions:
            claim = claim_by_id.get(question.claim_id or "")
            query = claim.text if claim else question.question
            hits = index.search(query, limit=2)
            evidence = [evidence_from_hit(hit, confidence=0.78) for hit in hits]
            if claim and claim.evidence:
                state = EvidenceAnswerState.SUPPORTED
                rationale = "The claim has direct paper evidence anchors from Claim Miner."
            elif evidence:
                state = EvidenceAnswerState.PARTIALLY_SUPPORTED
                rationale = (
                    "Related paper evidence was found, but the claim was not directly anchored."
                )
            else:
                state = EvidenceAnswerState.UNCLEAR
                rationale = "No relevant paper evidence was found by internal retrieval."
            answers.append(
                EvidenceAnswer(
                    answer_id=new_id("answer"),
                    question_id=question.question_id,
                    answer=state,
                    rationale=rationale,
                    evidence=evidence or (claim.evidence if claim else []),
                    confidence=0.8 if evidence or (claim and claim.evidence) else 0.4,
                )
            )
        run = completed_run(
            job_id=paper.job_id,
            agent_name=self.agent_name,
            output_schema="list[EvidenceAnswer]",
            evidence=[evidence for answer in answers for evidence in answer.evidence],
            input_text=" ".join(question.question for question in questions),
        )
        return answers, run
