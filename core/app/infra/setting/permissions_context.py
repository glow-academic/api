"""Setting permissions context + shared save helpers.

Permissions context:
  1. resolve_setting_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_setting_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → settings_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.department_id_resolution import (
    resolve_department_ids_to_resource_ids,
)
from app.tools.artifacts.auth.get import (
    get_auths as get_auth_artifacts,
)
from app.tools.artifacts.provider.get import (
    get_providers as get_provider_artifacts,
)
from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.settings.create import (
    create_setting as create_setting_resource,
)

if TYPE_CHECKING:
    from app.infra.setting.types import (
        CreateSettingItem,
        SettingFieldError,
        UpdateSettingItem,
    )


@dataclass(frozen=True)
class SettingPermissionsContext:
    """Lightweight context for setting permission checks."""

    exists: bool
    department_ids: list[UUID]


async def resolve_setting_permissions_context(
    conn: asyncpg.Connection,
    setting_id: UUID,
) -> SettingPermissionsContext:
    """Fetch just what's needed for setting permission checks.

    Single black-box tool call:
      1. get_setting_artifacts → department_ids
    """
    artifacts = await get_setting_artifacts(
        conn,
        [setting_id],
        departments=True,
    )

    if not artifacts:
        return SettingPermissionsContext(
            exists=False,
            department_ids=[],
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])

    return SettingPermissionsContext(
        exists=True,
        department_ids=department_ids,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both setting_create and setting_update
# ---------------------------------------------------------------------------


async def resolve_setting_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateSettingItem | UpdateSettingItem,
    is_create: bool,
) -> list[SettingFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.setting.types import SettingFieldError

    errors: list[SettingFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

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
                    SettingFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Cross-artifact artifact ID → *_resource ID resolution ---
    #
    # ``auth_ids`` / ``provider_ids`` supplied by the client are *artifact* IDs
    # (that is what ``/auth/search`` and ``/provider/search`` surface).
    # ``setting_auths_junction.auths_id`` and
    # ``setting_providers_junction.providers_id`` are FK'd to ``auths_resource``
    # / ``providers_resource`` (the denormalized snapshot each artifact owns via
    # its own self-junction). Writing the artifact ID straight into the junction
    # violates the FK → HTTP 500. Resolve artifact IDs to their snapshot
    # resource IDs here; unknown IDs (e.g. an already-resolved resource ID) pass
    # through so the FK validates.
    if item.auth_ids:
        auth_artifacts = await get_auth_artifacts(
            conn, list(item.auth_ids), auths=True
        )
        auth_map = {
            a.id: a.auth_ids[0]
            for a in auth_artifacts
            if a.id and a.auth_ids
        }
        item.auth_ids = [auth_map.get(aid, aid) for aid in item.auth_ids]

    if item.provider_ids:
        provider_artifacts = await get_provider_artifacts(
            conn, list(item.provider_ids), providers=True
        )
        provider_map = {
            a.id: a.provider_ids[0]
            for a in provider_artifacts
            if a.id and a.provider_ids
        }
        item.provider_ids = [
            provider_map.get(pid, pid) for pid in item.provider_ids
        ]

    # Resolve department *artifact* ids -> departments_resource ids before
    # the junction write. ``/department/search`` surfaces artifact ids, but
    # every ``*_departments_junction.departments_id`` is FK'd to
    # ``departments_resource``; writing a raw artifact id violates the FK
    # (HTTP 500). #282 class, missed for the cross-cutting ``department_ids``
    # dimension. Unknown/already-resolved ids pass through. No raw SQL.
    item.department_ids = await resolve_department_ids_to_resource_ids(
        conn, getattr(item, "department_ids", None)
    )

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None and item.name is None:
            errors.append(SettingFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    system_ids: list[UUID] | None = None,
    mcp_id: UUID | None = None,
) -> UUID:
    """Create a settings_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        return await get_names(pool, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        return await get_descriptions(pool, [description_id], redis, bypass_cache=True
        )

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_setting_resource(
            conn,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            provider_key_ids=provider_key_ids,
            system_ids=system_ids,
            mcp_id=mcp_id,
            redis=redis,
        )
    return result.id
