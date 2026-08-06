from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security.dependencies import get_current_api_key
from app.db.session import get_db_session
from app.ingestion.bm25_index import rebuild_bm25_index
from app.ingestion.file_hash import hash_file
from app.ingestion.pipeline import _purge_existing_document_data
from app.ingestion.versioning import register_queued_upload
from app.logging import get_logger
from app.models.api_key import ApiKey
from app.models.document import Document
from app.schemas.document import DocumentResponse, UploadResponse
from app.worker.tasks import ingest_document_task

logger = get_logger(__name__)

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile,
    department: str | None = Form(None),
    doc_type: str | None = Form(None),
    tags: str = Form(""),
    api_key: ApiKey = Depends(get_current_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    """Saves the upload under a per-tenant directory and enqueues it for the
    same ingestion pipeline folder-based CLI ingestion uses — just with
    metadata supplied explicitly instead of inferred from folder structure.
    tenant_id comes from the authenticated key, not the request, so a
    caller can never upload into another tenant's corpus.

    Ingestion itself runs asynchronously in a Celery worker (--pool=solo,
    one file at a time) rather than blocking this request. The document row
    is registered as "queued" here, before the worker has necessarily even
    picked up the task, so GET /documents shows it immediately instead of
    only once the worker gets around to it -- status then moves
    queued -> processing -> completed as the worker actually runs it."""
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    tenant_dir = upload_root / api_key.tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    file_path = tenant_dir / file.filename
    contents = await file.read()
    file_path.write_bytes(contents)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    relative_path = file_path.relative_to(upload_root).as_posix()

    await register_queued_upload(
        session,
        tenant_id=api_key.tenant_id,
        source_path=relative_path,
        ingestion_root=str(upload_root.resolve()),  # noqa: ASYNC240 -- cheap, bounded-cost syscall on a short relative path, same precedent as pipeline.py's identical resolve() call
        file_name=file_path.name,
        file_type=file_path.suffix.lstrip("."),
        department=department,
        doc_type=doc_type,
        tags=tag_list,
        content_hash=hash_file(file_path),
        size_bytes=file_path.stat().st_size,
    )
    await session.commit()

    task = ingest_document_task.delay(
        str(file_path), str(upload_root), api_key.tenant_id, department, doc_type, tag_list
    )

    return UploadResponse(task_id=task.id, source_path=relative_path, status="queued")


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    api_key: ApiKey = Depends(get_current_api_key), session: AsyncSession = Depends(get_db_session)
) -> list[DocumentResponse]:
    result = await session.execute(
        select(Document)
        .where(Document.tenant_id == api_key.tenant_id, Document.status != "deleted")
        .order_by(Document.created_at.desc())
    )
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    api_key: ApiKey = Depends(get_current_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Soft-deletes the registry row (status="deleted", excluded from
    GET /documents) and purges its vectors/docstore nodes/cached answers --
    the same cleanup registry_sync.py runs when a folder-ingested file
    disappears from disk. Also removes the underlying file for uploads
    (under UPLOAD_DIR), but never for folder-ingested documents (e.g.
    sample_docs, mounted read-only in Docker) -- those files aren't ours
    to delete."""
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == api_key.tenant_id,
            Document.status != "deleted",
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _purge_existing_document_data(str(document.id))
    document.status = "deleted"
    await session.commit()

    settings = get_settings()
    upload_root = str(Path(settings.upload_dir).resolve())  # noqa: ASYNC240 -- cheap, bounded-cost syscall, same precedent as upload_document above
    if document.ingestion_root == upload_root:
        file_path = Path(document.ingestion_root) / document.source_path
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("delete_document_file_failed", source_path=document.source_path)

    rebuild_bm25_index()

    return {"status": "deleted", "id": str(document.id)}
