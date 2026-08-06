"""Rate limiter enforcement against real Redis."""

import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security import rate_limit as rate_limit_module
from app.core.security.api_key import generate_api_key
from app.core.security.rate_limit import enforce_rate_limit
from app.main import app
from app.models.api_key import ApiKey

pytestmark = pytest.mark.integration


def _settings_with(**overrides):
    # model_copy preserves the real redis_url (Docker-mapped host port) from
    # the loaded environment -- only overriding the rate-limit-specific
    # fields under test, unlike Settings(_env_file=None, ...) which would
    # reset redis_url to its unreachable default.
    return get_settings().model_copy(update=overrides)


async def test_requests_within_limit_succeed(monkeypatch):
    settings = _settings_with(rate_limit_enabled=True, rate_limit_requests=3, rate_limit_window_seconds=60)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    identifier = f"test:{uuid.uuid4().hex[:8]}"

    for _ in range(3):
        await enforce_rate_limit(identifier)


async def test_request_over_limit_is_rejected_with_429_and_retry_after(monkeypatch):
    settings = _settings_with(rate_limit_enabled=True, rate_limit_requests=2, rate_limit_window_seconds=60)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    identifier = f"test:{uuid.uuid4().hex[:8]}"

    await enforce_rate_limit(identifier)
    await enforce_rate_limit(identifier)

    with pytest.raises(HTTPException) as exc_info:
        await enforce_rate_limit(identifier)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0


async def test_disabled_rate_limit_never_blocks(monkeypatch):
    settings = _settings_with(rate_limit_enabled=False, rate_limit_requests=1, rate_limit_window_seconds=60)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    identifier = f"test:{uuid.uuid4().hex[:8]}"

    for _ in range(5):
        await enforce_rate_limit(identifier)


async def test_different_identifiers_have_independent_budgets(monkeypatch):
    # Window must comfortably outlast worst-case cold-start retrieval
    # latency (embedding model load on first use can take 60s+) -- these
    # two real /search calls must land in the same fixed window regardless
    # of how long the first one takes.
    settings = _settings_with(rate_limit_enabled=True, rate_limit_requests=1, rate_limit_window_seconds=600)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    id_a = f"test:{uuid.uuid4().hex[:8]}"
    id_b = f"test:{uuid.uuid4().hex[:8]}"

    await enforce_rate_limit(id_a)  # uses up id_a's budget

    await enforce_rate_limit(id_b)  # unaffected, must not raise

    with pytest.raises(HTTPException):
        await enforce_rate_limit(id_a)


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


async def test_search_endpoint_returns_429_once_limit_exceeded(client, db_session, monkeypatch):
    # Window must comfortably outlast worst-case cold-start retrieval
    # latency (embedding model load on first use can take 60s+) -- these
    # two real /search calls must land in the same fixed window regardless
    # of how long the first one takes.
    settings = _settings_with(rate_limit_enabled=True, rate_limit_requests=1, rate_limit_window_seconds=600)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    acme_key = await db_session.make_key("acme")

    first = await client.post(
        "/api/v1/search", json={"query": "policy"}, headers={"X-API-Key": acme_key}
    )
    second = await client.post(
        "/api/v1/search", json={"query": "policy"}, headers={"X-API-Key": acme_key}
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers


async def test_rate_limit_is_scoped_per_api_key_not_global(client, db_session, monkeypatch):
    # Window must comfortably outlast worst-case cold-start retrieval
    # latency (embedding model load on first use can take 60s+) -- these
    # two real /search calls must land in the same fixed window regardless
    # of how long the first one takes.
    settings = _settings_with(rate_limit_enabled=True, rate_limit_requests=1, rate_limit_window_seconds=600)
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    acme_key = await db_session.make_key("acme")
    globex_key = await db_session.make_key("globex")

    acme_response = await client.post(
        "/api/v1/search", json={"query": "policy"}, headers={"X-API-Key": acme_key}
    )
    globex_response = await client.post(
        "/api/v1/search", json={"query": "PTO"}, headers={"X-API-Key": globex_key}
    )

    assert acme_response.status_code == 200
    assert globex_response.status_code == 200  # separate budget, unaffected by acme's usage
