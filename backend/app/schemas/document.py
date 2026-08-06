from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    source_path: str
    file_name: str
    file_type: str
    department: str | None
    doc_type: str | None
    tags: list[str] | None
    status: str
    num_chunks: int
    current_version: int
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    task_id: str
    source_path: str
    status: str
    """Always "queued" at response time — ingestion runs asynchronously in a
    Celery worker. Poll GET /documents to see the row appear and its status
    move from "processing" to "completed"."""
