from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.schema import BaseNode, Document

from app.config import get_settings


def _exclude_all_metadata_from_text_views(document: Document) -> None:
    """Metadata is payload-only: filterable via `.metadata` (Qdrant
    payload/BM25 post-filter), but never rendered into the text views used
    for embedding, reranking, or context compression.

    This matters more than it looks: SentenceEmbeddingOptimizer (context
    compression) naively sentence-splits whatever `get_content(metadata_mode
    =LLM)` returns and then calls `node.set_content()` with only the
    "top" sentences it keeps — for small chunks, metadata lines like
    "section_title: Purpose" can score as relevant as real sentences and
    get baked permanently into the node's text. Citation-relevant fields
    (source_file, page_label, ...) are attached explicitly from
    `node.metadata` when building citations/prompts (see
    app/core/retrieval/citations.py), not via implicit text templating.
    """
    for key in document.metadata:
        if key not in document.excluded_llm_metadata_keys:
            document.excluded_llm_metadata_keys.append(key)
        if key not in document.excluded_embed_metadata_keys:
            document.excluded_embed_metadata_keys.append(key)


def build_hierarchical_nodes(documents: list[Document]) -> tuple[list[BaseNode], list[BaseNode]]:
    """Parent-child chunking: returns (all_nodes, leaf_nodes).

    All nodes (leaf + parent) must be stored in the docstore, since
    AutoMergingRetriever needs the full hierarchy to resolve a leaf's
    ancestors. Only leaf_nodes are embedded and written to the vector store
    / BM25 index — they're what's actually searched.
    """
    settings = get_settings()
    for document in documents:
        _exclude_all_metadata_from_text_views(document)

    parser = HierarchicalNodeParser.from_defaults(chunk_sizes=settings.chunk_sizes_list)
    all_nodes = parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(all_nodes)
    return all_nodes, leaf_nodes
