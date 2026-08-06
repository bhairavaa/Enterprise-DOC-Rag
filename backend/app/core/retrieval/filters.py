from dataclasses import dataclass

from llama_index.core.vector_stores.types import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)


@dataclass
class SearchFilters:
    """tenant_id is mandatory (hard multi-tenant isolation boundary);
    department/doc_type/tags are optional facets scoped within a tenant.
    Auth-based scope intersection (Phase 5) constructs this from the
    caller's allowed facets ∩ their requested filters."""

    tenant_id: str
    department: list[str] | None = None
    doc_type: list[str] | None = None
    tags: list[str] | None = None


def build_metadata_filters(search_filters: SearchFilters) -> MetadataFilters:
    """Native Qdrant filter for the dense retriever."""
    filters: list[MetadataFilter] = [
        MetadataFilter(key="tenant_id", value=search_filters.tenant_id, operator=FilterOperator.EQ)
    ]
    if search_filters.department:
        filters.append(
            MetadataFilter(
                key="department", value=search_filters.department, operator=FilterOperator.IN
            )
        )
    if search_filters.doc_type:
        filters.append(
            MetadataFilter(
                key="doc_type", value=search_filters.doc_type, operator=FilterOperator.IN
            )
        )
    if search_filters.tags:
        filters.append(
            MetadataFilter(key="tags", value=search_filters.tags, operator=FilterOperator.ANY)
        )
    return MetadataFilters(filters=filters, condition=FilterCondition.AND)


def node_matches_filters(node_metadata: dict, search_filters: SearchFilters) -> bool:
    """Post-hoc equivalent for BM25, which has no native payload filtering
    (bm25s indexes text only)."""
    if node_metadata.get("tenant_id") != search_filters.tenant_id:
        return False
    if search_filters.department and node_metadata.get("department") not in search_filters.department:
        return False
    if search_filters.doc_type and node_metadata.get("doc_type") not in search_filters.doc_type:
        return False
    if search_filters.tags:
        node_tags = node_metadata.get("tags") or []
        if not set(node_tags) & set(search_filters.tags):
            return False
    return True
