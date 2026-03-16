"""Eval permissions context + shared save helpers.

Permissions context:
  1. resolve_eval_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_eval_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → evals_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.eval.get import get_evals as get_eval_artifacts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.evals.create import (
    create_eval as create_eval_resource,
)
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

if TYPE_CHECKING:
    from app.infra.eval.create import CreateEvalItem, EvalFieldError
    from app.infra.eval.types import (
        UpdateEvalItem,
    )


@dataclass(frozen=True)
class EvalPermissionsContext:
    """Lightweight context for eval permission checks."""

    exists: bool
    department_ids: list[UUID]


async def resolve_eval_permissions_context(
    conn: asyncpg.Connection,
    eval_id: UUID,
) -> EvalPermissionsContext:
    """Fetch just what's needed for eval permission checks.

    Single black-box tool call:
      1. get_eval_artifacts → department_ids
    """
    artifacts = await get_eval_artifacts(
        conn,
        [eval_id],
        departments=True,
    )

    if not artifacts:
        return EvalPermissionsContext(
            exists=False,
            department_ids=[],
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])

    return EvalPermissionsContext(
        exists=True,
        department_ids=department_ids,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both eval_create and eval_update
# ---------------------------------------------------------------------------


async def resolve_eval_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateEvalItem | UpdateEvalItem,
    is_create: bool,
) -> list[EvalFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.eval.create import EvalFieldError

    errors: list[EvalFieldError] = []

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
                    EvalFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(EvalFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
) -> UUID:
    """Create an evals_resource snapshot by hydrating IDs to values.

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
        result = await create_eval_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            model_ids=model_ids,
            model_rubric_ids=model_rubric_ids,
            model_flag_ids=model_flag_ids,
            model_position_ids=model_position_ids,
        )
    return result.id
