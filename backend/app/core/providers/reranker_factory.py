from functools import lru_cache

from llama_index.core.postprocessor.types import BaseNodePostprocessor

from app.config import Settings, get_settings


def _build_reranker(settings: Settings) -> BaseNodePostprocessor:
    provider = settings.reranker_provider

    if provider == "bge":
        from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank

        return SentenceTransformerRerank(
            model=settings.reranker_model,
            top_n=settings.rerank_top_n,
            # Forces the standard (non meta-device) transformers loading
            # path. The meta-device path (low_cpu_mem_usage=True, the
            # transformers default) hits an intermittent native access
            # violation in torch's memory-mapped state-dict loading on this
            # Windows environment; the classic path avoids that codepath
            # entirely at the cost of a slightly higher peak load memory.
            cross_encoder_kwargs={"model_kwargs": {"low_cpu_mem_usage": False}},
        )

    if provider == "cohere":
        from llama_index.postprocessor.cohere_rerank import CohereRerank

        return CohereRerank(
            model=settings.reranker_model,
            api_key=settings.cohere_api_key,
            top_n=settings.rerank_top_n,
        )

    raise ValueError(f"Unknown RERANKER_PROVIDER: {provider!r}")


@lru_cache
def get_reranker() -> BaseNodePostprocessor:
    return _build_reranker(get_settings())
