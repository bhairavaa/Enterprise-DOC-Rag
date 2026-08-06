import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.core.providers.embedding_factory import get_embed_model, get_embedding_dimension
from app.core.retrieval.filters import SearchFilters
from app.core.retrieval.qdrant_store import ensure_collection, get_qdrant_client
from app.schemas.citation import Citation


@dataclass
class CacheEntry:
    answer: str
    citations: list[Citation]


def _filter_scope_key(search_filters: SearchFilters) -> str:
    """A cache hit must match not just a similar question but the exact
    access scope it was answered under — otherwise a cached answer
    generated for one department/tag filter could leak into a request
    scoped differently."""
    return json.dumps(
        {
            "department": sorted(search_filters.department or []),
            "doc_type": sorted(search_filters.doc_type or []),
            "tags": sorted(search_filters.tags or []),
        },
        sort_keys=True,
    )


def lookup(question: str, search_filters: SearchFilters) -> CacheEntry | None:
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return None

    client = get_qdrant_client()
    collection = settings.semantic_cache_collection_name
    if not client.collection_exists(collection):
        return None

    query_vector = get_embed_model().get_query_embedding(question)
    scope_key = _filter_scope_key(search_filters)

    response = client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="tenant_id", match=qmodels.MatchValue(value=search_filters.tenant_id)
                ),
                qmodels.FieldCondition(
                    key="filter_scope", match=qmodels.MatchValue(value=scope_key)
                ),
            ]
        ),
        limit=1,
        score_threshold=settings.semantic_cache_threshold,
    )

    if not response.points:
        return None

    payload = response.points[0].payload
    if datetime.fromisoformat(payload["expires_at"]) < datetime.now(UTC):
        return None

    citations = [Citation(**c) for c in payload["citations"]]
    return CacheEntry(answer=payload["answer"], citations=citations)


def store(
    question: str,
    answer: str,
    citations: list[Citation],
    search_filters: SearchFilters,
    source_document_ids: list[str],
) -> None:
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return

    client = get_qdrant_client()
    collection = settings.semantic_cache_collection_name
    ensure_collection(client, collection, get_embedding_dimension())

    query_vector = get_embed_model().get_query_embedding(question)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.semantic_cache_ttl_seconds)

    client.upsert(
        collection_name=collection,
        points=[
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=query_vector,
                payload={
                    "question": question,
                    "answer": answer,
                    "citations": [c.model_dump() for c in citations],
                    "tenant_id": search_filters.tenant_id,
                    "filter_scope": _filter_scope_key(search_filters),
                    "source_document_ids": source_document_ids,
                    "created_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
            )
        ],
    )


def invalidate_for_document(document_id: str) -> None:
    """Purges cache entries whose citations referenced a document that just
    changed version or was deleted — called from
    app/ingestion/pipeline.py/registry_sync.py. More correct than relying on
    the TTL alone, which would happily serve stale answers for up to a full
    TTL window after the cited document changed."""
    settings = get_settings()
    client = get_qdrant_client()
    collection = settings.semantic_cache_collection_name
    if not client.collection_exists(collection):
        return

    client.delete(
        collection_name=collection,
        points_selector=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="source_document_ids", match=qmodels.MatchAny(any=[document_id])
                )
            ]
        ),
    )
