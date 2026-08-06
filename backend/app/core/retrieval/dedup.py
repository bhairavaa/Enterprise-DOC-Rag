import re

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import MetadataMode, NodeWithScore, QueryBundle

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def dedupe_sentences(text: str) -> str:
    """Drops repeated sentences from a node's text, preserving first-seen
    order. See KNOWN_ISSUES.md #1: AutoMergingRetriever can surface a parent
    chunk whose text overlaps its own leaf children, and SentenceEmbeddingOptimizer
    reassembles sentences from overlapping source nodes without deduplicating
    them -- both can leave the same sentence repeated in a node's final text.
    """
    seen: set[str] = set()
    kept: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        stripped = sentence.strip()
        if not stripped:
            continue
        key = stripped.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(stripped)
    return " ".join(kept)


class DeduplicateSentencesPostprocessor(BaseNodePostprocessor):
    """Runs unconditionally (not gated by reranker/compression toggles) since
    the duplication can originate purely from AutoMergingRetriever's merge
    step, before either of those run."""

    @classmethod
    def class_name(cls) -> str:
        return "DeduplicateSentencesPostprocessor"

    def _postprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        for node_with_score in nodes:
            node = node_with_score.node
            node.set_content(dedupe_sentences(node.get_content(metadata_mode=MetadataMode.NONE)))
        return nodes
