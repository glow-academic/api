"""Resolve key decryption — composes canonical black boxes.

Given a profile_id and key_id:
  1. resolve_profile_identity_context → identity check + actor_name
  2. get_keys → fetch the encrypted key
  3. decrypt_api_key → decrypt

No inline SQL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.resources.keys.get import get_keys
from app.utils.auth.decrypt_api_key import decrypt_api_key

ResolveProfileIdentityFn = Callable[..., Awaitable[object | None]]
GetKeysFn = Callable[..., Awaitable[list[object]]]
DecryptApiKeyFn = Callable[[str], str]


@dataclass(frozen=True)
class DecryptResult:
    """Result of a key decryption."""

    key: str
    name: str
    actor_name: str


async def resolve_decrypt(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    key_id: UUID,
    bypass_cache: bool = False,
    resolve_profile_identity_fn: ResolveProfileIdentityFn | None = None,
    get_keys_fn: GetKeysFn | None = None,
    decrypt_api_key_fn: DecryptApiKeyFn | None = None,
) -> DecryptResult:
    """Decrypt a key using canonical black boxes.

    Raises ValueError for missing profile or key.
    """
    resolve_profile_identity_fn = (
        resolve_profile_identity_fn or resolve_profile_identity_context
    )
    get_keys_fn = get_keys_fn or get_keys
    decrypt_api_key_fn = decrypt_api_key_fn or decrypt_api_key

    identity = await resolve_profile_identity_fn(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )
    if not identity:
        raise ValueError(f"Profile not found: {profile_id}")

    async with pool.acquire() as conn:
        keys = await get_keys_fn(conn, [key_id], redis, bypass_cache=bypass_cache)
    if not keys:
        raise ValueError(f"Key not found: {key_id}")

    key_resource = keys[0]
    decrypted = decrypt_api_key_fn(key_resource.key)

    return DecryptResult(
        key=decrypted,
        name=key_resource.name,
        actor_name=identity.name,
    )
