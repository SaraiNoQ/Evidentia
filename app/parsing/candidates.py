from pydantic import BaseModel, ConfigDict, Field

from app.core.models import (
    CitationContext,
    FigureArtifactV2,
    PaperBlock,
    PaperMetadata,
    ParserSource,
    ReferenceRecord,
    SectionNode,
    TableArtifactV2,
)


class GrobidParseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    abstract: str | None = None
    sections: list[SectionNode] = Field(default_factory=list)
    references: list[ReferenceRecord] = Field(default_factory=list)
    citations: list[CitationContext] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: ParserSource = ParserSource.GROBID


class MarkerParseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str | None = None
    blocks: list[PaperBlock] = Field(default_factory=list)
    tables: list[TableArtifactV2] = Field(default_factory=list)
    figures: list[FigureArtifactV2] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: ParserSource = ParserSource.MARKER


class Pdffigures2ParseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figures: list[FigureArtifactV2] = Field(default_factory=list)
    tables: list[TableArtifactV2] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: ParserSource = ParserSource.PDFFIGURES2
