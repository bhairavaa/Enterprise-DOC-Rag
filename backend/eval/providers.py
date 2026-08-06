"""Maps this project's provider settings to ragas's own LLM/embeddings
wrappers, which take native provider SDK clients (openai.OpenAI, anthropic.
Anthropic, ...) rather than the LlamaIndex LLM objects app/core/providers
builds — ragas evaluates with its own client instances, separate from the
app's generation path in app/core/providers/llm_factory.py. The judge model
here defaults to the same provider/model the app itself is configured with;
using a distinct (often stronger) judge model is a common refinement but not
required to get useful signal.
"""

from ragas.embeddings import embedding_factory
from ragas.llms import llm_factory

from app.config import Settings

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_ragas_llm(settings: Settings):
    provider = settings.llm_provider

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        return llm_factory(settings.llm_model, provider="openai", client=client)

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        return llm_factory(settings.llm_model, provider="anthropic", client=client)

    if provider in ("groq", "openrouter"):
        # Both are OpenAI-compatible APIs, so ragas's "openai" adapter works
        # against them directly by pointing the client at their base_url.
        from openai import OpenAI

        if provider == "groq":
            api_key, base_url = settings.groq_api_key, _GROQ_BASE_URL
        else:
            api_key, base_url = settings.openrouter_api_key, settings.openrouter_base_url

        client = OpenAI(api_key=api_key, base_url=base_url)
        return llm_factory(settings.llm_model, provider="openai", client=client)

    raise ValueError(
        f"eval harness has no LLM wiring for LLM_PROVIDER={provider!r} yet "
        "(gemini would need the litellm adapter, not currently a dependency). "
        "Use openai/anthropic/groq/openrouter for evaluation."
    )


def build_ragas_embeddings(settings: Settings):
    if settings.embedding_provider == "huggingface":
        # Runs locally, no API key — same model the app itself embeds with.
        return embedding_factory("huggingface", settings.embedding_model)

    if settings.embedding_provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        return embedding_factory("openai", settings.embedding_model, client=client)

    raise ValueError(
        f"eval harness has no embeddings wiring for EMBEDDING_PROVIDER="
        f"{settings.embedding_provider!r} yet. Use openai/huggingface for evaluation."
    )
