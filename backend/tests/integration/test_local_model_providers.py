"""Providers that load real model weights on first use (network + disk cache
required), so they're kept out of the fast unit suite."""

import pytest

from app.config import Settings
from app.core.providers.embedding_factory import _build_embed_model
from app.core.providers.reranker_factory import _build_reranker

pytestmark = pytest.mark.integration


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_huggingface_embedding_factory():
    settings = _settings(embedding_provider="huggingface", embedding_model="BAAI/bge-small-en-v1.5")
    embed_model = _build_embed_model(settings)
    assert type(embed_model).__name__ == "HuggingFaceEmbedding"


def test_bge_reranker_factory():
    settings = _settings(
        reranker_provider="bge", reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    reranker = _build_reranker(settings)
    assert type(reranker).__name__ == "SentenceTransformerRerank"
