"""Provider duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_providers — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (provider_active, value=false)
  6. create_provider — new artifact with original's IDs + new name + inactive flag
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import compute_can_duplicate
from app.infra.provider.types import (
    DuplicateProviderApiResponse,
)
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)
from app.tools.artifacts.provider.get import get_providers
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def duplicate_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    provider_id: UUID,
    session_id: UUID | None = None,
) -> DuplicateProviderApiResponse:
    """Provider duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_providers -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. search_flags -> find inactive flag (provider_active, value=false)
      6. create_provider -> new artifact with original IDs + inactive flag
      7. invalidate_tags
    """

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check -----------------------------------------------

    if not compute_can_duplicate(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this provider.",
        )

    # -- Step 3: Fetch original provider with all junctions ---------------------

    async with pool.acquire() as conn:
        originals = await get_providers(
            conn,
            [provider_id],
            names=True,
            descriptions=True,
            departments=True,
            endpoints=True,
            keys=True,
            values=True,
            providers=True,
        )

        if not originals:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found.",
            )

        original = originals[0]

        # -- Step 4: Create new name resource ---------------------------------------

        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(conn, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

        # -- Step 5: Find inactive flag (provider_active, value=false) --------------

        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="provider_active",
            provider=True,
            limit_count=10,
        )
        inactive_match = next((f for f in flag_results if not f.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    # -- Step 6: Create new provider artifact with inactive flag ----------------

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_provider_artifact(
                conn,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                endpoint_ids=original.endpoint_ids,
                key_ids=original.key_ids,
                value_ids=original.value_ids,
                provider_ids=original.provider_ids,
                flag_ids=flag_ids,
            )

    # -- Step 7: Invalidate cache -----------------------------------------------

    await invalidate_tags(["providers"], redis=redis)

    return DuplicateProviderApiResponse(
        success=True,
        provider_id=result.id,
        message=f"Provider '{original_name}' duplicated successfully",
    )
