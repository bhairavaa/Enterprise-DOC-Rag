from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.retrievers import AutoMergingRetriever, QueryFusionRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.storage.storage_context import StorageContext
from llama_index.retrievers.bm25 import BM25Retriever

from app.config import get_settings
from app.core.providers.embedding_factory import get_embed_model
from app.core.providers.llm_factory import get_llm
from app.core.retrieval.docstore import get_docstore
from app.core.retrieval.filters import SearchFilters, build_metadata_filters, node_matches_filters
from app.core.retrieval.qdrant_store import get_vector_store


class FilteredBM25Retriever(BaseRetriever):
    """BM25 has no native payload filtering (bm25s indexes text only, no
    structured metadata predicates like Qdrant's), so tenant/facet scoping
    is applied post-hoc on the nodes it returns."""

    def __init__(self, bm25_retriever: BM25Retriever, search_filters: SearchFilters):
        self._bm25_retriever = bm25_retriever
        self._search_filters = search_filters
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        nodes = self._bm25_retriever.retrieve(query_bundle)
        return [n for n in nodes if node_matches_filters(n.node.metadata, self._search_filters)]


def build_hybrid_retriever(search_filters: SearchFilters) -> BaseRetriever:
    """Composes the full retrieval pipeline:

    1. Dense (Qdrant, natively filtered) + BM25 (post-hoc filtered)
    2. QueryFusionRetriever — reciprocal-rank fusion of both; num_queries>1
       is also where LLM-based query rewriting happens (paraphrased query
       variants, each retrieved and fused in)
    3. AutoMergingRetriever — merges sibling leaf chunks back into their
       parent chunk when enough of them show up in the fused results, per
       the parent-child hierarchy built in app/ingestion/node_parsers.py
    """
    settings = get_settings()

    vector_store = get_vector_store(settings.embedding_collection_name)
    index = VectorStoreIndex.from_vector_store(vector_store, embed_model=get_embed_model())
    dense_retriever = index.as_retriever(
        similarity_top_k=settings.hybrid_top_k,
        filters=build_metadata_filters(search_filters),
    )

    retrievers: list[BaseRetriever] = [dense_retriever]
    bm25_index_dir = Path(settings.bm25_index_dir)
    if bm25_index_dir.exists():
        raw_bm25 = BM25Retriever.from_persist_dir(str(bm25_index_dir))
        # bm25s errors if top_k exceeds the corpus size rather than
        # clamping it itself — always true for small/demo corpora.
        raw_bm25.similarity_top_k = min(settings.hybrid_top_k, len(raw_bm25.corpus))
        retrievers.append(FilteredBM25Retriever(raw_bm25, search_filters))

    fusion_retriever = QueryFusionRetriever(
        retrievers,
        llm=get_llm(),
        similarity_top_k=settings.hybrid_top_k,
        num_queries=settings.num_query_variations if settings.query_rewrite_enabled else 1,
        mode=FUSION_MODES.RECIPROCAL_RANK,
        # Sync, not async: every caller (search_service.run_search,
        # chat/engine.py's _retrieve_and_build_citations) invokes this via
        # the sync .retrieve(), never .aretrieve(). use_async=True still
        # engages here because AutoMergingRetriever/QueryFusionRetriever's
        # sync _retrieve() falls back to bridging into async Qdrant calls on
        # a throwaway event loop. When .retrieve() is called from *within*
        # an already-running loop (chat/engine.py's stream_chat_response is
        # async and calls it inline), that bridge spins up a NEW throwaway
        # loop per call in a background thread -- but the async Qdrant
        # client is a process-wide cached singleton (qdrant_store.py), so
        # its connection pool stays bound to whichever throwaway loop
        # touched it first. The next call's different throwaway loop then
        # tries to reuse those pooled connections and crashes with
        # `RuntimeError: Event loop is closed`. Forcing the sync fan-out
        # path (plain QdrantClient, no event loop juggling) avoids the
        # whole class of bug.
        use_async=False,
    )

    storage_context = StorageContext.from_defaults(docstore=get_docstore())
    return AutoMergingRetriever(
        fusion_retriever, storage_context, simple_ratio_thresh=settings.auto_merge_threshold
    )
