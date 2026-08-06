from llama_index.core.schema import NodeWithScore

from app.schemas.citation import Citation


def build_citations(nodes: list[NodeWithScore]) -> list[Citation]:
    """Numbered 1-based to match the `[1]`, `[2]`... markers the chat
    prompt (Phase 3) inserts inline in the generated answer."""
    citations: list[Citation] = []
    for i, node_with_score in enumerate(nodes, start=1):
        node = node_with_score.node
        citations.append(
            Citation(
                index=i,
                text=node.get_content(metadata_mode="none"),
                score=node_with_score.score,
                source_file=node.metadata.get("source_file"),
                document_id=node.metadata.get("document_id"),
                page_label=node.metadata.get("page_label"),
                section_title=node.metadata.get("section_title"),
                slide_number=node.metadata.get("slide_number"),
            )
        )
    return citations
