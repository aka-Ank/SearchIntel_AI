from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SearchIntel AI"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./searchintel.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    allow_local_urls: bool = False
    crawler_user_agent: str = "SearchIntelAI/0.1 (+local-development)"
    crawler_timeout_seconds: float = Field(default=15.0, gt=0)
    crawler_max_response_bytes: int = Field(default=5_000_000, gt=0, le=50_000_000)
    crawler_max_concurrency: int = Field(default=4, gt=0)
    crawler_request_delay_seconds: float = Field(default=0.5, ge=0)
    embedding_provider: str = "deterministic"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = Field(default=64, ge=8, le=4096)
    embedding_version: str = "v1"
    vector_store_provider: str = "memory"
    qdrant_collection: str = "searchintel_chunks"
    bm25_top_k: int = Field(default=20, ge=1, le=200)
    dense_top_k: int = Field(default=20, ge=1, le=200)
    fusion_top_k: int = Field(default=20, ge=1, le=200)
    rerank_top_k: int = Field(default=8, ge=1, le=100)
    reranker_provider: str = "noop"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rag_context_max_chars: int = Field(default=6000, ge=500, le=50000)
    llm_provider: str = "mock"
    auth_secret: SecretStr | None = None
    auth_cookie_secure: bool | None = None
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    auth_token_lifetime_seconds: int = Field(default=3600, ge=300, le=86400)
    auth_login_rate_limit: int = Field(default=10, ge=1, le=1000)
    auth_login_rate_window_seconds: int = Field(default=300, ge=1, le=86400)
    auth_register_rate_limit: int = Field(default=5, ge=1, le=1000)
    auth_register_rate_window_seconds: int = Field(default=3600, ge=1, le=86400)
    crawl_enqueue_rate_limit: int = Field(default=60, ge=1, le=10000)
    crawl_enqueue_rate_window_seconds: int = Field(default=3600, ge=1, le=86400)
    audit_enqueue_rate_limit: int = Field(default=30, ge=1, le=10000)
    audit_enqueue_rate_window_seconds: int = Field(default=3600, ge=1, le=86400)
    llm_model: str = "gpt-4o-mini"
    llm_api_key: SecretStr | None = None
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=180)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_input_cost_per_million: float | None = Field(default=None, ge=0)
    llm_output_cost_per_million: float | None = Field(default=None, ge=0)

    @property
    def secure_auth_cookies(self) -> bool:
        return (
            self.auth_cookie_secure
            if self.auth_cookie_secure is not None
            else self.app_env == "production"
        )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
