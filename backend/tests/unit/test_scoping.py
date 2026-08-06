import pytest
from fastapi import HTTPException

from app.core.security.scoping import resolve_scoped_filters
from app.models.api_key import ApiKey


def _api_key(tenant_id="acme", allowed_filters=None) -> ApiKey:
    return ApiKey(tenant_id=tenant_id, name="test", key_hash="x", key_prefix="edr_x", allowed_filters=allowed_filters or {})


def test_unrestricted_key_passes_through_requested_filters():
    key = _api_key()
    filters = resolve_scoped_filters(key, department=["engineering"], doc_type=None, tags=None)

    assert filters.tenant_id == "acme"
    assert filters.department == ["engineering"]


def test_tenant_id_always_comes_from_the_key_never_the_request():
    key = _api_key(tenant_id="globex")
    filters = resolve_scoped_filters(key, department=None, doc_type=None, tags=None)

    assert filters.tenant_id == "globex"


def test_restricted_key_omitting_filter_gets_full_allowed_set_injected():
    """Omitting a filter must not be usable to bypass scope — the caller
    should see exactly what they're allowed to, not everything."""
    key = _api_key(allowed_filters={"department": ["engineering", "legal"]})
    filters = resolve_scoped_filters(key, department=None, doc_type=None, tags=None)

    assert filters.department == ["engineering", "legal"]


def test_restricted_key_requesting_within_allowed_set_succeeds():
    key = _api_key(allowed_filters={"department": ["engineering", "legal"]})
    filters = resolve_scoped_filters(key, department=["engineering"], doc_type=None, tags=None)

    assert filters.department == ["engineering"]


def test_restricted_key_requesting_outside_allowed_set_is_rejected():
    key = _api_key(allowed_filters={"department": ["engineering"]})

    with pytest.raises(HTTPException) as exc_info:
        resolve_scoped_filters(key, department=["hr"], doc_type=None, tags=None)

    assert exc_info.value.status_code == 403


def test_restriction_on_one_facet_does_not_affect_others():
    key = _api_key(allowed_filters={"department": ["engineering"]})
    filters = resolve_scoped_filters(key, department=["engineering"], doc_type=["policies"], tags=None)

    assert filters.doc_type == ["policies"]
