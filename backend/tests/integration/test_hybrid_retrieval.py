"""Exercises the full Phase 2 retrieval pipeline (hybrid fusion + parent-child
merge + rerank + compression + reorder) against the real sample_docs corpus
ingested by app/ingestion/runner.py. Requires that corpus to already be
ingested (see README) — these tests are read-only against it."""

import pytest

from app.core.retrieval.citations import build_citations
from app.core.retrieval.filters import SearchFilters
from app.core.retrieval.search_service import run_search

pytestmark = pytest.mark.integration


def test_retrieves_relevant_result_for_acme_tenant():
    nodes = run_search(
        "How much is the home office stipend for remote employees?",
        SearchFilters(tenant_id="acme"),
    )

    assert len(nodes) > 0
    top_sources = {n.node.metadata.get("source_file") for n in nodes[:2]}
    assert "acme/engineering/policies/remote_work_policy.pdf" in top_sources


def test_tenant_isolation_globex_query_never_returns_acme_documents():
    nodes = run_search("What are the PTO accrual rules?", SearchFilters(tenant_id="globex"))

    assert len(nodes) > 0
    for node_with_score in nodes:
        assert node_with_score.node.metadata.get("tenant_id") == "globex"


def test_department_filter_narrows_results():
    nodes = run_search(
        "policy",
        SearchFilters(tenant_id="acme", department=["engineering"]),
    )

    for node_with_score in nodes:
        assert node_with_score.node.metadata.get("department") == "engineering"


def test_retrieved_text_has_no_metadata_leakage():
    """Regression test: SentenceEmbeddingOptimizer (context compression)
    treats whatever get_content(metadata_mode=LLM) returns as plain prose
    to sentence-split, and previously baked stray metadata lines (e.g.
    "section_title: Purpose") permanently into the node text via
    set_content(). Metadata must now be fully excluded from text views."""
    nodes = run_search("code review approval process", SearchFilters(tenant_id="acme"))

    for node_with_score in nodes:
        text = node_with_score.node.get_content(metadata_mode="none")
        assert "section_title:" not in text
        assert "tenant_id:" not in text
        assert "document_id:" not in text


def test_citations_built_from_search_results():
    nodes = run_search(
        "How much is the home office stipend for remote employees?",
        SearchFilters(tenant_id="acme"),
    )
    citations = build_citations(nodes)

    assert len(citations) == len(nodes)
    assert [c.index for c in citations] == list(range(1, len(citations) + 1))
    assert all(c.source_file is not None for c in citations)
