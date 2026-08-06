import uuid
from collections.abc import AsyncGenerator
from typing import Any

from llama_index.core.llms import LLM, ChatMessage, MessageRole
from llama_index.core.schema import NodeWithScore, QueryBundle
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.cache import semantic_cache
from app.core.chat.memory import append_message, load_history
from app.core.providers.llm_factory import get_llm
from app.core.retrieval.citations import build_citations
from app.core.retrieval.filters import SearchFilters
from app.core.retrieval.hybrid_retriever import build_hybrid_retriever
from app.core.retrieval.postprocessors import build_postprocessors
from app.logging import get_logger
from app.schemas.citation import Citation

logger = get_logger(__name__)

CHAT_SYSTEM_PROMPT = (
    "You are an enterprise document assistant. Answer the user's question "
    "using ONLY the numbered sources in the context below. Cite sources "
    "inline using their number, e.g. [1], [2]. If the sources don't contain "
    "the answer, say so explicitly rather than guessing.\n\n"
    "Format the answer as markdown: use bullet or numbered lists when "
    "presenting multiple facts, steps, or values; use **bold** for key "
    "terms; use short paragraphs otherwise. Don't force structure onto a "
    "simple one-sentence answer.\n\n"
    "You have a limited response budget, so budget for it: if several "
    "sources are relevant, prioritize the most directly relevant ones "
    "rather than covering every source exhaustively, and write concisely "
    "enough to finish your full answer, including a proper conclusion, "
    "within that budget. Never let your response run out mid-sentence or "
    "mid-thought -- a shorter, complete answer is always better than a "
    "longer one that cuts off unfinished."
)

CONDENSE_PROMPT_TEMPLATE = (
    "Given the conversation history and a follow-up question, rewrite the "
    "follow-up question as a standalone question that captures all "
    "necessary context from the history. If it's already standalone, "
    "return it unchanged. Respond with only the rewritten question.\n\n"
    "Chat history:\n{history}\n\n"
    "Follow-up question: {question}\n"
    "Standalone question:"
)


async def _condense_question(llm: LLM, history: list[ChatMessage], question: str) -> str:
    if not history:
        return question
    history_text = "\n".join(f"{m.role.value}: {m.content}" for m in history)
    prompt = CONDENSE_PROMPT_TEMPLATE.format(history=history_text, question=question)
    response = await llm.acomplete(prompt)
    return str(response).strip()


def _location_label(citation: Citation) -> str | None:
    if citation.page_label:
        return f"page {citation.page_label}"
    if citation.slide_number:
        return f"slide {citation.slide_number}"
    if citation.section_title:
        return citation.section_title
    return None


def _build_context_block(citations: list[Citation]) -> str:
    blocks = []
    for citation in citations:
        location = _location_label(citation)
        source = citation.source_file or "unknown source"
        header = f"[{citation.index}] (Source: {source}{f', {location}' if location else ''})"
        blocks.append(f"{header}\n{citation.text}")
    return "\n\n".join(blocks)


async def _retrieve_and_build_citations(
    query: str, search_filters: SearchFilters
) -> tuple[list[NodeWithScore], list[Citation]]:
    retriever = build_hybrid_retriever(search_filters)
    query_bundle = QueryBundle(query_str=query)

    nodes = retriever.retrieve(query_bundle)
    for postprocessor in build_postprocessors():
        nodes = postprocessor.postprocess_nodes(nodes, query_bundle=query_bundle)

    return nodes, build_citations(nodes)


async def stream_chat_response(
    session: AsyncSession,
    tenant_id: str,
    conversation_id: uuid.UUID,
    question: str,
    search_filters: SearchFilters,
    llm: LLM | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Yields {"event": ..., "data": ...} dicts for the SSE layer to encode.
    Event sequence is always: "citations" (once, so the UI can render
    sources immediately) -> "token" (many) -> "done" (once).

    `llm` defaults to the configured provider (get_llm()) but is injectable
    so tests can exercise the full engine with MockLLM instead of a real,
    costly (and here, unconfigured) provider call.
    """
    retrieval_filters_payload = {
        "tenant_id": search_filters.tenant_id,
        "department": search_filters.department,
        "doc_type": search_filters.doc_type,
        "tags": search_filters.tags,
    }

    cache_hit = semantic_cache.lookup(question, search_filters)
    trace.get_current_span().set_attribute("cache.hit", cache_hit is not None)
    logger.info("semantic_cache_lookup", hit=cache_hit is not None, tenant_id=tenant_id)

    if cache_hit is not None:
        await append_message(
            session, conversation_id, "user", question, retrieval_filters=retrieval_filters_payload
        )
        await append_message(
            session, conversation_id, "assistant", cache_hit.answer, citations=cache_hit.citations
        )

        yield {"event": "citations", "data": [c.model_dump() for c in cache_hit.citations]}
        yield {"event": "token", "data": cache_hit.answer}
        yield {"event": "done", "data": {"cached": True}}
        return

    settings = get_settings()
    llm = llm or get_llm()
    history = await load_history(session, conversation_id)

    standalone_question = (
        await _condense_question(llm, history, question)
        if settings.query_rewrite_enabled
        else question
    )

    _, citations = await _retrieve_and_build_citations(standalone_question, search_filters)
    yield {"event": "citations", "data": [c.model_dump() for c in citations]}

    context_block = _build_context_block(citations)
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=CHAT_SYSTEM_PROMPT),
        *history,
        ChatMessage(
            role=MessageRole.USER, content=f"Context:\n{context_block}\n\nQuestion: {question}"
        ),
    ]

    full_answer = ""
    async for chunk in await llm.astream_chat(messages):
        delta = chunk.delta or ""
        if delta:
            full_answer += delta
            yield {"event": "token", "data": delta}

    await append_message(
        session, conversation_id, "user", question, retrieval_filters=retrieval_filters_payload
    )
    await append_message(session, conversation_id, "assistant", full_answer, citations=citations)

    document_ids = list({c.document_id for c in citations if c.document_id})
    semantic_cache.store(question, full_answer, citations, search_filters, document_ids)

    yield {"event": "done", "data": {"cached": False}}
