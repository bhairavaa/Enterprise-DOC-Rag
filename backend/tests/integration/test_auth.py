"""Auth + multi-tenant scoping against the real app and Postgres. Uses the
already-ingested acme/globex sample corpus to prove cross-tenant isolation
holds even when a caller requests no filters at all."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security.api_key import generate_api_key
from app.main import app
from app.models.api_key import ApiKey

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    created_prefixes: list[str] = []

    async with session_factory() as session:
        async def make_key(tenant_id: str, allowed_filters: dict | None = None, is_admin: bool = False):
            full_key, key_prefix, key_hash = generate_api_key()
            api_key = ApiKey(
                tenant_id=tenant_id,
                name=f"test-{uuid.uuid4().hex[:8]}",
                key_hash=key_hash,
                key_prefix=key_prefix,
                allowed_filters=allowed_filters or {},
                is_admin=is_admin,
            )
            session.add(api_key)
            await session.commit()
            created_prefixes.append(key_prefix)
            return full_key

        session.make_key = make_key
        yield session

        await session.execute(delete(ApiKey).where(ApiKey.key_prefix.in_(created_prefixes)))
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_missing_api_key_is_rejected(client):
    response = await client.get("/api/v1/documents")
    assert response.status_code == 422  # missing required header


async def test_invalid_api_key_is_rejected(client):
    response = await client.get("/api/v1/documents", headers={"X-API-Key": "not-a-real-key"})
    assert response.status_code == 401


async def test_valid_key_scopes_documents_to_its_own_tenant(client, db_session):
    acme_key = await db_session.make_key("acme")

    response = await client.get("/api/v1/documents", headers={"X-API-Key": acme_key})

    assert response.status_code == 200
    documents = response.json()
    assert len(documents) > 0
    assert all(d["tenant_id"] == "acme" for d in documents)


async def test_cross_tenant_isolation_even_with_no_filters_requested(client, db_session):
    acme_key = await db_session.make_key("acme")
    globex_key = await db_session.make_key("globex")

    acme_docs = (await client.get("/api/v1/documents", headers={"X-API-Key": acme_key})).json()
    globex_docs = (await client.get("/api/v1/documents", headers={"X-API-Key": globex_key})).json()

    assert all(d["tenant_id"] == "acme" for d in acme_docs)
    assert all(d["tenant_id"] == "globex" for d in globex_docs)
    assert {d["source_path"] for d in acme_docs}.isdisjoint({d["source_path"] for d in globex_docs})


async def test_search_endpoint_uses_tenant_from_key_not_request_body(client, db_session):
    globex_key = await db_session.make_key("globex")

    response = await client.post(
        "/api/v1/search", json={"query": "PTO accrual"}, headers={"X-API-Key": globex_key}
    )

    assert response.status_code == 200
    citations = response.json()["citations"]
    assert all("globex" in (c["source_file"] or "") for c in citations)


async def test_scoped_key_can_query_within_its_allowed_department(client, db_session):
    key = await db_session.make_key("acme", allowed_filters={"department": ["engineering"]})

    response = await client.post(
        "/api/v1/search",
        json={"query": "policy", "department": ["engineering"]},
        headers={"X-API-Key": key},
    )

    assert response.status_code == 200


async def test_scoped_key_rejected_outside_its_allowed_department(client, db_session):
    key = await db_session.make_key("acme", allowed_filters={"department": ["engineering"]})

    response = await client.post(
        "/api/v1/search",
        json={"query": "policy", "department": ["hr"]},
        headers={"X-API-Key": key},
    )

    assert response.status_code == 403


async def test_revoked_key_is_rejected(client, db_session):
    key = await db_session.make_key("acme")

    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.key_prefix == key[:12]))
    ).scalar_one()
    row.revoked_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get("/api/v1/documents", headers={"X-API-Key": key})
    assert response.status_code == 401


async def test_create_api_key_endpoint_requires_bootstrap_admin_header(client):
    response = await client.post(
        "/api/v1/auth/api-keys", json={"tenant_id": "acme", "name": "demo"}
    )
    assert response.status_code == 422  # missing required X-Admin-Key header


async def test_create_api_key_endpoint_rejects_wrong_admin_key(client):
    response = await client.post(
        "/api/v1/auth/api-keys",
        json={"tenant_id": "acme", "name": "demo"},
        headers={"X-Admin-Key": "wrong"},
    )
    assert response.status_code == 403


async def test_create_api_key_endpoint_end_to_end(client, db_session):
    settings = get_settings()

    response = await client.post(
        "/api/v1/auth/api-keys",
        json={"tenant_id": "acme", "name": "ci-test-key"},
        headers={"X-Admin-Key": settings.admin_bootstrap_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["api_key"].startswith("edr_")

    documents = await client.get("/api/v1/documents", headers={"X-API-Key": body["api_key"]})
    assert documents.status_code == 200

    await db_session.execute(delete(ApiKey).where(ApiKey.key_prefix == body["key_prefix"]))
    await db_session.commit()
