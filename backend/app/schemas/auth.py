from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateApiKeyRequest(BaseModel):
    tenant_id: str
    name: str
    allowed_filters: dict[str, list[str]] | None = None
    is_admin: bool = False


class CreateApiKeyResponse(BaseModel):
    api_key: str
    """Shown exactly once — not recoverable after this response."""
    key_prefix: str
    tenant_id: str


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    name: str
    key_prefix: str
    allowed_filters: dict
    is_admin: bool
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
