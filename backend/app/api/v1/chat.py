import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette import EventSourceResponse

from app.core.chat.engine import stream_chat_response
from app.core.chat.memory import get_or_create_conversation
from app.core.security.dependencies import get_current_api_key
from app.core.security.rate_limit import rate_limiter
from app.core.security.scoping import resolve_scoped_filters
from app.db.session import get_db_session
from app.models.api_key import ApiKey
from app.schemas.chat import ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/chat", dependencies=[Depends(rate_limiter("chat"))])
async def chat(
    request: ChatRequest,
    api_key: ApiKey = Depends(get_current_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> EventSourceResponse:
    """SSE stream: `event: conversation` (once, so a new client-side chat
    learns the server-assigned conversation id) -> `event: citations` (once)
    -> `event: token` (many, streamed answer) -> `event: done`."""
    search_filters = resolve_scoped_filters(api_key, request.department, request.doc_type, request.tags)
    conversation = await get_or_create_conversation(
        session, api_key.tenant_id, request.conversation_id
    )
    await session.commit()

    async def event_stream() -> AsyncGenerator[dict[str, Any], None]:
        yield {"event": "conversation", "data": json.dumps({"id": str(conversation.id)})}
        async for event in stream_chat_response(
            session, api_key.tenant_id, conversation.id, request.query, search_filters
        ):
            yield {"event": event["event"], "data": json.dumps(event["data"])}
        await session.commit()

    return EventSourceResponse(event_stream())
