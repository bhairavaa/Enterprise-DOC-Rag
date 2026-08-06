from llama_index.core import Document
from llama_index.core.schema import NodeRelationship

from app.ingestion.node_parsers import build_hierarchical_nodes


def _document(text: str, **metadata) -> Document:
    return Document(text=text, metadata=metadata)


def test_leaf_nodes_are_subset_of_all_nodes():
    doc = _document("Sentence one. " * 200, page_label="1", section_title="Intro")
    all_nodes, leaf_nodes = build_hierarchical_nodes([doc])

    assert len(leaf_nodes) <= len(all_nodes)
    leaf_ids = {n.node_id for n in leaf_nodes}
    all_ids = {n.node_id for n in all_nodes}
    assert leaf_ids.issubset(all_ids)


def test_leaf_nodes_carry_parent_relationship_for_auto_merging():
    doc = _document("Sentence one. " * 400, page_label="1", section_title="Intro")
    _, leaf_nodes = build_hierarchical_nodes([doc])

    assert len(leaf_nodes) > 1
    for leaf in leaf_nodes:
        assert NodeRelationship.PARENT in leaf.relationships


def test_source_metadata_propagates_to_leaf_nodes():
    doc = _document(
        "Some body text about remote work policy details and eligibility rules.",
        page_label="3",
        section_title="Eligibility",
        tenant_id="acme",
    )
    _, leaf_nodes = build_hierarchical_nodes([doc])

    assert len(leaf_nodes) >= 1
    for leaf in leaf_nodes:
        assert leaf.metadata["page_label"] == "3"
        assert leaf.metadata["section_title"] == "Eligibility"
        assert leaf.metadata["tenant_id"] == "acme"


def test_all_metadata_excluded_from_llm_and_embed_text():
    """Metadata is payload-only (Qdrant/BM25 filtering + explicit citation
    construction) — never rendered into text views. This matters beyond
    tidiness: context compression (SentenceEmbeddingOptimizer) naively
    sentence-splits the LLM-mode view and can permanently bake stray
    metadata lines into a node's text (see node_parsers.py docstring)."""
    doc = _document(
        "Body text about remote work eligibility.",
        tenant_id="acme",
        content_hash="deadbeef",
        document_id="doc-1",
        document_version=2,
        page_label="1",
        section_title="Eligibility",
        source_file="remote_work_policy.pdf",
    )
    _, leaf_nodes = build_hierarchical_nodes([doc])

    leaf = leaf_nodes[0]
    llm_content = leaf.get_content(metadata_mode="llm")
    embed_content = leaf.get_content(metadata_mode="embed")
    bare_content = leaf.get_content(metadata_mode="none")

    assert llm_content == bare_content
    assert embed_content == bare_content
    for needle in ["acme", "deadbeef", "doc-1", "remote_work_policy.pdf", "Eligibility"]:
        assert needle not in llm_content

    # Still present as structured metadata for payload filtering / citations.
    assert leaf.metadata["tenant_id"] == "acme"
    assert leaf.metadata["page_label"] == "1"
    assert leaf.metadata["section_title"] == "Eligibility"
