from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.api_key import hash_api_key
from app.db.session import get_db_session
from app.models.api_key import ApiKey


async def get_current_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKey:
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(x_api_key))
    )
    api_key = result.scalar_one_or_none()

    if api_key is None or api_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key"
        )

    api_key.last_used_at = datetime.now(UTC)
    await session.commit()
    return api_key
