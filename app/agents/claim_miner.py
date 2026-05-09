import re

from app.agents.utils import completed_run, evidence_from_hit
from app.core.ids import new_id
from app.core.models import AgentRun, Claim, ClaimType, PaperDocument
from app.indexing.internal import InternalPaperIndex

CLAIM_PATTERNS: tuple[tuple[ClaimType, re.Pattern[str]], ...] = (
    (
        ClaimType.NOVELTY,
        re.compile(r"\b(novel|new|first|introduc(?:e|es)|propos(?:e|es))\b", re.I),
    ),
    (
        ClaimType.TECHNICAL,
        re.compile(r"\b(method|framework|algorithm|architecture|system)\b", re.I),
    ),
    (
        ClaimType.EMPIRICAL,
        re.compile(r"\b(experiment|evaluation|result|benchmark|outperform)\b", re.I),
    ),
    (
        ClaimType.EFFICIENCY,
        re.compile(r"\b(efficient|latency|cost|speed|throughput|faster)\b", re.I),
    ),
    (
        ClaimType.PRIVACY,
        re.compile(r"\b(privac|differential|anonymous|federated)\b", re.I),
    ),
    (ClaimType.SAFETY, re.compile(r"\b(safety|secure|risk|robust|attack)\b", re.I)),
    (
        ClaimType.REPRODUCIBILITY,
        re.compile(r"\b(code|data|seed|hyperparameter|reproduc)\b", re.I),
    ),
)


class ClaimMiner:
    agent_name = "claim_miner"

    def run(self, paper: PaperDocument, index: InternalPaperIndex) -> tuple[list[Claim], AgentRun]:
        claims: list[Claim] = []
        for chunk in paper.chunks:
            if not self._is_claim_rich_section(chunk.section_title):
                continue
            for sentence in self._sentences(chunk.text):
                claim_type = self._classify(sentence)
                if claim_type is None:
                    continue
                hit = index.search_chunks(sentence, limit=1)
                evidence = [evidence_from_hit(hit[0], confidence=0.82)] if hit else []
                claims.append(
                    Claim(
                        claim_id=new_id("claim"),
                        paper_id=paper.paper_id,
                        text=sentence,
                        claim_type=claim_type,
                        evidence=evidence,
                        confidence=0.78 if evidence else 0.55,
                    )
                )
                if len(claims) >= 20:
                    break
            if len(claims) >= 20:
                break

        if not claims and paper.chunks:
            chunk = paper.chunks[0]
            hit = index.search_chunks(chunk.text[:120], limit=1)
            evidence = [evidence_from_hit(hit[0], confidence=0.65)] if hit else []
            claims.append(
                Claim(
                    claim_id=new_id("claim"),
                    paper_id=paper.paper_id,
                    text=chunk.text[:300],
                    claim_type=ClaimType.GENERAL,
                    evidence=evidence,
                    confidence=0.5,
                )
            )

        evidence_items = [item for claim in claims for item in claim.evidence]
        run = completed_run(
            job_id=paper.job_id,
            agent_name=self.agent_name,
            output_schema="list[Claim]",
            evidence=evidence_items,
            input_text=" ".join(chunk.text[:80] for chunk in paper.chunks[:8]),
        )
        return claims, run

    def _is_claim_rich_section(self, section: str) -> bool:
        normalized = section.lower()
        return any(
            key in normalized
            for key in (
                "abstract",
                "introduction",
                "method",
                "approach",
                "experiment",
                "evaluation",
                "result",
                "conclusion",
                "unknown",
            )
        )

    def _sentences(self, text: str) -> list[str]:
        candidates = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
        return [candidate for candidate in candidates if 25 <= len(candidate) <= 500]

    def _classify(self, sentence: str) -> ClaimType | None:
        for claim_type, pattern in CLAIM_PATTERNS:
            if pattern.search(sentence):
                return claim_type
        return None
