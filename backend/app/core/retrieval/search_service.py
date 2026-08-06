from llama_index.core.schema import NodeWithScore, QueryBundle

from app.core.retrieval.filters import SearchFilters
from app.core.retrieval.hybrid_retriever import build_hybrid_retriever
from app.core.retrieval.postprocessors import build_postprocessors


def run_search(query: str, search_filters: SearchFilters) -> list[NodeWithScore]:
    """Full retrieval pipeline: hybrid fusion + parent-child merge, then the
    rerank -> compress -> reorder postprocessor chain. Synchronous — the
    embedding/Qdrant/reranker calls underneath are all sync; callers from
    async endpoints should run this via a threadpool (e.g. a plain `def`
    FastAPI route, which Starlette dispatches off the event loop)."""
    retriever = build_hybrid_retriever(search_filters)
    query_bundle = QueryBundle(query_str=query)

    nodes = retriever.retrieve(query_bundle)
    for postprocessor in build_postprocessors():
        nodes = postprocessor.postprocess_nodes(nodes, query_bundle=query_bundle)

    return nodes
