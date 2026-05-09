from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph

from app.agents.auditors import LocalAuditors
from app.agents.claim_miner import ClaimMiner
from app.agents.meta_reviewer import MetaReviewer
from app.agents.question_answering import EvidenceAnsweringAgent, QuestionTreeGenerator
from app.agents.summarizer import PaperSummarizer
from app.core.models import (
    AgentRun,
    Claim,
    EvidenceAnswer,
    Issue,
    LocalAuditResult,
    PaperDocument,
    PaperSummary,
    QuestionNode,
    RetrievalHit,
)
from app.indexing.internal import InternalPaperIndex


class LocalAuditState(TypedDict, total=False):
    paper: PaperDocument
    index: InternalPaperIndex
    summary: PaperSummary
    claims: list[Claim]
    issues: list[Issue]
    questions: list[QuestionNode]
    evidence_answers: list[EvidenceAnswer]
    agent_runs: list[AgentRun]
    retrieval_hits: list[RetrievalHit]


class LocalAuditOrchestrator:
    """Deterministic Phase 1 audit implemented as a LangGraph DAG."""

    def __init__(self) -> None:
        self.summarizer = PaperSummarizer()
        self.claim_miner = ClaimMiner()
        self.auditors = LocalAuditors()
        self.question_generator = QuestionTreeGenerator()
        self.evidence_answerer = EvidenceAnsweringAgent()
        self.meta_reviewer = MetaReviewer()

    def run(self, paper: PaperDocument) -> LocalAuditResult:
        initial_state: LocalAuditState = {
            "paper": paper,
            "index": InternalPaperIndex(paper),
            "agent_runs": [],
        }
        final_state = cast(LocalAuditState, self._build_graph().invoke(initial_state))
        return LocalAuditResult(
            summary=final_state.get("summary"),
            claims=final_state.get("claims", []),
            questions=final_state.get("questions", []),
            evidence_answers=final_state.get("evidence_answers", []),
            issues=final_state.get("issues", []),
            agent_runs=final_state.get("agent_runs", []),
            retrieval_hits=final_state.get("retrieval_hits", []),
            warnings=[],
        )

    def _build_graph(self) -> Any:
        graph = StateGraph(LocalAuditState)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("claim_mine", self._claim_mine_node)
        graph.add_node("local_auditors", self._local_auditors_node)
        graph.add_node("question_tree", self._question_tree_node)
        graph.add_node("evidence_answer", self._evidence_answer_node)
        graph.add_node("meta_review", self._meta_review_node)
        graph.add_node("collect_retrieval_hits", self._collect_retrieval_hits_node)
        graph.set_entry_point("summarize")
        graph.add_edge("summarize", "claim_mine")
        graph.add_edge("claim_mine", "local_auditors")
        graph.add_edge("local_auditors", "question_tree")
        graph.add_edge("question_tree", "evidence_answer")
        graph.add_edge("evidence_answer", "meta_review")
        graph.add_edge("meta_review", "collect_retrieval_hits")
        graph.add_edge("collect_retrieval_hits", END)
        return graph.compile()

    def _summarize_node(self, state: LocalAuditState) -> LocalAuditState:
        summary, run = self.summarizer.run(state["paper"], state["index"])
        return {"summary": summary, "agent_runs": [*state.get("agent_runs", []), run]}

    def _claim_mine_node(self, state: LocalAuditState) -> LocalAuditState:
        claims, run = self.claim_miner.run(state["paper"], state["index"])
        return {"claims": claims, "agent_runs": [*state.get("agent_runs", []), run]}

    def _local_auditors_node(self, state: LocalAuditState) -> LocalAuditState:
        issues, runs = self.auditors.run(state["paper"], state.get("claims", []), state["index"])
        return {"issues": issues, "agent_runs": [*state.get("agent_runs", []), *runs]}

    def _question_tree_node(self, state: LocalAuditState) -> LocalAuditState:
        questions, run = self.question_generator.run(state["paper"], state.get("claims", []))
        return {"questions": questions, "agent_runs": [*state.get("agent_runs", []), run]}

    def _evidence_answer_node(self, state: LocalAuditState) -> LocalAuditState:
        answers, run = self.evidence_answerer.run(
            state["paper"],
            state.get("questions", []),
            state.get("claims", []),
            state["index"],
        )
        return {"evidence_answers": answers, "agent_runs": [*state.get("agent_runs", []), run]}

    def _meta_review_node(self, state: LocalAuditState) -> LocalAuditState:
        issues, run = self.meta_reviewer.run(state["paper"], state.get("issues", []))
        return {"issues": issues, "agent_runs": [*state.get("agent_runs", []), run]}

    def _collect_retrieval_hits_node(self, state: LocalAuditState) -> LocalAuditState:
        hits = []
        for claim in state.get("claims", []):
            for evidence in claim.evidence:
                hits.extend(state["index"].search(evidence.quote or claim.text, limit=1))
        return {"retrieval_hits": hits}
