from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class UpdateConversationRequest(BaseModel):
    title: str | None = None
    """A blank/whitespace-only value clears the title (falls back to
    "Untitled conversation" in the UI), rather than storing an empty
    string."""


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    citations: list[dict] | None
    created_at: datetime
