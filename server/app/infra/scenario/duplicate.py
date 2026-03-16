"""Scenario duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_scenarios — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (scenario_active, value=false)
  6. create_scenario — new artifact with original's IDs + new name + inactive flag
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions import compute_can_duplicate
from app.infra.scenario.types import (
    DuplicateScenarioApiResponse,
)
from app.tools.artifacts.scenario.create import (
    create_scenario as create_scenario_artifact,
)
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def duplicate_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    scenario_id: UUID,
    session_id: UUID | None = None,
) -> DuplicateScenarioApiResponse:
    """Scenario duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_scenarios -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. search_flags -> find inactive flag (scenario_active, value=false)
      6. create_scenario -> new artifact with original IDs + inactive flag
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
            detail="You don't have permission to duplicate this scenario.",
        )

    # -- Step 3: Fetch original scenario with all junctions ---------------------

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

        # -- Step 4: Create new name resource ---------------------------------------

        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(conn, original.name_ids, redis)
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
            )

    # -- Step 7: Invalidate cache -----------------------------------------------

    await invalidate_tags(["scenarios"], redis=redis)

    return DuplicateScenarioApiResponse(
        success=True,
        scenario_id=result.id,
        message=f"Scenario '{original_name}' duplicated successfully",
    )
