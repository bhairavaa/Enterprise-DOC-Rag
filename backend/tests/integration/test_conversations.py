"""Conversation rename endpoint, against the real app and Postgres."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security.api_key import generate_api_key
from app.main import app
from app.models.api_key import ApiKey
from app.models.conversation import Conversation

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    created_prefixes: list[str] = []
    created_conversation_ids: list[uuid.UUID] = []

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

        async def make_conversation(tenant_id: str):
            conversation = Conversation(tenant_id=tenant_id)
            session.add(conversation)
            await session.commit()
            created_conversation_ids.append(conversation.id)
            return conversation.id

        session.make_key = make_key
        session.make_conversation = make_conversation
        yield session

        await session.execute(delete(ApiKey).where(ApiKey.key_prefix.in_(created_prefixes)))
        await session.execute(
            delete(Conversation).where(Conversation.id.in_(created_conversation_ids))
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_rename_conversation_sets_title(client, db_session):
    acme_key = await db_session.make_key("acme")
    conversation_id = await db_session.make_conversation("acme")

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Remote work follow-ups"},
        headers={"X-API-Key": acme_key},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Remote work follow-ups"

    listed = await client.get("/api/v1/conversations", headers={"X-API-Key": acme_key})
    titles = {c["id"]: c["title"] for c in listed.json()}
    assert titles[str(conversation_id)] == "Remote work follow-ups"


async def test_rename_does_not_change_updated_at_or_reorder_sidebar(client, db_session):
    # list_conversations sorts by updated_at desc as a "most recently
    # active" ordering -- renaming is a metadata edit, not activity, and
    # must not bump a conversation to the top of that list.
    acme_key = await db_session.make_key("acme")
    first_id = await db_session.make_conversation("acme")
    await db_session.make_conversation("acme")  # second conversation, gives ordering something to preserve

    before = await client.get("/api/v1/conversations", headers={"X-API-Key": acme_key})
    order_before = [c["id"] for c in before.json()]
    first_updated_at_before = next(c["updated_at"] for c in before.json() if c["id"] == str(first_id))

    response = await client.patch(
        f"/api/v1/conversations/{first_id}",
        json={"title": "Renamed but still in the same position"},
        headers={"X-API-Key": acme_key},
    )

    assert response.json()["updated_at"] == first_updated_at_before

    after = await client.get("/api/v1/conversations", headers={"X-API-Key": acme_key})
    order_after = [c["id"] for c in after.json()]
    assert order_after == order_before


async def test_rename_conversation_blank_title_clears_it(client, db_session):
    acme_key = await db_session.make_key("acme")
    conversation_id = await db_session.make_conversation("acme")

    await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Something"},
        headers={"X-API-Key": acme_key},
    )
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "   "},
        headers={"X-API-Key": acme_key},
    )

    assert response.status_code == 200
    assert response.json()["title"] is None


async def test_rename_conversation_from_another_tenant_is_not_found(client, db_session):
    acme_key = await db_session.make_key("acme")
    globex_conversation_id = await db_session.make_conversation("globex")

    response = await client.patch(
        f"/api/v1/conversations/{globex_conversation_id}",
        json={"title": "Should not work"},
        headers={"X-API-Key": acme_key},
    )

    assert response.status_code == 404


async def test_rename_nonexistent_conversation_is_not_found(client, db_session):
    acme_key = await db_session.make_key("acme")

    response = await client.patch(
        f"/api/v1/conversations/{uuid.uuid4()}",
        json={"title": "Ghost"},
        headers={"X-API-Key": acme_key},
    )

    assert response.status_code == 404
