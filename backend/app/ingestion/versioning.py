from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion


@dataclass
class VersionDecision:
    document: Document
    is_new: bool
    changed: bool
    """False means the file's content_hash is unchanged since last ingestion
    — the caller should skip re-chunking/re-embedding entirely."""


async def get_or_create_document(
    session: AsyncSession,
    *,
    tenant_id: str,
    source_path: str,
    ingestion_root: str,
    file_name: str,
    file_type: str,
    department: str | None,
    doc_type: str | None,
    tags: list[str],
    content_hash: str,
    size_bytes: int,
) -> VersionDecision:
    result = await session.execute(
        select(Document).where(
            Document.tenant_id == tenant_id, Document.source_path == source_path
        )
    )
    document = result.scalar_one_or_none()

    if document is None:
        document = Document(
            tenant_id=tenant_id,
            source_path=source_path,
            ingestion_root=ingestion_root,
            file_name=file_name,
            file_type=file_type,
            department=department,
            doc_type=doc_type,
            tags=tags,
            content_hash=content_hash,
            size_bytes=size_bytes,
            current_version=1,
            status="processing",
        )
        session.add(document)
        await session.flush()
        session.add(
            DocumentVersion(
                document_id=document.id,
                version=1,
                content_hash=content_hash,
                size_bytes=size_bytes,
            )
        )
        return VersionDecision(document=document, is_new=True, changed=True)

    # Only a *completed* row with matching content is genuinely unchanged.
    # A row can exist with a matching content_hash but status != "completed"
    # when register_queued_upload() eagerly registered it as "queued" ahead
    # of the worker actually processing it -- that's not "nothing to do",
    # it just hasn't been embedded yet.
    if document.content_hash == content_hash and document.status == "completed":
        return VersionDecision(document=document, is_new=False, changed=False)

    result = await session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version == document.current_version,
        )
    )
    existing_version = result.scalar_one_or_none()

    if existing_version is None:
        # No version row for current_version yet -- this is the first real
        # ingestion of a document whose row was created early by
        # register_queued_upload() (async upload path), not a genuine
        # content change on a previously-completed document. Don't bump the
        # version; just fill in its initial version row.
        document.status = "processing"
        document.content_hash = content_hash
        document.size_bytes = size_bytes
        session.add(
            DocumentVersion(
                document_id=document.id,
                version=document.current_version,
                content_hash=content_hash,
                size_bytes=size_bytes,
            )
        )
        return VersionDecision(document=document, is_new=True, changed=True)

    existing_version.superseded_at = datetime.now(UTC)

    document.current_version += 1
    document.content_hash = content_hash
    document.size_bytes = size_bytes
    document.department = department
    document.doc_type = doc_type
    document.tags = tags
    document.status = "processing"

    session.add(
        DocumentVersion(
            document_id=document.id,
            version=document.current_version,
            content_hash=content_hash,
            size_bytes=size_bytes,
        )
    )
    return VersionDecision(document=document, is_new=False, changed=True)


async def register_queued_upload(
    session: AsyncSession,
    *,
    tenant_id: str,
    source_path: str,
    ingestion_root: str,
    file_name: str,
    file_type: str,
    department: str | None,
    doc_type: str | None,
    tags: list[str],
    content_hash: str,
    size_bytes: int,
) -> None:
    """Eagerly creates/refreshes a `queued` Document row the moment a file
    is uploaded (app/api/v1/ingestion.py's upload_document), so it shows up
    in GET /documents immediately -- before the Celery worker has even
    picked up the task, which may still be busy with an earlier queued file
    (the --pool=solo worker processes one at a time, so uploads queue up).
    The real version-tracking upsert (content-hash comparison, version
    bump, DocumentVersion bookkeeping) still happens in
    get_or_create_document() once the worker actually starts processing;
    this only ever touches status/content_hash/size/facets, never
    `current_version` -- get_or_create_document decides whether that
    upload turns out to need a version bump or is just filling in a fresh
    document's first version.
    """
    result = await session.execute(
        select(Document).where(Document.tenant_id == tenant_id, Document.source_path == source_path)
    )
    document = result.scalar_one_or_none()

    if document is None:
        session.add(
            Document(
                tenant_id=tenant_id,
                source_path=source_path,
                ingestion_root=ingestion_root,
                file_name=file_name,
                file_type=file_type,
                department=department,
                doc_type=doc_type,
                tags=tags,
                content_hash=content_hash,
                size_bytes=size_bytes,
                current_version=1,
                status="queued",
            )
        )
    else:
        document.status = "queued"
        document.content_hash = content_hash
        document.size_bytes = size_bytes
        document.department = department
        document.doc_type = doc_type
        document.tags = tags


async def mark_document_failed(session: AsyncSession, *, tenant_id: str, source_path: str) -> None:
    """Best-effort: flips a queued/processing row to `failed` so a crash
    mid-ingestion (a bug, a transient Qdrant/Postgres hiccup, an
    out-of-memory embedding load, ...) leaves a visible, terminal status
    instead of a row stuck at `queued`/`processing` forever with no
    indication anything went wrong. No-op if the row doesn't exist --
    ingest_document_task calls this from an exception handler, so the
    failure could in principle happen before the row was ever created."""
    result = await session.execute(
        select(Document).where(Document.tenant_id == tenant_id, Document.source_path == source_path)
    )
    document = result.scalar_one_or_none()
    if document is not None:
        document.status = "failed"


async def finalize_document(session: AsyncSession, document: Document, num_chunks: int) -> None:
    document.num_chunks = num_chunks
    document.status = "completed"

    result = await session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version == document.current_version,
        )
    )
    version_row = result.scalar_one_or_none()
    if version_row is not None:
        version_row.num_chunks = num_chunks
