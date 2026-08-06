import uuid

import pytest

from app.core.cache import semantic_cache
from app.core.retrieval.filters import SearchFilters
from app.core.retrieval.qdrant_store import get_qdrant_client
from app.schemas.citation import Citation

pytestmark = pytest.mark.integration


def _tenant() -> str:
    return f"test-tenant-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _cleanup_cache_collection():
    yield
    from app.config import get_settings

    client = get_qdrant_client()
    settings = get_settings()
    if client.collection_exists(settings.semantic_cache_collection_name):
        client.delete_collection(settings.semantic_cache_collection_name)


def test_store_and_lookup_round_trip():
    tenant_id = _tenant()
    filters = SearchFilters(tenant_id=tenant_id)
    citations = [Citation(index=1, text="stipend is $500", source_file="policy.pdf")]

    semantic_cache.store(
        "How much is the home office stipend?",
        "The home office stipend is $500.",
        citations,
        filters,
        source_document_ids=["doc-1"],
    )

    hit = semantic_cache.lookup("How much is the home office stipend?", filters)

    assert hit is not None
    assert hit.answer == "The home office stipend is $500."
    assert hit.citations[0].source_file == "policy.pdf"


def test_lookup_miss_for_unrelated_question():
    tenant_id = _tenant()
    filters = SearchFilters(tenant_id=tenant_id)

    semantic_cache.store(
        "How much is the home office stipend?",
        "The home office stipend is $500.",
        [],
        filters,
        source_document_ids=["doc-1"],
    )

    miss = semantic_cache.lookup("What is the PTO accrual rate?", filters)
    assert miss is None


def test_lookup_scoped_by_filter_facets_not_just_question():
    tenant_id = _tenant()
    scoped_filters = SearchFilters(tenant_id=tenant_id, department=["engineering"])
    different_scope = SearchFilters(tenant_id=tenant_id, department=["hr"])

    semantic_cache.store(
        "How much is the home office stipend?",
        "The home office stipend is $500.",
        [],
        scoped_filters,
        source_document_ids=["doc-1"],
    )

    assert semantic_cache.lookup("How much is the home office stipend?", scoped_filters) is not None
    assert semantic_cache.lookup("How much is the home office stipend?", different_scope) is None


def test_lookup_isolated_by_tenant():
    tenant_a = SearchFilters(tenant_id=_tenant())
    tenant_b = SearchFilters(tenant_id=_tenant())

    semantic_cache.store(
        "How much is the home office stipend?",
        "The home office stipend is $500.",
        [],
        tenant_a,
        source_document_ids=["doc-1"],
    )

    assert semantic_cache.lookup("How much is the home office stipend?", tenant_b) is None


def test_invalidate_for_document_removes_matching_entries():
    tenant_id = _tenant()
    filters = SearchFilters(tenant_id=tenant_id)

    semantic_cache.store(
        "How much is the home office stipend?",
        "The home office stipend is $500.",
        [],
        filters,
        source_document_ids=["doc-1"],
    )
    assert semantic_cache.lookup("How much is the home office stipend?", filters) is not None

    semantic_cache.invalidate_for_document("doc-1")

    assert semantic_cache.lookup("How much is the home office stipend?", filters) is None
