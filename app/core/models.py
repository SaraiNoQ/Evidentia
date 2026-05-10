from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.ids import has_prefix


def utc_now() -> datetime:
    return datetime.now(UTC)


class PrefixModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @staticmethod
    def _validate_prefix(value: str, prefix: str) -> str:
        if not has_prefix(value, prefix):
            raise ValueError(f"id must start with {prefix}_")
        return value


class JobStatus(StrEnum):
    CREATED = "created"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewMode(StrEnum):
    QUICK_AUDIT = "quick_audit"
    LOCAL_FULL_AUDIT = "local_full_audit"
    FULL_REVIEW = "full_review"


class ParserProfile(StrEnum):
    RESEARCH_DEFAULT = "research_default"
    COMMERCIAL_SAFE = "commercial_safe"
    HARD_CASE = "hard_case"


class ParserSource(StrEnum):
    GROBID = "grobid"
    MARKER = "marker"
    PDFFIGURES2 = "pdffigures2"
    DOCLING = "docling"
    CAMELOT = "camelot"
    MINERU = "mineru"
    PYMUPDF = "pymupdf"
    FUSION = "fusion"
    RENDERER = "renderer"


class EvidenceSourceType(StrEnum):
    PAPER = "paper"
    EXTERNAL_PAPER = "external_paper"
    CODE = "code"
    COMPUTED_CHECK = "computed_check"
    USER_NOTE = "user_note"


class EvidenceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class IssueSeverity(StrEnum):
    FATAL = "fatal"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    POSSIBLE = "possible"


class GateState(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_RUN = "not_run"


class AgentRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ArtifactType(StrEnum):
    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    ALGORITHM = "algorithm"


class PaperBlockType(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    EQUATION = "equation"
    TABLE_REF = "table_ref"
    FIGURE_REF = "figure_ref"
    LIST = "list"
    CODE = "code"
    QUOTE = "quote"
    APPENDIX = "appendix"


class TextBasedPdfStatus(StrEnum):
    TEXT_BASED = "text_based"
    LOW_TEXT = "low_text"
    UNSUPPORTED_SCANNED = "unsupported_scanned_pdf"


class ClaimType(StrEnum):
    NOVELTY = "novelty"
    TECHNICAL = "technical"
    THEORY = "theory"
    EMPIRICAL = "empirical"
    EFFICIENCY = "efficiency"
    PRIVACY = "privacy"
    SAFETY = "safety"
    REPRODUCIBILITY = "reproducibility"
    GENERAL = "general"


class EvidenceAnswerState(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNCLEAR = "unclear"


class LineSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int | None = Field(default=None, ge=1)
    end: int | None = Field(default=None, ge=1)


class CharSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @field_validator("end")
    @classmethod
    def end_must_follow_start(cls, value: int, info: Any) -> int:
        start = info.data.get("start")
        if start is not None and value < start:
            raise ValueError("char span end must be greater than or equal to start")
        return value


class JobConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: str | None = None
    review_mode: ReviewMode = ReviewMode.QUICK_AUDIT
    parser_provider: str = "paper_ir_ensemble"
    parser_profile: ParserProfile = ParserProfile.RESEARCH_DEFAULT
    external_retrieval_enabled: bool = False
    max_pages: int | None = Field(default=None, ge=1)
    token_budget: int | None = Field(default=None, ge=1)


class PaperChunk(PrefixModel):
    chunk_id: str
    paper_id: str
    section_title: str
    text: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    char_span: CharSpan | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("chunk_id")
    @classmethod
    def validate_chunk_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "chunk")

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "paper")

    @field_validator("page_end")
    @classmethod
    def page_end_must_follow_start(cls, value: int, info: Any) -> int:
        page_start = info.data.get("page_start")
        if page_start is not None and value < page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return value


class PaperArtifact(PrefixModel):
    artifact_id: str
    paper_id: str
    artifact_type: ArtifactType
    label: str | None = None
    caption: str | None = None
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "artifact")

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "paper")


class Table(PaperArtifact):
    artifact_type: Literal[ArtifactType.TABLE] = ArtifactType.TABLE
    cells: list[list[str]] = Field(default_factory=list)


class Figure(PaperArtifact):
    artifact_type: Literal[ArtifactType.FIGURE] = ArtifactType.FIGURE


class Equation(PaperArtifact):
    artifact_type: Literal[ArtifactType.EQUATION] = ArtifactType.EQUATION
    latex: str | None = None


class Reference(PrefixModel):
    reference_id: str
    paper_id: str
    raw_text: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1000, le=3000)
    doi: str | None = None
    url: str | None = None

    @field_validator("reference_id")
    @classmethod
    def validate_reference_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "ref")

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "paper")


class PaperDocument(PrefixModel):
    paper_id: str
    job_id: str
    title: str | None = None
    page_count: int = Field(ge=0)
    sections: list[str] = Field(default_factory=list)
    chunks: list[PaperChunk] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    figures: list[Figure] = Field(default_factory=list)
    equations: list[Equation] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    parse_confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "paper")

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "job")


class EvidenceAnchor(PrefixModel):
    evidence_id: str
    source_type: EvidenceSourceType
    source_id: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    line_span: LineSpan | None = None
    artifact_id: str | None = None
    quote: str | None = None
    url: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_level: EvidenceLevel

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "ev")


class RetrievalHit(PrefixModel):
    hit_id: str
    source_type: EvidenceSourceType
    source_id: str
    score: float = Field(ge=0.0)
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    quote: str
    artifact_id: str | None = None

    @field_validator("hit_id")
    @classmethod
    def validate_hit_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "hit")

    def to_evidence(self, confidence: float = 0.75) -> EvidenceAnchor:
        return EvidenceAnchor(
            evidence_id=self.hit_id.replace("hit_", "ev_", 1),
            source_type=self.source_type,
            source_id=self.source_id,
            page=self.page,
            section=self.section,
            artifact_id=self.artifact_id,
            quote=self.quote,
            confidence=min(1.0, max(0.0, confidence)),
            evidence_level=EvidenceLevel.B,
        )


class Claim(PrefixModel):
    claim_id: str
    paper_id: str
    text: str
    claim_type: ClaimType
    evidence: list[EvidenceAnchor] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "claim")

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "paper")


class PaperSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    contribution_bullets: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GateStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_name: str
    state: GateState = GateState.NOT_RUN
    message: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Issue(PrefixModel):
    issue_id: str
    title: str
    severity: IssueSeverity
    dimension: str
    description: str
    affected_claim_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceAnchor] = Field(default_factory=list)
    counter_evidence: list[EvidenceAnchor] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_fix: str
    confidence: float = Field(ge=0.0, le=1.0)
    verified_by: list[str] = Field(default_factory=list)
    gate_status: list[GateStatus] = Field(default_factory=list)

    @field_validator("issue_id")
    @classmethod
    def validate_issue_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "issue")


class AgentRun(PrefixModel):
    agent_run_id: str
    job_id: str
    agent_name: str
    prompt_version: str | None = None
    model_name: str | None = None
    input_hash: str | None = None
    output_schema: str | None = None
    output_json_uri: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_estimate: float | None = Field(default=None, ge=0.0)
    status: AgentRunStatus = AgentRunStatus.PENDING
    warnings: list[str] = Field(default_factory=list)

    @field_validator("agent_run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "run")

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "job")


class QuestionNode(PrefixModel):
    question_id: str
    claim_id: str | None = None
    question: str
    dimension: str
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "question")


class EvidenceAnswer(PrefixModel):
    answer_id: str
    question_id: str
    answer: EvidenceAnswerState
    rationale: str
    evidence: list[EvidenceAnchor] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("answer_id")
    @classmethod
    def validate_answer_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "answer")

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "question")


class IssueStoreSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[Issue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LocalAuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: PaperSummary | None = None
    claims: list[Claim] = Field(default_factory=list)
    questions: list[QuestionNode] = Field(default_factory=list)
    evidence_answers: list[EvidenceAnswer] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    agent_runs: list[AgentRun] = Field(default_factory=list)
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SectionDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)


class PaperUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    global_summary: str
    core_contributions: list[str] = Field(default_factory=list)
    method_overview: str | None = None
    experiment_overview: str | None = None
    main_claims: list[str] = Field(default_factory=list)
    section_digests: list[SectionDigest] = Field(default_factory=list)
    potential_review_concerns: list[str] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    source: Literal["llm", "deterministic"] = "deterministic"


class PaperMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = Field(default=None, ge=1000, le=3000)
    doi: str | None = None


class ParserProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_parser: ParserSource
    source_id: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class SectionNode(PrefixModel):
    section_id: str
    title: str
    normalized_title: str
    level: int = Field(default=1, ge=1)
    parent_id: str | None = None
    source: ParserSource = ParserSource.FUSION
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    block_ids: list[str] = Field(default_factory=list)

    @field_validator("section_id")
    @classmethod
    def validate_section_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "sec")


class PaperBlock(PrefixModel):
    block_id: str
    block_type: PaperBlockType
    section_id: str | None = None
    text: str
    markdown: str | None = None
    source_parser: ParserSource
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    provenance: ParserProvenance

    @field_validator("block_id")
    @classmethod
    def validate_block_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "block")


class EquationBlock(PrefixModel):
    equation_id: str
    latex: str
    label: str | None = None
    number: str | None = None
    section_id: str | None = None
    source_parser: ParserSource
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("equation_id")
    @classmethod
    def validate_equation_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "equation")


class TableArtifactV2(PrefixModel):
    table_id: str
    label: str | None = None
    caption: str | None = None
    markdown: str | None = None
    html: str | None = None
    cells: list[list[str]] = Field(default_factory=list)
    section_id: str | None = None
    source_parser: ParserSource
    repair_status: str = "unrepaired"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("table_id")
    @classmethod
    def validate_table_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "table")


class FigureArtifactV2(PrefixModel):
    figure_id: str
    label: str | None = None
    caption: str | None = None
    image_path: str | None = None
    section_id: str | None = None
    source_parser: ParserSource
    caption_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("figure_id")
    @classmethod
    def validate_figure_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "figure")


class ReferenceRecord(PrefixModel):
    bib_id: str
    raw: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1000, le=3000)
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    citation_markers: list[str] = Field(default_factory=list)

    @field_validator("bib_id")
    @classmethod
    def validate_bib_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "bib")


class CitationContext(PrefixModel):
    citation_id: str
    marker: str
    bib_id: str | None = None
    section_id: str | None = None
    context: str
    source_parser: ParserSource = ParserSource.GROBID
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("citation_id")
    @classmethod
    def validate_citation_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "citation")


class PaperAssetInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figures: list[FigureArtifactV2] = Field(default_factory=list)
    tables: list[TableArtifactV2] = Field(default_factory=list)
    equations: list[EquationBlock] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)


class ParseReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_based_pdf: TextBasedPdfStatus = TextBasedPdfStatus.TEXT_BASED
    page_count: int = Field(default=0, ge=0)
    parsed_pages: int = Field(default=0, ge=0)
    section_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    reference_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    table_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    figure_caption_alignment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    equation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    parser_profile: ParserProfile = ParserProfile.RESEARCH_DEFAULT
    parser_sources: list[ParserSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PaperIR(PrefixModel):
    paper_id: str
    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    abstract: str | None = None
    sections: list[SectionNode] = Field(default_factory=list)
    blocks: list[PaperBlock] = Field(default_factory=list)
    references: list[ReferenceRecord] = Field(default_factory=list)
    citations: list[CitationContext] = Field(default_factory=list)
    assets: PaperAssetInventory = Field(default_factory=PaperAssetInventory)
    parse_report: ParseReport = Field(default_factory=ParseReport)

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "paper")


class ReportTrace(PrefixModel):
    report_id: str
    job_id: str
    format: str
    section_key: str
    source_issue_ids: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    source_agent_run_ids: list[str] = Field(default_factory=list)
    generated_text_hash: str | None = None
    gate_status_snapshot: list[GateStatus] = Field(default_factory=list)

    @field_validator("report_id")
    @classmethod
    def validate_report_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "report")

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "job")


class JobRecord(PrefixModel):
    job_id: str
    status: JobStatus
    config: JobConfig
    upload_path: Path
    paper_ir_path: Path | None = None
    canonical_markdown_path: Path | None = None
    parse_report_path: Path | None = None
    trace_path: Path | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        return cls._validate_prefix(value, "job")


class ParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_document: PaperDocument
    paper_ir: PaperIR | None = None
    artifacts: dict[str, list[PaperArtifact]] = Field(default_factory=dict)
    references: list[Reference] = Field(default_factory=list)
    parse_confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    provider: str


class PaperTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    job: JobRecord
    parser_provider: str
    job_config: JobConfig
    paper_document: PaperDocument
    paper_ir: PaperIR | None = None
    generated_files: dict[str, str]
    warnings: list[str] = Field(default_factory=list)
    paper_understanding: PaperUnderstanding | None = None
    summary: PaperSummary | None = None
    claims: list[Claim] = Field(default_factory=list)
    questions: list[QuestionNode] = Field(default_factory=list)
    evidence_answers: list[EvidenceAnswer] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    agent_runs: list[AgentRun] = Field(default_factory=list)
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
