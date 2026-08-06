from functools import lru_cache

from llama_index.storage.docstore.postgres import PostgresDocumentStore

from app.config import get_settings


@lru_cache
def get_docstore() -> PostgresDocumentStore:
    """Stores every hierarchical node (leaf + parent) keyed by node_id, and
    nodes derived from the same source Document share its ref_doc_id — so
    `delete_ref_doc(document_id)` cleanly purges a whole file's nodes in one
    call when it changes or is removed. Separate from the Qdrant vector
    store: this is node *storage* for AutoMergingRetriever's parent lookups,
    not the search index itself (only leaf nodes are embedded/searched)."""
    settings = get_settings()
    # llama-index's postgres kvstore wants a plain libpq URI, not the
    # SQLAlchemy "+asyncpg" dialect string our own async engine uses.
    uri = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return PostgresDocumentStore.from_uri(uri=uri, namespace="enterprise_doc_rag")
