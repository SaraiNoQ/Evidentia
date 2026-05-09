from app.agents.utils import completed_run, evidence_from_hit
from app.core.models import AgentRun, PaperDocument, PaperSummary
from app.indexing.internal import InternalPaperIndex


class PaperSummarizer:
    agent_name = "paper_summarizer"

    def run(self, paper: PaperDocument, index: InternalPaperIndex) -> tuple[PaperSummary, AgentRun]:
        hits = []
        for query in ("abstract contribution", "introduction method", "conclusion results"):
            hits.extend(index.search_chunks(query, limit=2))
        unique_hits = {hit.source_id: hit for hit in hits}
        evidence = [evidence_from_hit(hit, confidence=0.8) for hit in unique_hits.values()]
        selected_text = " ".join(hit.quote for hit in list(unique_hits.values())[:3])
        summary_text = (
            selected_text[:900] if selected_text else "No extractable summary evidence found."
        )
        bullets = [hit.quote[:220] for hit in list(unique_hits.values())[:4]]
        summary = PaperSummary(
            summary=summary_text,
            contribution_bullets=bullets,
            evidence_ids=[item.evidence_id for item in evidence],
            warnings=[] if evidence else ["summary_has_no_evidence"],
        )
        run = completed_run(
            job_id=paper.job_id,
            agent_name=self.agent_name,
            output_schema="PaperSummary",
            evidence=evidence,
            warnings=summary.warnings,
            input_text=paper.paper_id,
        )
        return summary, run
