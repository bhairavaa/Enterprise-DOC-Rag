from llama_index.core.schema import NodeWithScore, TextNode

from app.core.retrieval.citations import build_citations


def _node_with_score(text: str, score: float, **metadata) -> NodeWithScore:
    node = TextNode(text=text, metadata=metadata)
    return NodeWithScore(node=node, score=score)


def test_build_citations_numbers_sequentially_from_one():
    nodes = [
        _node_with_score("First chunk.", 0.9, source_file="a.pdf"),
        _node_with_score("Second chunk.", 0.5, source_file="b.pdf"),
    ]
    citations = build_citations(nodes)

    assert [c.index for c in citations] == [1, 2]


def test_build_citations_extracts_structural_metadata():
    nodes = [
        _node_with_score(
            "Some policy text.",
            0.8,
            source_file="remote_work_policy.pdf",
            document_id="doc-1",
            page_label="3",
            section_title="Eligibility",
        )
    ]
    citation = build_citations(nodes)[0]

    assert citation.text == "Some policy text."
    assert citation.score == 0.8
    assert citation.source_file == "remote_work_policy.pdf"
    assert citation.document_id == "doc-1"
    assert citation.page_label == "3"
    assert citation.section_title == "Eligibility"
    assert citation.slide_number is None


def test_build_citations_handles_missing_optional_fields():
    nodes = [_node_with_score("Bare text with no structural metadata.", 0.4)]
    citation = build_citations(nodes)[0]

    assert citation.source_file is None
    assert citation.page_label is None
    assert citation.section_title is None
    assert citation.slide_number is None
