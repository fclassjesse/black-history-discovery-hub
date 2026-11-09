"""Runtime configuration. Everything comes from the environment / .env; nothing secret lives in code."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
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

    # --- Public deployment guards -----------------------------------------
    # AI-written answers per UTC day (0 = unlimited); over the cap Nova still shows the matching records.
    guide_daily_limit: int = 300
    guide_daily_limit_per_visitor: int = 30
    trust_proxy_headers: bool = True  # the API sits behind the Next.js proxy, which sets X-Forwarded-For
    search_log_retention_days: int = 30  # search/guide questions are deleted after this many days (0 = keep)

    # --- Files / jobs ----------------------------------------------------
    upload_dir: Path = BACKEND_ROOT / "uploads"
    jobs_inline: bool = True
    # inline jobs run after the response is sent, so a slow vision call never holds the upload request open
    # (the Next.js dev proxy gives up after ~30 s and shows a 500). Tests set this false to await the result.
    jobs_inline_background: bool = True
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        """Refuse to start a public deployment with the development secrets."""
        if not self.is_production:
            return self
        problems = []
        if self.jwt_secret in ("", "dev-only-change-me") or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a random value of at least 32 characters (python -c 'import secrets; print(secrets.token_urlsafe(48))')")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (the site is served over HTTPS)")
        if "localhost" in self.cors_origins or "localhost" in self.public_base_url:
            problems.append("CORS_ORIGINS and PUBLIC_BASE_URL must be the public https address, not localhost")
        if problems:
            raise ValueError("Unsafe production settings:\n- " + "\n- ".join(problems))
        return self

    @property
    def _pg_url(self) -> str:
        # hosts (Render, Heroku) may hand out the short "postgres://" scheme
        url = self.database_url
        return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url

    @property
    def async_database_url(self) -> str:
        return self._pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def sync_database_url(self) -> str:
        return self._pg_url.replace("postgresql://", "postgresql+psycopg://", 1)

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
