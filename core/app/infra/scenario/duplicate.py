"""Scenario duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_scenarios — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (scenario_active, value=false)
  6. create_scenario — new artifact with original's IDs + new name + inactive flag
7. canonical refresh via refresh_scenario_impl
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.scenario.permissions import compute_can_duplicate
from app.infra.scenario.refresh import refresh_scenario_impl
from app.infra.scenario.types import (
    DuplicateScenarioApiResponse,
    ListScenarioApiScenario,
)
from app.tools.artifacts.scenario.create import (
    create_scenario as create_scenario_artifact,
)
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "scenario"


async def duplicate_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DuplicateScenarioApiResponse:
    """Scenario duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_scenarios -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. search_flags -> find inactive flag (scenario_active, value=false)
      6. create_scenario -> new artifact with original IDs + inactive flag
      7. canonical refresh via refresh_scenario_impl
    """
    scenario_id = id  # alias: tools send 'id', internal code uses 'scenario_id'

    # -- Step 1: Profile context ------------------------------------------------

    with timed("profile"):
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

    # -- Step 2: Permission check (role-level) ----------------------------------
    # The department-subset guard runs after the original is fetched (below).
    # This early gate covers the ack short-circuit, which never fetches the
    # original — it only confirms a pending row whose first call already
    # passed the full (dept-aware) check.

    with timed("permissions"):
        if not compute_can_duplicate(role_level=profile.role_level, role_permissions=profile.role_permissions):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to duplicate this scenario.",
            )

    # -- Ack short-circuit ------------------------------------------------------

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending scenario duplicate for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_scenario_artifact(
                        conn,
                        id=target_id,
                        soft=False,
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="duplicate",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DuplicateScenarioApiResponse(
            success=True,
            scenario_id=target_id,
            message="Duplicate accepted" if accept else "Duplicate rejected",
            idempotency_key=idempotency_key,
        )

    # -- Step 3: Fetch original scenario with all junctions ---------------------

    with timed("hydrate"):
      async with pool.acquire() as conn:
        originals = await get_scenarios(
            conn,
            [scenario_id],
            names=True,
            descriptions=True,
            departments=True,
            documents=True,
            images=True,
            objectives=True,
            options=True,
            parameter_fields=True,
            personas=True,
            problem_statements=True,
            questions=True,
            videos=True,
            scenarios=True,
        )

        if not originals:
            raise HTTPException(
                status_code=404,
                detail=f"Scenario {scenario_id} not found.",
            )

        original = originals[0]

    # -- Step 3b: Department-subset guard ---------------------------------------
    # Non-top-level users must belong to ALL of the original's departments,
    # else a Dept-A actor could clone a Dept-B scenario they cannot even edit.
    if not compute_can_duplicate(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        scenario_department_ids=original.department_ids,
        user_department_ids=profile.department_ids,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this scenario.",
        )

    async with pool.acquire() as conn:
        # -- Step 4: Create new name resource ---------------------------------------

        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(pool, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

        # -- Step 5: Find inactive flag (scenario_active, value=false) --------------

        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="scenario_active",
            scenario=True,
            limit_count=10,
        )
        inactive_match = next((f for f in flag_results if not f.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    # -- Step 6: Create new scenario artifact with inactive flag ----------------

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_scenario_artifact(
                conn,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                document_ids=original.document_ids,
                image_ids=original.image_ids,
                objective_ids=original.objective_ids,
                option_ids=original.option_ids,
                parameter_field_ids=original.parameter_field_ids,
                persona_ids=original.persona_ids,
                problem_statement_ids=original.problem_statement_ids,
                question_ids=original.question_ids,
                video_ids=original.video_ids,
                scenario_ids=original.scenario_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # -- Step 7: Canonical refresh ----------------------------------------------

    with timed("refresh"):
        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or result.id,
        )

    # Hydrate full row content for the client ghost rail (skip when soft).
    scenarios: list[ListScenarioApiScenario] | None = None
    if not soft:
        from app.infra.scenario.hydrate_list_rows import hydrate_scenario_list_rows
        scenarios = await hydrate_scenario_list_rows(
            pool, redis, profile_id=profile_id, scenario_ids=[result.id],
        )

    return DuplicateScenarioApiResponse(
        success=True,
        scenario_id=result.id,
        message="Scenario duplicated (pending acceptance)" if soft else f"Scenario '{original_name}' duplicated successfully",
        idempotency_key=idempotency_key,
        scenarios=scenarios,
    )
