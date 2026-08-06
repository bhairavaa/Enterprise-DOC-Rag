from llama_index.core.vector_stores.types import FilterOperator

from app.core.retrieval.filters import SearchFilters, build_metadata_filters, node_matches_filters


def test_build_metadata_filters_always_includes_tenant_id():
    filters = build_metadata_filters(SearchFilters(tenant_id="acme"))

    assert len(filters.filters) == 1
    assert filters.filters[0].key == "tenant_id"
    assert filters.filters[0].value == "acme"
    assert filters.filters[0].operator == FilterOperator.EQ


def test_build_metadata_filters_includes_optional_facets():
    filters = build_metadata_filters(
        SearchFilters(tenant_id="acme", department=["engineering"], doc_type=["policies"], tags=["hr"])
    )

    keys = {f.key for f in filters.filters}
    assert keys == {"tenant_id", "department", "doc_type", "tags"}


def test_node_matches_filters_enforces_tenant_isolation():
    search_filters = SearchFilters(tenant_id="acme")

    assert node_matches_filters({"tenant_id": "acme"}, search_filters) is True
    assert node_matches_filters({"tenant_id": "globex"}, search_filters) is False


def test_node_matches_filters_department_facet():
    search_filters = SearchFilters(tenant_id="acme", department=["engineering", "legal"])

    assert node_matches_filters({"tenant_id": "acme", "department": "engineering"}, search_filters) is True
    assert node_matches_filters({"tenant_id": "acme", "department": "hr"}, search_filters) is False


def test_node_matches_filters_tags_any_overlap():
    search_filters = SearchFilters(tenant_id="acme", tags=["hr", "onboarding"])

    assert (
        node_matches_filters({"tenant_id": "acme", "tags": ["onboarding", "benefits"]}, search_filters)
        is True
    )
    assert node_matches_filters({"tenant_id": "acme", "tags": ["benefits"]}, search_filters) is False
    assert node_matches_filters({"tenant_id": "acme", "tags": []}, search_filters) is False
