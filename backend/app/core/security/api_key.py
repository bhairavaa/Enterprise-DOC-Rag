import hashlib
import secrets

KEY_PREFIX = "edr"
PREFIX_DISPLAY_CHARS = 12
"""API keys are high-entropy random tokens, not user passwords — unlike
passwords, they don't need slow/salted hashing to resist brute force (the
token itself already has 256 bits of entropy). A fast SHA-256 digest over
the full key is the standard approach (mirrors GitHub/Stripe-style tokens).
key_prefix (the token's first few chars) is stored in the clear so a key can
be identified/revoked by prefix without ever storing the full secret."""


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, key_prefix, key_hash). full_key is shown to the
    caller exactly once at creation time and never persisted anywhere."""
    full_key = f"{KEY_PREFIX}_{secrets.token_urlsafe(32)}"
    key_prefix = full_key[:PREFIX_DISPLAY_CHARS]
    return full_key, key_prefix, hash_api_key(full_key)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
