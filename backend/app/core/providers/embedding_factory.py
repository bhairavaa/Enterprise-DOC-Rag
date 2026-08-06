from functools import lru_cache

from llama_index.core.base.embeddings.base import BaseEmbedding

from app.config import Settings, get_settings


def _build_embed_model(settings: Settings) -> BaseEmbedding:
    provider = settings.embedding_provider

    if provider == "openai":
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            dimensions=settings.embedding_dimensions,
        )

    if provider == "gemini":
        from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

        return GoogleGenAIEmbedding(
            model_name=settings.embedding_model,
            api_key=settings.google_api_key,
        )

    if provider == "huggingface":
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        return HuggingFaceEmbedding(model_name=settings.embedding_model)

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER: {provider!r}. Note: Anthropic/Groq/OpenRouter don't "
        "serve embeddings APIs, so only openai|gemini|huggingface are supported here."
    )


@lru_cache
def get_embed_model() -> BaseEmbedding:
    return _build_embed_model(get_settings())


@lru_cache
def get_embedding_dimension() -> int:
    """OpenAI's dimension is explicitly configured (settings.embedding_dimensions
    is passed straight to the client), so it's known without a network call.
    Other providers don't expose a dimension knob, so it's discovered by
    embedding a short probe string once."""
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return settings.embedding_dimensions
    return len(get_embed_model().get_text_embedding("dimension probe"))
