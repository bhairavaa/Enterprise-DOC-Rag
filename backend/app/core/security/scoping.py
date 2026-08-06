from fastapi import HTTPException, status

from app.core.retrieval.filters import SearchFilters
from app.models.api_key import ApiKey


def _scoped_facet(
    requested: list[str] | None, allowed: list[str] | None, facet_name: str
) -> list[str] | None:
    """No entry (or empty list) in the key's allowed_filters means
    unrestricted for that facet. Otherwise: omitting the filter doesn't
    bypass scope (the full allowed set is injected), and requesting any
    value outside the allowed set is rejected outright rather than silently
    dropped — a caller asking for something it can't have should know."""
    if not allowed:
        return requested
    if not requested:
        return list(allowed)

    disallowed = sorted(set(requested) - set(allowed))
    if disallowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key is not authorized for {facet_name}: {disallowed}",
        )
    return requested


def resolve_scoped_filters(
    api_key: ApiKey,
    department: list[str] | None,
    doc_type: list[str] | None,
    tags: list[str] | None,
) -> SearchFilters:
    """tenant_id always comes from the authenticated key — never from client
    input — which is the hard multi-tenant isolation boundary. department/
    doc_type/tags are intersected with the key's allowed_filters."""
    allowed = api_key.allowed_filters or {}
    return SearchFilters(
        tenant_id=api_key.tenant_id,
        department=_scoped_facet(department, allowed.get("department"), "department"),
        doc_type=_scoped_facet(doc_type, allowed.get("doc_type"), "doc_type"),
        tags=_scoped_facet(tags, allowed.get("tags"), "tags"),
    )
