import time
from collections.abc import Callable, Coroutine
from functools import lru_cache
from typing import Any

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status

from app.config import get_settings
from app.core.security.dependencies import get_current_api_key
from app.models.api_key import ApiKey


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


async def enforce_rate_limit(identifier: str) -> None:
    """Fixed-window counter: `ratelimit:{identifier}:{window_index}` in
    Redis, incremented per call, expired after the window closes. Simpler
    and cheaper than a sliding-window log; the known tradeoff is a caller
    can burst up to ~2x the limit across a window boundary, which is an
    acceptable cost for the abuse/cost-control this exists for (LLM/embedding
    spend and reranker load, not billing-grade precision)."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    client = get_redis_client()
    now = time.time()
    window_index = int(now) // settings.rate_limit_window_seconds
    key = f"ratelimit:{identifier}:{window_index}"

    count = await client.incr(key)
    if count == 1:
        await client.expire(key, settings.rate_limit_window_seconds)

    if count > settings.rate_limit_requests:
        retry_after = settings.rate_limit_window_seconds - (int(now) % settings.rate_limit_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: {settings.rate_limit_requests} requests "
                f"per {settings.rate_limit_window_seconds}s for this API key."
            ),
            headers={"Retry-After": str(retry_after)},
        )


def rate_limiter(operation: str) -> Callable[[ApiKey], Coroutine[Any, Any, None]]:
    """Dependency factory, e.g. `Depends(rate_limiter("chat"))`. Each
    operation name tracks its own budget per API key -- /chat and /search
    don't share a counter, since they have different cost profiles."""

    async def _dependency(api_key: ApiKey = Depends(get_current_api_key)) -> None:
        await enforce_rate_limit(f"{operation}:{api_key.id}")

    return _dependency
