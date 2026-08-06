"""Exercises the chat engine (semantic cache short-circuit, retrieval,
condense-question, streaming, message persistence) against the real
sample_docs corpus and Postgres, with the LLM call mocked via MockLLM since
no provider API key is configured in this environment."""

import uuid

import pytest
from llama_index.core.llms import MockLLM
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.chat.engine import stream_chat_response
from app.core.chat.memory import get_or_create_conversation, load_history
from app.core.retrieval.filters import SearchFilters
from app.models.conversation import Conversation

pytestmark = pytest.mark.integration


@pytest.fixture
async def session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:8]}"

    async with session_factory() as s:
        s.test_tenant_id = tenant_id
        yield s
        await s.rollback()
        await s.execute(delete(Conversation).where(Conversation.tenant_id == tenant_id))
        await s.commit()
    await engine.dispose()


async def _collect_events(generator):
    return [event async for event in generator]


async def test_event_sequence_is_citations_then_tokens_then_done(session):
    conversation = await get_or_create_conversation(session, session.test_tenant_id, None)
    await session.commit()

    events = await _collect_events(
        stream_chat_response(
            session,
            session.test_tenant_id,
            conversation.id,
            "What is the code review SLA?",
            SearchFilters(tenant_id=session.test_tenant_id),
            llm=MockLLM(),
        )
    )
    await session.commit()

    assert events[0]["event"] == "citations"
    assert events[-1]["event"] == "done"
    assert all(e["event"] == "token" for e in events[1:-1])
    assert len(events) > 2  # at least one token between citations and done


async def test_messages_persisted_after_response(session):
    conversation = await get_or_create_conversation(session, session.test_tenant_id, None)
    await session.commit()

    await _collect_events(
        stream_chat_response(
            session,
            session.test_tenant_id,
            conversation.id,
            "What is the code review SLA?",
            SearchFilters(tenant_id=session.test_tenant_id),
            llm=MockLLM(),
        )
    )
    await session.commit()

    history = await load_history(session, conversation.id)
    assert len(history) == 2
    assert history[0].role.value == "user"
    assert history[1].role.value == "assistant"


async def test_second_identical_question_hits_semantic_cache(session):
    conversation = await get_or_create_conversation(session, session.test_tenant_id, None)
    await session.commit()
    search_filters = SearchFilters(tenant_id=session.test_tenant_id)
    question = "What is the code review SLA for urgent pull requests?"

    await _collect_events(
        stream_chat_response(
            session, session.test_tenant_id, conversation.id, question, search_filters, llm=MockLLM()
        )
    )
    await session.commit()

    second_events = await _collect_events(
        stream_chat_response(
            session, session.test_tenant_id, conversation.id, question, search_filters, llm=MockLLM()
        )
    )
    await session.commit()

    assert second_events[-1]["data"] == {"cached": True}
    # Cached path emits exactly one token event containing the full answer.
    token_events = [e for e in second_events if e["event"] == "token"]
    assert len(token_events) == 1


async def test_multi_turn_history_is_included_in_second_call(session):
    conversation = await get_or_create_conversation(session, session.test_tenant_id, None)
    await session.commit()
    search_filters = SearchFilters(tenant_id=session.test_tenant_id)

    await _collect_events(
        stream_chat_response(
            session,
            session.test_tenant_id,
            conversation.id,
            "What is the PTO accrual rate?",
            search_filters,
            llm=MockLLM(),
        )
    )
    await session.commit()

    history_before_second_turn = await load_history(session, conversation.id)
    assert len(history_before_second_turn) == 2

    await _collect_events(
        stream_chat_response(
            session,
            session.test_tenant_id,
            conversation.id,
            "And what about carryover?",
            search_filters,
            llm=MockLLM(),
        )
    )
    await session.commit()

    history_after_second_turn = await load_history(session, conversation.id)
    assert len(history_after_second_turn) == 4
