import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
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


async def test_search_endpoint_returns_citations(client, db_session):
    acme_key = await db_session.make_key("acme")

    response = await client.post(
        "/api/v1/search",
        json={"query": "How much is the home office stipend for remote employees?"},
        headers={"X-API-Key": acme_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert "citations" in body
    assert len(body["citations"]) > 0
    assert body["citations"][0]["index"] == 1
    assert any(
        c["source_file"] == "acme/engineering/policies/remote_work_policy.pdf"
        for c in body["citations"]
    )


async def test_search_endpoint_scopes_by_tenant(client, db_session):
    globex_key = await db_session.make_key("globex")

    response = await client.post(
        "/api/v1/search", json={"query": "PTO accrual"}, headers={"X-API-Key": globex_key}
    )

    assert response.status_code == 200
    citations = response.json()["citations"]
    assert all("globex" in (c["source_file"] or "") for c in citations)
