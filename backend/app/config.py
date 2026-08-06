from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to this file's location (backend/app/config.py -> repo root),
# not CWD — CWD varies (backend/ for pytest/uvicorn, repo root for docker
# compose), and a CWD-relative path silently misses the file from some of
# them, falling back to defaults instead of erroring. Inside Docker this
# path simply won't exist (docker-compose injects real env vars instead),
# which pydantic-settings tolerates.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- Postgres ---
    database_url: str = "postgresql+asyncpg://rag_user:change_me@localhost:5432/enterprise_rag"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_prefix: str = "enterprise_docs"

    # --- LLM provider ---
    llm_provider: Literal["openai", "anthropic", "gemini", "groq", "openrouter"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    """Explicit and provider-agnostic on purpose: each LlamaIndex LLM class
    has its own inconsistent implicit default when this isn't set (OpenAI/
    Gemini effectively uncapped, Anthropic 512, OpenRouter only 256) --
    256 tokens is enough to truncate a multi-source cited answer mid-
    sentence. Passed explicitly to every provider in llm_factory.py so
    behavior is the same and predictable regardless of LLM_PROVIDER."""

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Embedding provider ---
    embedding_provider: Literal["openai", "gemini", "huggingface"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- Reranker ---
    reranker_enabled: bool = True
    """Local BGE reranking loads a real cross-encoder model into memory —
    set false for lightweight local dev/laptop work. The rest of the
    pipeline (hybrid retrieval, compression, citations) works unaffected;
    only the rerank step of build_postprocessors() is skipped."""
    reranker_provider: Literal["bge", "cohere"] = "bge"
    reranker_model: str = "BAAI/bge-reranker-base"
    rerank_top_n: int = 5
    cohere_api_key: str | None = None

    # --- Retrieval tuning ---
    hybrid_top_k: int = 20
    query_rewrite_enabled: bool = True
    num_query_variations: int = 3
    auto_merge_threshold: float = 0.5

    # --- Chunking ---
    chunk_sizes: str = "2048,512,128"
    """Comma-separated parent->child token sizes for HierarchicalNodeParser,
    largest first. Only the smallest (leaf) size is embedded/searched."""

    # --- Context compression ---
    context_compression_enabled: bool = True
    context_compression_percentile_cutoff: float = 0.5
    """Keeps the top N% most query-relevant sentences per node (via
    SentenceEmbeddingOptimizer), trimming prompt tokens without discarding
    whole chunks the way a stricter top-k cut would."""

    # --- Uploads ---
    upload_dir: str = "storage/uploads"

    # --- BM25 ---
    bm25_index_dir: str = "storage/bm25_index"
    """Rebuilt from scratch after every ingestion run (bm25s has no
    incremental update API) — see app/ingestion/bm25_index.py."""

    # --- Semantic cache ---
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.96
    semantic_cache_ttl_seconds: int = 86400

    # --- Observability ---
    phoenix_enabled: bool = True
    phoenix_collector_endpoint: str = "http://localhost:6006"

    # --- Auth ---
    admin_bootstrap_api_key: str = "change_me_admin_key"

    # --- Rate limiting ---
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    """Fixed-window counter, per API key, per endpoint (chat/search tracked
    separately) — see app/core/security/rate_limit.py. Redis-backed (reuses
    the same Redis instance as Celery), so limits hold across multiple API
    replicas, not just per-process."""

    @property
    def embedding_collection_name(self) -> str:
        """Encode embedding identity in the collection name so a provider/model
        swap after indexing fails loudly (collection not found) instead of
        silently mixing incompatible vector spaces."""
        safe_model = self.embedding_model.replace("/", "_").replace(":", "_")
        return f"{self.qdrant_collection_prefix}__{self.embedding_provider}_{safe_model}"

    @property
    def chunk_sizes_list(self) -> list[int]:
        return [int(size.strip()) for size in self.chunk_sizes.split(",") if size.strip()]

    @property
    def semantic_cache_collection_name(self) -> str:
        return f"semantic_cache__{self.embedding_provider}_{self.embedding_model.replace('/', '_')}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
