from functools import lru_cache

from llama_index.core.llms import LLM

from app.config import Settings, get_settings


def _build_llm(settings: Settings) -> LLM:
    provider = settings.llm_provider

    if provider == "openai":
        from llama_index.llms.openai import OpenAI

        return OpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key,
        )

    if provider == "anthropic":
        from llama_index.llms.anthropic import Anthropic

        return Anthropic(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.anthropic_api_key,
        )

    if provider == "gemini":
        from llama_index.llms.google_genai import GoogleGenAI

        return GoogleGenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.google_api_key,
        )

    if provider == "groq":
        from llama_index.llms.groq import Groq

        return Groq(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.groq_api_key,
        )

    if provider == "openrouter":
        from llama_index.llms.openrouter import OpenRouter

        return OpenRouter(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openrouter_api_key,
            api_base=settings.openrouter_base_url,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")


@lru_cache
def get_llm() -> LLM:
    return _build_llm(get_settings())
