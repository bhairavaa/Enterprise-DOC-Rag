from pathlib import Path

from llama_index.retrievers.bm25 import BM25Retriever

from app.config import get_settings
from app.core.retrieval.qdrant_store import get_vector_store


def rebuild_bm25_index() -> int:
    """Full rebuild from the current Qdrant leaf-node corpus (the vector
    store is the source of truth for "what's currently searchable" — it's
    already kept correct across adds/updates/deletes by the ingestion
    pipeline). bm25s has no incremental update API, so a full rebuild after
    each ingestion run is the documented tradeoff at portfolio scale.
    Returns the number of nodes indexed.
    """
    settings = get_settings()
    vector_store = get_vector_store(settings.embedding_collection_name)
    nodes = vector_store.get_nodes(limit=None)

    index_dir = Path(settings.bm25_index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    if not nodes:
        return 0

    retriever = BM25Retriever.from_defaults(nodes=nodes)
    retriever.persist(str(index_dir))
    return len(nodes)
