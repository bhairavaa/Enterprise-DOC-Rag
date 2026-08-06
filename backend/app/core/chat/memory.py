import uuid

from llama_index.core.llms import ChatMessage, MessageRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.schemas.citation import Citation

_ROLE_MAP = {"user": MessageRole.USER, "assistant": MessageRole.ASSISTANT}


async def get_or_create_conversation(
    session: AsyncSession, tenant_id: str, conversation_id: uuid.UUID | None
) -> Conversation:
    if conversation_id is not None:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            return conversation

    conversation = Conversation(tenant_id=tenant_id)
    session.add(conversation)
    await session.flush()
    return conversation


async def load_history(session: AsyncSession, conversation_id: uuid.UUID) -> list[ChatMessage]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return [
        ChatMessage(role=_ROLE_MAP.get(m.role, MessageRole.USER), content=m.content)
        for m in result.scalars().all()
    ]


async def append_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    citations: list[Citation] | None = None,
    retrieval_filters: dict | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=[c.model_dump() for c in citations] if citations else None,
        retrieval_filters=retrieval_filters,
    )
    session.add(message)
    await session.flush()
    return message
