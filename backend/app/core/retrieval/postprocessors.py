from llama_index.core.postprocessor import LongContextReorder, SentenceEmbeddingOptimizer
from llama_index.core.postprocessor.types import BaseNodePostprocessor

from app.config import get_settings
from app.core.providers.embedding_factory import get_embed_model
from app.core.providers.reranker_factory import get_reranker
from app.core.retrieval.dedup import DeduplicateSentencesPostprocessor


def build_postprocessors() -> list[BaseNodePostprocessor]:
    """Applied in order after retrieval+merge: rerank cuts the fused
    candidate set down to the most relevant few, context compression trims
    each surviving node to its most query-relevant sentences (reducing
    prompt tokens without discarding whole chunks), sentence dedup removes
    repeats left by AutoMergingRetriever/compression overlap (KNOWN_ISSUES.md
    #1) -- unconditional since the overlap can happen even with both toggles
    off -- and reordering mitigates "lost in the middle" right before the
    final prompt is built.
    """
    settings = get_settings()
    postprocessors: list[BaseNodePostprocessor] = []

    if settings.reranker_enabled:
        postprocessors.append(get_reranker())

    if settings.context_compression_enabled:
        postprocessors.append(
            SentenceEmbeddingOptimizer(
                embed_model=get_embed_model(),
                percentile_cutoff=settings.context_compression_percentile_cutoff,
            )
        )

    postprocessors.append(DeduplicateSentencesPostprocessor())
    postprocessors.append(LongContextReorder())
    return postprocessors
