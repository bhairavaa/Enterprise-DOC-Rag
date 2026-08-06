from functools import lru_cache

from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings

# Indexed for fast filtered search — tenant_id is the hard multi-tenant
# isolation boundary, department/doc_type are the facets scoped within it.
PAYLOAD_INDEX_FIELDS = ["tenant_id", "department", "doc_type"]


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


@lru_cache
def get_async_qdrant_client() -> AsyncQdrantClient:
    """Needed alongside the sync client because QueryFusionRetriever fans
    out to each sub-retriever concurrently via aretrieve() — without an
    async client, QdrantVectorStore.aquery() raises rather than falling
    back to the sync one."""
    settings = get_settings()
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    """Idempotent: creates the collection + payload indexes only if the
    collection doesn't already exist."""
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )
    for field in PAYLOAD_INDEX_FIELDS:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )


def get_vector_store(collection_name: str) -> QdrantVectorStore:
    return QdrantVectorStore(
        collection_name=collection_name,
        client=get_qdrant_client(),
        aclient=get_async_qdrant_client(),
    )
