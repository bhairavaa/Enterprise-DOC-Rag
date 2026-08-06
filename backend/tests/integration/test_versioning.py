import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.ingestion.versioning import (
    finalize_document,
    get_or_create_document,
    mark_document_failed,
    register_queued_upload,
)
from app.models.document import Document, DocumentVersion

pytestmark = pytest.mark.integration


@pytest.fixture
async def session():
    """Uses a per-test tenant_id (rather than a real-looking tenant like
    "acme") so committed test data can never collide with or get swept up
    by a real ingestion run's tenant-scoped deletion detection — and is
    explicitly cleaned up afterward, since committed rows survive the
    session rollback below."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:8]}"

    async with session_factory() as s:
        s.test_tenant_id = tenant_id
        yield s
        await s.rollback()
        await s.execute(delete(Document).where(Document.tenant_id == tenant_id))
        await s.commit()
    await engine.dispose()


def _unique_source_path() -> str:
    return f"handbook-{uuid.uuid4().hex}.pdf"


async def test_new_document_creates_version_1(session):
    decision = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=_unique_source_path(),
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await session.commit()

    assert decision.is_new is True
    assert decision.changed is True
    assert decision.document.current_version == 1

    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == decision.document.id)
    )
    versions = result.scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].superseded_at is None


async def test_unchanged_content_hash_is_a_noop(session):
    source_path = _unique_source_path()

    first = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    # "Unchanged" only means something once a row has actually finished
    # ingesting -- a row can share a content_hash with an in-flight
    # ("processing"/"queued") row without that meaning there's nothing left
    # to do (see register_queued_upload's eager-registration tests below).
    await finalize_document(session, first.document, num_chunks=3)
    await session.commit()

    second = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )

    assert second.is_new is False
    assert second.changed is False
    assert second.document.id == first.document.id
    assert second.document.current_version == 1


async def test_changed_content_hash_bumps_version_and_supersedes_previous(session):
    source_path = _unique_source_path()

    first = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await finalize_document(session, first.document, num_chunks=5)
    await session.commit()
    document_id = first.document.id

    second = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v2",
        size_bytes=150,
    )
    await session.commit()

    assert second.is_new is False
    assert second.changed is True
    assert second.document.id == document_id
    assert second.document.current_version == 2
    assert second.document.content_hash == "hash-v2"

    result = await session.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version)
    )
    versions = result.scalars().all()
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[0].superseded_at is not None
    assert versions[0].num_chunks == 5
    assert versions[1].version == 2
    assert versions[1].superseded_at is None


async def test_finalize_document_sets_status_and_chunk_count(session):
    decision = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=_unique_source_path(),
        file_name="handbook.pdf",
        file_type="pdf",
        department=None,
        doc_type=None,
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await finalize_document(session, decision.document, num_chunks=7)
    await session.commit()

    result = await session.execute(select(Document).where(Document.id == decision.document.id))
    document = result.scalar_one()
    assert document.status == "completed"
    assert document.num_chunks == 7


async def test_register_queued_upload_creates_row_visible_before_processing(session):
    source_path = _unique_source_path()

    await register_queued_upload(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await session.commit()

    result = await session.execute(select(Document).where(Document.source_path == source_path))
    document = result.scalar_one()
    assert document.status == "queued"
    assert document.current_version == 1

    # No version row yet -- that's created once real processing starts.
    versions = await session.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == document.id)
    )
    assert versions.scalars().all() == []


async def test_processing_a_queued_upload_does_not_bump_version(session):
    source_path = _unique_source_path()

    await register_queued_upload(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await session.commit()

    # Worker picks up the task and calls get_or_create_document with the
    # *same* content_hash the upload already registered -- must be treated
    # as "first real ingestion", not a no-op and not a version bump.
    decision = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await session.commit()

    assert decision.is_new is True
    assert decision.changed is True
    assert decision.document.current_version == 1
    assert decision.document.status == "processing"

    versions = await session.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == decision.document.id)
    )
    version_rows = versions.scalars().all()
    assert len(version_rows) == 1
    assert version_rows[0].version == 1


async def test_register_queued_upload_on_existing_completed_document_does_not_touch_version(session):
    source_path = _unique_source_path()

    first = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await finalize_document(session, first.document, num_chunks=3)
    await session.commit()

    # A re-upload of a changed file: register_queued_upload flips it back
    # to "queued" but must not touch current_version -- that's still
    # get_or_create_document's decision once processing actually runs.
    await register_queued_upload(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v2",
        size_bytes=150,
    )
    await session.commit()

    result = await session.execute(select(Document).where(Document.id == first.document.id))
    document = result.scalar_one()
    assert document.status == "queued"
    assert document.current_version == 1
    assert document.content_hash == "hash-v2"

    # Processing then correctly bumps the version, since a version-1 row
    # already exists from the original completed ingestion.
    second = await get_or_create_document(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v2",
        size_bytes=150,
    )
    await session.commit()

    assert second.is_new is False
    assert second.changed is True
    assert second.document.current_version == 2


async def test_mark_document_failed_flips_status_on_existing_row(session):
    source_path = _unique_source_path()

    await register_queued_upload(
        session,
        tenant_id=session.test_tenant_id,
        ingestion_root="/tmp/test-root",
        source_path=source_path,
        file_name="handbook.pdf",
        file_type="pdf",
        department="engineering",
        doc_type="policies",
        tags=[],
        content_hash="hash-v1",
        size_bytes=100,
    )
    await session.commit()

    await mark_document_failed(session, tenant_id=session.test_tenant_id, source_path=source_path)
    await session.commit()

    result = await session.execute(select(Document).where(Document.source_path == source_path))
    document = result.scalar_one()
    assert document.status == "failed"


async def test_mark_document_failed_is_a_noop_when_row_does_not_exist(session):
    # Should never raise even if the crash happened before any row existed.
    await mark_document_failed(
        session, tenant_id=session.test_tenant_id, source_path=_unique_source_path()
    )
    await session.commit()
