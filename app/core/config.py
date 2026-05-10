from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelProfile(BaseSettings):
    provider: str = "openai_compatible"
    model: str = "deepseek-v4-pro"
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_REVIEWER_", env_file=".env", extra="ignore")

    object_storage_path: Path = Field(default=Path("var"))
    parser_provider: str = "paper_ir_ensemble"
    parser_profile: str = "research_default"
    grobid_base_url: str = "http://127.0.0.1:8070"
    grobid_timeout_seconds: float = 30.0
    marker_enabled: bool = True
    marker_output_format: str = "json"
    marker_timeout_seconds: float = 120.0
    marker_quick_page_limit: int | None = None
    marker_disable_image_extraction: bool = True
    marker_low_memory_mode: bool = True
    pdffigures2_command: str = "pdffigures2"
    pdffigures2_enabled: bool = True
    parser_assets_dir: str = "assets"
    schema_version: str = "paper_ir.v0.2"
    default_review_mode: str = "quick_audit"
    llm_profile: ModelProfile = Field(default_factory=ModelProfile)
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str | None = None
    llm_model: str = "deepseek-v4-pro"
    llm_timeout_seconds: float = 120.0
    llm_reasoning_effort: str | None = "high"
    llm_thinking_enabled: bool = True
    llm_input_char_limit: int = 24000


@lru_cache
def get_settings() -> Settings:
    return Settings()
