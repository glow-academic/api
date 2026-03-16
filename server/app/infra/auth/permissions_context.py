"""Auth permissions context + shared save helpers.

Permissions context:
  1. resolve_auth_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_auth_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → auths_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.auth.get import (
    get_auths as get_auth_artifacts,
)
from app.tools.artifacts.setting.search import (
    search_settings as search_setting_artifacts,
)
from app.tools.resources.auths.create import (
    create_auth as create_auth_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.protocols.create import create_protocol
from app.tools.resources.protocols.get import get_protocols
from app.tools.resources.slugs.create import create_slug
from app.tools.resources.slugs.get import get_slugs

if TYPE_CHECKING:
    from app.infra.auth.create import AuthFieldError, CreateAuthItem
    from app.infra.auth.types import (
        UpdateAuthItem,
    )


@dataclass(frozen=True)
class AuthPermissionsContext:
    """Lightweight context for auth permission checks."""

    exists: bool
    department_ids: list[UUID]
    active_settings_count: int


async def resolve_auth_permissions_context(
    conn: asyncpg.Connection,
    auth_id: UUID,
) -> AuthPermissionsContext:
    """Fetch just what's needed for auth permission checks.

    Two black-box tool calls:
      1. get_auth_artifacts → department_ids, auth_ids (resource IDs)
      2. search_settings(auth_ids=...) → count of active settings referencing this auth
    """
    artifacts = await get_auth_artifacts(
        conn,
        [auth_id],
        departments=True,
        auths=True,
    )

    if not artifacts:
        return AuthPermissionsContext(
            exists=False,
            department_ids=[],
            active_settings_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])
    auth_resource_ids = list(artifact.auth_ids or [])

    # Count active settings referencing this auth's resource IDs
    active_settings_count = 0
    if auth_resource_ids:
        _, total = await search_setting_artifacts(
            conn,
            auth_ids=auth_resource_ids,
            active_only=True,
            limit_count=1,
        )
        active_settings_count = total

    return AuthPermissionsContext(
        exists=True,
        department_ids=department_ids,
        active_settings_count=active_settings_count,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both auth_create and auth_update
# ---------------------------------------------------------------------------


async def resolve_auth_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateAuthItem | UpdateAuthItem,
    is_create: bool,
) -> list[AuthFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.auth.create import AuthFieldError

    errors: list[AuthFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    if hasattr(item, "slug") and item.slug is not None and item.slug_id is None:
        result = await create_slug(conn, item.slug, redis)
        item.slug_id = result.id

    if (
        hasattr(item, "protocol")
        and item.protocol is not None
        and item.protocol_ids is None
    ):
        result = await create_protocol(conn, item.protocol, redis)
        item.protocol_ids = [result.id]

    # --- Match resources ---

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    AuthFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None and item.name is None:
            errors.append(AuthFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None,
    slug_id: UUID | None = None,
    protocol_ids: list[UUID] | None = None,
) -> UUID:
    """Create an auths_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, [description_id], redis, bypass_cache=True
            )

    async def _get_slug() -> list:
        if not slug_id:
            return []
        async with pool.acquire() as conn:
            return await get_slugs(conn, [slug_id], redis, bypass_cache=True)

    async def _get_protocols() -> list:
        if not protocol_ids:
            return []
        async with pool.acquire() as conn:
            return await get_protocols(conn, protocol_ids, redis, bypass_cache=True)

    names, descriptions, slugs, protocols = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_slug(),
        _get_protocols(),
    )

    async with pool.acquire() as conn:
        result = await create_auth_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            slug=slugs[0].value if slugs else None,
            protocol=protocols[0].value if protocols else None,
        )
    return result.id
