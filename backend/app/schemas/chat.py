from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    conversation_id: UUID | None = None
    department: list[str] | None = None
    doc_type: list[str] | None = None
    tags: list[str] | None = None
