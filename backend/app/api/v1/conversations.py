from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.dependencies import get_current_api_key
from app.db.session import get_db_session
from app.models.api_key import ApiKey
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationResponse,
    MessageResponse,
    UpdateConversationRequest,
)

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    api_key: ApiKey = Depends(get_current_api_key), session: AsyncSession = Depends(get_db_session)
) -> list[ConversationResponse]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.tenant_id == api_key.tenant_id)
        .order_by(Conversation.updated_at.desc())
    )
    return [ConversationResponse.model_validate(c) for c in result.scalars().all()]


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def rename_conversation(
    conversation_id: UUID,
    request: UpdateConversationRequest,
    api_key: ApiKey = Depends(get_current_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == api_key.tenant_id
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # updated_at has onupdate=func.now(), which the ORM applies to ANY
    # update of this row -- reassigning conversation.updated_at to its own
    # current value in Python does NOT suppress it (same-value reassignment
    # isn't picked up as an explicit override by the ORM's flush logic, so
    # onupdate fires anyway). list_conversations sorts by updated_at desc
    # as a "most recently active" ordering (driven by actual chat activity,
    # not metadata edits) -- renaming must not reorder the sidebar, so this
    # uses a Core-level UPDATE with an explicit `.values()` for both
    # columns, which bypasses the ORM's onupdate default entirely.
    title = (request.title or "").strip()
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id, Conversation.tenant_id == api_key.tenant_id)
        .values(title=title or None, updated_at=conversation.updated_at)
    )
    await session.commit()
    await session.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    api_key: ApiKey = Depends(get_current_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> list[MessageResponse]:
    result = await session.execute(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.conversation_id == conversation_id, Conversation.tenant_id == api_key.tenant_id)
        .order_by(Message.created_at)
    )
    return [MessageResponse.model_validate(m) for m in result.scalars().all()]
