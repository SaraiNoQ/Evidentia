import hashlib
import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings
from app.core.ids import new_id
from app.core.llm import LLMRequest, OpenAICompatibleLLMAdapter
from app.core.models import (
    AgentRun,
    AgentRunStatus,
    PaperIR,
    PaperUnderstanding,
    SectionDigest,
)

PROMPT_VERSION = "markdown_understanding.v0.1"


class MarkdownUnderstandingAgent:
    agent_name = "markdown_understanding_agent"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self,
        *,
        job_id: str,
        markdown: str,
        paper_ir: PaperIR | None,
    ) -> tuple[PaperUnderstanding, AgentRun]:
        input_text = self._input_text(markdown, paper_ir)
        input_hash = hashlib.sha256(input_text.encode("utf-8")).hexdigest()[:16]

        if not self.settings.llm_api_key:
            understanding = self._deterministic_understanding(markdown, paper_ir)
            return understanding, self._run_record(
                job_id=job_id,
                model_name="deterministic",
                input_hash=input_hash,
                status=AgentRunStatus.COMPLETED,
                warnings=["llm_api_key_missing_using_deterministic_fallback"],
            )

        adapter = OpenAICompatibleLLMAdapter(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key,
            timeout_seconds=self.settings.llm_timeout_seconds,
        )
        warnings: list[str] = []
        try:
            response = await adapter.complete(
                LLMRequest(
                    model=self.settings.llm_model,
                    messages=self._messages(input_text),
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=1800,
                    reasoning_effort=self.settings.llm_reasoning_effort,
                    thinking_enabled=self.settings.llm_thinking_enabled,
                )
            )
            warnings.extend(response.warnings)
            understanding = self._parse_understanding(response.content, paper_ir)
            run = self._run_record(
                job_id=job_id,
                model_name=response.model,
                input_hash=input_hash,
                status=AgentRunStatus.COMPLETED,
                warnings=warnings,
                token_usage=response.token_usage,
            )
            return understanding, run
        except Exception as exc:  # noqa: BLE001 - fallback keeps parsing jobs usable.
            warnings.append(f"llm_call_failed:{type(exc).__name__}")
            understanding = self._deterministic_understanding(markdown, paper_ir)
            run = self._run_record(
                job_id=job_id,
                model_name=self.settings.llm_model,
                input_hash=input_hash,
                status=AgentRunStatus.COMPLETED,
                warnings=[*warnings, "using_deterministic_fallback"],
            )
            return understanding, run

    def _input_text(self, markdown: str, paper_ir: PaperIR | None) -> str:
        parse_summary = self._parse_summary(paper_ir)
        limited_markdown = markdown[: self.settings.llm_input_char_limit]
        return f"{parse_summary}\n\n<canonical_markdown>\n{limited_markdown}\n</canonical_markdown>"

    def _parse_summary(self, paper_ir: PaperIR | None) -> str:
        if paper_ir is None:
            return "Parse summary unavailable."
        report = paper_ir.parse_report
        sections = [section.title for section in paper_ir.sections[:30]]
        return json.dumps(
            {
                "title": paper_ir.metadata.title,
                "section_count": len(paper_ir.sections),
                "sections": sections,
                "reference_count": len(paper_ir.references),
                "figure_count": len(paper_ir.assets.figures),
                "table_count": len(paper_ir.assets.tables),
                "parser_sources": [source.value for source in report.parser_sources],
                "parse_warnings": report.warnings,
            },
            ensure_ascii=False,
        )

    def _messages(self, input_text: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI research-paper understanding agent. Use only the provided "
                    "canonical markdown and parse summary. Return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Read the paper markdown and produce this JSON object with keys: "
                    "global_summary, core_contributions, method_overview, experiment_overview, "
                    "main_claims, section_digests, potential_review_concerns. "
                    "section_digests items must contain section_title, summary, key_points. "
                    "Do not cite or invent external papers.\n\n"
                    f"{input_text}"
                ),
            },
        ]

    def _parse_understanding(self, content: str, paper_ir: PaperIR | None) -> PaperUnderstanding:
        payload = self._json_from_content(content)
        payload["source"] = "llm"
        payload["parse_warnings"] = paper_ir.parse_report.warnings if paper_ir else []
        try:
            return PaperUnderstanding.model_validate(payload)
        except ValidationError:
            fallback = self._deterministic_understanding(content, paper_ir)
            return fallback.model_copy(update={"source": "llm"})

    def _json_from_content(self, content: str) -> dict[str, Any]:
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if match is None:
                raise
            value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("LLM understanding output must be a JSON object.")
        return value

    def _deterministic_understanding(
        self,
        markdown: str,
        paper_ir: PaperIR | None,
    ) -> PaperUnderstanding:
        title = (
            paper_ir.metadata.title
            if paper_ir is not None and paper_ir.metadata.title
            else "Untitled paper"
        )
        abstract = self._extract_section(markdown, "Abstract") or markdown[:900]
        contributions = self._extract_contribution_bullets(markdown)
        section_digests = []
        if paper_ir:
            for section in paper_ir.sections[:8]:
                section_digests.append(
                    SectionDigest(
                        section_title=section.title,
                        summary=self._section_preview(markdown, section.title),
                        key_points=[],
                    )
                )
        return PaperUnderstanding(
            global_summary=f"{title}. {abstract[:900]}".strip(),
            core_contributions=contributions[:6],
            method_overview=self._extract_section(markdown, "METHOD")
            or self._extract_section(markdown, "SYSTEM MODEL"),
            experiment_overview=self._extract_section(markdown, "EXPERIMENT"),
            main_claims=contributions[:8],
            section_digests=section_digests,
            potential_review_concerns=[
                "Verify whether the claimed contributions are fully supported by experiments.",
                "Check whether baselines, datasets, hyperparameters and ablations are complete.",
            ],
            parse_warnings=paper_ir.parse_report.warnings if paper_ir else [],
            source="deterministic",
        )

    def _extract_contribution_bullets(self, markdown: str) -> list[str]:
        patterns = [
            r"(?im)^\s*(?:[-*]|\d+[.)])\s+(.*(?:propos|introduc|develop|show|demonstrat).*)$",
            r"(?i)(we\s+(?:propose|introduce|develop|show|demonstrate)[^.]{20,260}\.)",
        ]
        bullets: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, markdown):
                candidate = " ".join(match.group(1).split())
                if candidate and candidate not in bullets:
                    bullets.append(candidate)
        return bullets or ["No explicit contribution bullets were detected in the markdown."]

    def _extract_section(self, markdown: str, title_fragment: str) -> str | None:
        escaped = re.escape(title_fragment)
        match = re.search(
            rf"(?ims)^##+\s+[^\n]*{escaped}[^\n]*\n(.*?)(?=^##+\s+|\Z)",
            markdown,
        )
        if match is None:
            return None
        return " ".join(match.group(1).split())[:1200] or None

    def _section_preview(self, markdown: str, title: str) -> str:
        body = self._extract_section(markdown, title)
        return body[:500] if body else "No section preview available from canonical markdown."

    def _run_record(
        self,
        *,
        job_id: str,
        model_name: str,
        input_hash: str,
        status: AgentRunStatus,
        warnings: list[str],
        token_usage: dict[str, int] | None = None,
    ) -> AgentRun:
        return AgentRun(
            agent_run_id=new_id("run"),
            job_id=job_id,
            agent_name=self.agent_name,
            prompt_version=PROMPT_VERSION,
            model_name=model_name,
            input_hash=input_hash,
            output_schema="PaperUnderstanding",
            status=status,
            warnings=warnings,
            token_usage=token_usage or {},
        )
