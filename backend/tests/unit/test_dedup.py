from llama_index.core.schema import NodeWithScore, TextNode

from app.core.retrieval.dedup import DeduplicateSentencesPostprocessor, dedupe_sentences


def test_dedupe_sentences_drops_exact_repeats_preserving_order():
    text = "First sentence. Second sentence. First sentence. Third sentence."

    result = dedupe_sentences(text)

    assert result == "First sentence. Second sentence. Third sentence."


def test_dedupe_sentences_is_case_insensitive():
    text = "Remote work is allowed. remote work is allowed. Something else."

    result = dedupe_sentences(text)

    assert result == "Remote work is allowed. Something else."


def test_dedupe_sentences_handles_no_duplicates():
    text = "One. Two. Three."

    assert dedupe_sentences(text) == "One. Two. Three."


def test_dedupe_sentences_handles_empty_text():
    assert dedupe_sentences("") == ""


def test_postprocessor_mutates_node_content_in_place():
    node = TextNode(text="Eligible after 90 days. Eligible after 90 days. Managers may approve exceptions.")
    node_with_score = NodeWithScore(node=node, score=0.9)

    result = DeduplicateSentencesPostprocessor().postprocess_nodes([node_with_score])

    assert len(result) == 1
    assert result[0].node.get_content() == "Eligible after 90 days. Managers may approve exceptions."
