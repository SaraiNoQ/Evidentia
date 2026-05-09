import math
import re
from collections import Counter

from app.core.ids import new_id
from app.core.models import EvidenceSourceType, PaperArtifact, PaperDocument, RetrievalHit

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


class InternalPaperIndex:
    """Small deterministic retrieval index over chunks and artifacts."""

    def __init__(self, paper: PaperDocument) -> None:
        self.paper = paper
        self.chunk_terms = [Counter(tokenize(chunk.text)) for chunk in paper.chunks]
        self.doc_freq: Counter[str] = Counter()
        for terms in self.chunk_terms:
            self.doc_freq.update(terms.keys())
        self.avg_len = (
            sum(sum(terms.values()) for terms in self.chunk_terms) / len(self.chunk_terms)
            if self.chunk_terms
            else 0.0
        )

    def search_chunks(self, query: str, *, limit: int = 5) -> list[RetrievalHit]:
        query_terms = tokenize(query)
        if not query_terms:
            return []

        scored: list[tuple[float, int]] = []
        for index, terms in enumerate(self.chunk_terms):
            bm25 = self._bm25_score(query_terms, terms)
            overlap = self._term_overlap_score(query_terms, terms)
            score = bm25 + overlap
            if score > 0:
                scored.append((score, index))

        scored.sort(key=lambda item: item[0], reverse=True)
        hits: list[RetrievalHit] = []
        for score, index in scored[:limit]:
            chunk = self.paper.chunks[index]
            hits.append(
                RetrievalHit(
                    hit_id=new_id("hit"),
                    source_type=EvidenceSourceType.PAPER,
                    source_id=chunk.chunk_id,
                    score=round(score, 4),
                    page=chunk.page_start,
                    section=chunk.section_title,
                    quote=self._trim_quote(chunk.text),
                )
            )
        return hits

    def search_artifacts(self, query: str, *, limit: int = 5) -> list[RetrievalHit]:
        query_terms = set(tokenize(query))
        if not query_terms:
            return []
        artifacts: list[PaperArtifact] = [
            *self.paper.tables,
            *self.paper.figures,
            *self.paper.equations,
        ]
        scored: list[tuple[float, PaperArtifact]] = []
        for artifact in artifacts:
            artifact_text = " ".join(
                part for part in [artifact.label, artifact.caption, artifact.section] if part
            )
            artifact_terms = set(tokenize(artifact_text))
            if not artifact_terms:
                continue
            overlap = len(query_terms & artifact_terms) / len(query_terms)
            if overlap > 0:
                scored.append((overlap, artifact))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalHit(
                hit_id=new_id("hit"),
                source_type=EvidenceSourceType.PAPER,
                source_id=artifact.artifact_id,
                score=round(score, 4),
                page=artifact.page,
                section=artifact.section,
                artifact_id=artifact.artifact_id,
                quote=self._trim_quote(
                    artifact.caption or artifact.label or artifact.artifact_type.value
                ),
            )
            for score, artifact in scored[:limit]
        ]

    def search(self, query: str, *, limit: int = 5) -> list[RetrievalHit]:
        hits = [*self.search_chunks(query, limit=limit), *self.search_artifacts(query, limit=limit)]
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def _bm25_score(self, query_terms: list[str], document_terms: Counter[str]) -> float:
        if not document_terms:
            return 0.0
        total_documents = max(1, len(self.chunk_terms))
        doc_len = sum(document_terms.values())
        k1 = 1.5
        b = 0.75
        score = 0.0
        for term in query_terms:
            freq = document_terms.get(term, 0)
            if freq == 0:
                continue
            df = self.doc_freq.get(term, 0)
            idf = math.log(1 + (total_documents - df + 0.5) / (df + 0.5))
            norm = freq + k1 * (1 - b + b * doc_len / max(self.avg_len, 1.0))
            score += idf * (freq * (k1 + 1)) / norm
        return score

    def _term_overlap_score(self, query_terms: list[str], document_terms: Counter[str]) -> float:
        query_set = set(query_terms)
        if not query_set:
            return 0.0
        return len(query_set & set(document_terms.keys())) / len(query_set)

    def _trim_quote(self, text: str, limit: int = 500) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        return normalized[:limit]
