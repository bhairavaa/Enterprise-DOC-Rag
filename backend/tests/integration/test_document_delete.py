"""DELETE /documents/{id} against the real app and Postgres. Uses bare
Document rows (no real Qdrant vectors/docstore nodes) to test the endpoint's
request/response contract and tenant scoping -- the underlying purge logic
(_purge_existing_document_data) already has dedicated coverage via
test_pipeline_incremental.py's folder-sync deletion test."""

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security.api_key import generate_api_key
from app.main import app
from app.models.api_key import ApiKey
from app.models.document import Document

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    created_prefixes: list[str] = []
    created_document_ids: list[uuid.UUID] = []

    async with session_factory() as session:
        async def make_key(tenant_id: str):
            full_key, key_prefix, key_hash = generate_api_key()
            session.add(
                ApiKey(
                    tenant_id=tenant_id,
                    name=f"test-{uuid.uuid4().hex[:8]}",
                    key_hash=key_hash,
                    key_prefix=key_prefix,
                    allowed_filters={},
                )
            )
            await session.commit()
            created_prefixes.append(key_prefix)
            return full_key

        async def make_document(tenant_id: str, ingestion_root: str, source_path: str):
            document = Document(
                tenant_id=tenant_id,
                source_path=source_path,
                ingestion_root=ingestion_root,
                file_name=Path(source_path).name,
                file_type="pdf",
                current_version=1,
                content_hash="test-hash",
                size_bytes=10,
                status="completed",
            )
            session.add(document)
            await session.commit()
            created_document_ids.append(document.id)
            return document.id

        session.make_key = make_key
        session.make_document = make_document
        yield session

        await session.execute(delete(ApiKey).where(ApiKey.key_prefix.in_(created_prefixes)))
        await session.execute(delete(Document).where(Document.id.in_(created_document_ids)))
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_delete_document_marks_it_deleted_and_excludes_from_list(client, db_session):
    acme_key = await db_session.make_key("acme")
    document_id = await db_session.make_document("acme", "/tmp/test-root", "some/doc.pdf")

    response = await client.delete(
        f"/api/v1/documents/{document_id}", headers={"X-API-Key": acme_key}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "id": str(document_id)}

    listed = await client.get("/api/v1/documents", headers={"X-API-Key": acme_key})
    assert str(document_id) not in {d["id"] for d in listed.json()}


async def test_delete_document_from_another_tenant_is_not_found(client, db_session):
    acme_key = await db_session.make_key("acme")
    globex_document_id = await db_session.make_document("globex", "/tmp/test-root", "some/doc.pdf")

    response = await client.delete(
        f"/api/v1/documents/{globex_document_id}", headers={"X-API-Key": acme_key}
    )

    assert response.status_code == 404


async def test_delete_already_deleted_document_is_not_found(client, db_session):
    acme_key = await db_session.make_key("acme")
    document_id = await db_session.make_document("acme", "/tmp/test-root", "some/doc.pdf")

    first = await client.delete(f"/api/v1/documents/{document_id}", headers={"X-API-Key": acme_key})
    second = await client.delete(f"/api/v1/documents/{document_id}", headers={"X-API-Key": acme_key})

    assert first.status_code == 200
    assert second.status_code == 404


async def test_delete_nonexistent_document_is_not_found(client, db_session):
    acme_key = await db_session.make_key("acme")

    response = await client.delete(
        f"/api/v1/documents/{uuid.uuid4()}", headers={"X-API-Key": acme_key}
    )

    assert response.status_code == 404


async def test_delete_removes_underlying_file_for_uploads_only(client, db_session, tmp_path):
    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    tenant_dir = upload_root / "acme"
    tenant_dir.mkdir(parents=True, exist_ok=True)
    uploaded_file = tenant_dir / f"delete-test-{uuid.uuid4().hex[:8]}.pdf"
    uploaded_file.write_bytes(b"fake pdf content")

    acme_key = await db_session.make_key("acme")
    uploaded_doc_id = await db_session.make_document(
        "acme", str(upload_root), f"acme/{uploaded_file.name}"
    )

    # A folder-ingested document (e.g. sample_docs) -- its file must NOT be
    # touched, even though it happens to live under a real tmp_path here.
    foreign_root = tmp_path / "sample_docs"
    foreign_root.mkdir()
    foreign_file = foreign_root / "untouchable.pdf"
    foreign_file.write_bytes(b"do not delete me")
    foreign_doc_id = await db_session.make_document(
        "acme", str(foreign_root), "untouchable.pdf"
    )

    await client.delete(f"/api/v1/documents/{uploaded_doc_id}", headers={"X-API-Key": acme_key})
    await client.delete(f"/api/v1/documents/{foreign_doc_id}", headers={"X-API-Key": acme_key})

    assert not uploaded_file.exists()
    assert foreign_file.exists()
