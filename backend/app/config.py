"""Runtime configuration. Everything comes from the environment / .env; nothing secret lives in code."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "postgresql://postgres@127.0.0.1:54329/bhdh"
    test_database_url: str = "postgresql://postgres@127.0.0.1:54329/bhdh_test"

    # --- AI providers ---------------------------------------------------
    # PRD default is OpenAI; "auto" picks openai when OPENAI_API_KEY exists,
    # otherwise anthropic when ANTHROPIC_API_KEY exists, otherwise none.
    llm_provider: Literal["auto", "openai", "anthropic", "fake", "none"] = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-6.1-terra"
    openai_vision_model: str = "gpt-6.1-terra"
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    embeddings_provider: Literal["local", "openai", "fake"] = "local"
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- Connector keys --------------------------------------------------
    dpla_api_key: str | None = None
    europeana_api_key: str | None = None
    smithsonian_api_key: str | None = None
    nypl_api_token: str | None = None

    # --- HTTP etiquette --------------------------------------------------
    http_user_agent: str = "BlackHistoryDiscoveryHub/0.1 (hackathon prototype)"
    http_cache_dir: Path = BACKEND_ROOT / ".cache" / "http"
    http_cache_ttl_seconds: int = 7 * 24 * 3600
    http_timeout_seconds: float = 30.0
    reranker: str = "local"  # local (fastembed cross-encoder, keyless) | none
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    guide_cache_ttl_seconds: int = 600
    dal_oai_max_sets: int = 700  # fonds-level GetRecord calls per harvest (1 req/s, cached 7 days)
    dal_oai_max_pages_per_set: int = 3  # ListRecords pages (100 each) read per matching fonds

    # --- Auth ------------------------------------------------------------
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 60 * 12
    cookie_secure: bool = False

    # --- Files / jobs ----------------------------------------------------
    upload_dir: Path = BACKEND_ROOT / "uploads"
    jobs_inline: bool = True
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:3000"

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    @field_validator("openai_api_key", "anthropic_api_key", "dpla_api_key", "europeana_api_key", "smithsonian_api_key", "nypl_api_token", mode="before")
    @classmethod
    def _blank_keys_to_none(cls, v: object) -> object:
        """`DPLA_API_KEY=` (blank) in .env means "not set", not "configured with an empty key"."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        return "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()
