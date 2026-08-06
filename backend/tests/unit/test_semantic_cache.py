from app.core.cache.semantic_cache import _filter_scope_key
from app.core.retrieval.filters import SearchFilters


def test_filter_scope_key_is_order_independent():
    a = SearchFilters(tenant_id="acme", department=["engineering", "legal"])
    b = SearchFilters(tenant_id="acme", department=["legal", "engineering"])

    assert _filter_scope_key(a) == _filter_scope_key(b)


def test_filter_scope_key_differs_across_scopes():
    a = SearchFilters(tenant_id="acme", department=["engineering"])
    b = SearchFilters(tenant_id="acme", department=["legal"])
    c = SearchFilters(tenant_id="acme")

    keys = {_filter_scope_key(a), _filter_scope_key(b), _filter_scope_key(c)}
    assert len(keys) == 3


def test_filter_scope_key_ignores_tenant_id():
    """tenant_id is checked separately as its own Qdrant filter condition —
    the scope key only needs to distinguish facet combinations."""
    a = SearchFilters(tenant_id="acme", department=["engineering"])
    b = SearchFilters(tenant_id="globex", department=["engineering"])

    assert _filter_scope_key(a) == _filter_scope_key(b)
