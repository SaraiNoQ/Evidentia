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
    parser_provider: str = "pymupdf"
    schema_version: str = "paper_ir.v0.1"
    default_review_mode: str = "quick_audit"
    llm_profile: ModelProfile = Field(default_factory=ModelProfile)


@lru_cache
def get_settings() -> Settings:
    return Settings()
