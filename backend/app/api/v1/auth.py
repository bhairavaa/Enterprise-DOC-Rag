from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security.api_key import generate_api_key
from app.db.session import get_db_session
from app.models.api_key import ApiKey
from app.schemas.auth import ApiKeyResponse, CreateApiKeyRequest, CreateApiKeyResponse

router = APIRouter(prefix="/auth", tags=["auth"])


async def require_bootstrap_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> None:
    """Gates key-management endpoints with a single shared secret
    (ADMIN_BOOTSTRAP_API_KEY) rather than a stored ApiKey row — there has to
    be some way to create the very first key. Everything downstream of key
    creation uses the normal X-API-Key + get_current_api_key path."""
    settings = get_settings()
    if x_admin_key != settings.admin_bootstrap_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")


@router.post(
    "/api-keys",
    response_model=CreateApiKeyResponse,
    dependencies=[Depends(require_bootstrap_admin)],
)
async def create_api_key(
    request: CreateApiKeyRequest, session: AsyncSession = Depends(get_db_session)
) -> CreateApiKeyResponse:
    full_key, key_prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        tenant_id=request.tenant_id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        allowed_filters=request.allowed_filters or {},
        is_admin=request.is_admin,
    )
    session.add(api_key)
    await session.commit()

    return CreateApiKeyResponse(api_key=full_key, key_prefix=key_prefix, tenant_id=request.tenant_id)


@router.get(
    "/api-keys", response_model=list[ApiKeyResponse], dependencies=[Depends(require_bootstrap_admin)]
)
async def list_api_keys(session: AsyncSession = Depends(get_db_session)) -> list[ApiKeyResponse]:
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return [ApiKeyResponse.model_validate(k) for k in result.scalars().all()]


@router.delete("/api-keys/{key_prefix}", dependencies=[Depends(require_bootstrap_admin)])
async def revoke_api_key(
    key_prefix: str, session: AsyncSession = Depends(get_db_session)
) -> dict[str, str]:
    result = await session.execute(select(ApiKey).where(ApiKey.key_prefix == key_prefix))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.revoked_at = datetime.now(UTC)
    await session.commit()
    return {"status": "revoked", "key_prefix": key_prefix}
