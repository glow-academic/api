"""Provider permissions context + shared save helpers.

Permissions context:
  1. resolve_provider_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_provider_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → providers_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.model.search import search_models
from app.tools.artifacts.provider.get import (
    get_providers as get_provider_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.providers.create import (
    create_provider as create_provider_resource,
)

if TYPE_CHECKING:
    from app.infra.provider.create import CreateProviderItem, ProviderFieldError
    from app.infra.provider.types import (
        UpdateProviderItem,
    )


@dataclass(frozen=True)
class ProviderPermissionsContext:
    """Lightweight context for provider permission checks."""

    exists: bool
    department_ids: list[UUID]
    active_model_count: int


async def resolve_provider_permissions_context(
    conn: asyncpg.Connection,
    provider_id: UUID,
) -> ProviderPermissionsContext:
    """Fetch just what's needed for provider permission checks.

    Two black-box tool calls:
      1. get_provider_artifacts → department_ids
      2. search_models(provider_ids=...) → any active models?
    """
    artifacts = await get_provider_artifacts(
        conn,
        [provider_id],
        departments=True,
    )

    if not artifacts:
        return ProviderPermissionsContext(
            exists=False,
            department_ids=[],
            active_model_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])

    _, total = await search_models(
        conn,
        provider_ids=[provider_id],
        active_only=True,
        limit_count=1,
    )

    return ProviderPermissionsContext(
        exists=True,
        department_ids=department_ids,
        active_model_count=total,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both provider_create and provider_update
# ---------------------------------------------------------------------------


async def resolve_provider_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateProviderItem | UpdateProviderItem,
    is_create: bool,
) -> list[ProviderFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments, active_flag):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.provider.create import ProviderFieldError

    errors: list[ProviderFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Match resources ---

    if item.active_flag is not None and item.active_flag_id is None:
        results = await search_flags(
            conn,
            redis,
            search=None,
            flag_type="provider_active",
            limit_count=100,
        )
        match = next((r for r in results if r.type == "provider_active"), None)
        if match and match.id:
            if item.active_flag:
                item.active_flag_id = match.id
        elif item.active_flag:
            errors.append(
                ProviderFieldError(
                    field="active_flag", message="Active flag resource not found"
                )
            )

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids: list[UUID] = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    ProviderFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(ProviderFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
) -> UUID:
    """Create a providers_resource snapshot by hydrating IDs to values.

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

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_provider_resource(
            conn,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            redis=redis,
            department_ids=department_ids,
        )
    return result.id
