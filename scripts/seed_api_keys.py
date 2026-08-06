"""Creates one demo API key per sample tenant (acme, globex) for local
trying-out of the app — prints each key exactly once, matching how a real
key issuance flow works (the raw secret is never stored or shown again).

Usage: python scripts/seed_api_keys.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.security.api_key import generate_api_key  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.api_key import ApiKey  # noqa: E402


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for tenant_id in ["acme", "globex"]:
            full_key, key_prefix, key_hash = generate_api_key()
            session.add(
                ApiKey(
                    tenant_id=tenant_id,
                    name=f"{tenant_id}-demo-key",
                    key_hash=key_hash,
                    key_prefix=key_prefix,
                    allowed_filters={},
                    is_admin=False,
                )
            )
            print(f"{tenant_id}: {full_key}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
