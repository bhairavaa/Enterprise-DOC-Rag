import pytest

from app.config import Settings
from app.core.providers.embedding_factory import _build_embed_model
from app.core.providers.llm_factory import _build_llm
from app.core.providers.reranker_factory import _build_reranker


def _settings(**overrides) -> Settings:
    defaults = {
        "openai_api_key": "sk-test",
        "anthropic_api_key": "sk-ant-test",
        "google_api_key": "test-google-key",
        "groq_api_key": "gsk-test",
        "openrouter_api_key": "sk-or-test",
        "cohere_api_key": "test-cohere-key",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


@pytest.mark.parametrize(
    ("provider", "expected_class"),
    [
        # gemini is exercised in tests/integration: unlike these four, GoogleGenAI's
        # constructor makes a live network call to validate the API key.
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("groq", "Groq"),
        ("openrouter", "OpenRouter"),
    ],
)
def test_llm_factory_returns_expected_class(provider, expected_class):
    settings = _settings(llm_provider=provider, llm_model="test-model")
    llm = _build_llm(settings)
    assert type(llm).__name__ == expected_class


@pytest.mark.parametrize("provider", ["openai", "anthropic", "groq", "openrouter"])
def test_llm_factory_applies_configured_max_tokens(provider):
    # Each LlamaIndex LLM class has its own inconsistent implicit default
    # when max_tokens isn't passed explicitly (OpenRouter's is only 256 --
    # easily truncates a multi-source cited answer mid-sentence). Must be
    # set explicitly and consistently regardless of provider.
    settings = _settings(llm_provider=provider, llm_model="test-model", llm_max_tokens=4096)
    llm = _build_llm(settings)
    assert llm.max_tokens == 4096


def test_llm_factory_rejects_unknown_provider():
    settings = _settings(llm_provider="openai")
    settings.llm_provider = "made_up_provider"
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        _build_llm(settings)


def test_openai_embedding_factory_returns_expected_class():
    # OpenAIEmbedding validates the model name against a fixed enum of known
    # OpenAI models, so a placeholder name isn't valid here.
    settings = _settings(embedding_provider="openai", embedding_model="text-embedding-3-small")
    embed_model = _build_embed_model(settings)
    assert type(embed_model).__name__ == "OpenAIEmbedding"


def test_embedding_factory_rejects_unsupported_provider():
    settings = _settings()
    settings.embedding_provider = "anthropic"
    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
        _build_embed_model(settings)


def test_reranker_factory_returns_expected_class_for_api_provider():
    settings = _settings(reranker_provider="cohere", reranker_model="rerank-english-v3.0")
    reranker = _build_reranker(settings)
    assert type(reranker).__name__ == "CohereRerank"
