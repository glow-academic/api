"""Canonical shared invocation get operation.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_invocation_context — draft-only → hydrated resources
  3. score_tools — tool graph + artifact resources → per-resource tool picks
  4. Pure Python — response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.invocation.context import resolve_invocation_context
from app.infra.tool_graph import score_tools
from app.infra.invocation.types import (
    BaseSuiteSection,
    GetSuiteResponse,
    SuiteDepartmentSection,
    SuiteDescriptionSection,
    SuiteEndpointSection,
    SuiteFlagSection,
    SuiteKeySection,
    SuiteModalitySection,
    SuiteNameSection,
    SuitePricingSection,
    SuiteQualitySection,
    SuiteReasoningLevelSection,
    SuiteTemperatureLevelSection,
    SuiteValueSection,
    SuiteVoiceSection,
)

# =============================================================================
# Constants
# =============================================================================

INVOCATION_BUNDLE_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "values",
    "flags",
    "departments",
    "keys",
    "endpoints",
    "modalities",
    "temperature_levels",
    "pricing",
    "reasoning_levels",
    "qualities",
    "voices",
}

# Section class mapping for building typed sections
_SECTION_CLASSES: dict[str, type] = {
    "names": SuiteNameSection,
    "descriptions": SuiteDescriptionSection,
    "values": SuiteValueSection,
    "flags": SuiteFlagSection,
    "departments": SuiteDepartmentSection,
    "keys": SuiteKeySection,
    "endpoints": SuiteEndpointSection,
    "modalities": SuiteModalitySection,
    "temperature_levels": SuiteTemperatureLevelSection,
    "pricing": SuitePricingSection,
    "reasoning_levels": SuiteReasoningLevelSection,
    "qualities": SuiteQualitySection,
    "voices": SuiteVoiceSection,
}


# =============================================================================
# Client/BFF Layer — composable infra architecture
# =============================================================================


async def get_invocation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    test_id: UUID,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    descriptions_search: str | None = None,
    bypass_cache: bool = False,
) -> GetSuiteResponse:
    """HTTP-facing bundle response using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_invocation_context(group_id, draft_id) → hydrated resources
      3. score_tools(tool_graph, INVOCATION_BUNDLE_RESOURCES) → per-resource tool picks
      4. Pure Python: response assembly
    """

    # ── Step 1: Common context (profile → tool_graph + runs) ──────────────

    async with pool.acquire() as conn:
        common = await resolve_common_context(
            conn,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            draft_id=draft_id,
            test_id=test_id,
            bypass_cache=bypass_cache,
        )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )
    group_id = common.profile.group_id
    if group_id is None:
        raise HTTPException(status_code=400, detail="Failed to resolve group context.")

    profile = common.profile

    # ── Step 2: Invocation context (draft-only) ───────────────────────────

    invocation = await resolve_invocation_context(
        pool,
        redis,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        descriptions_search=descriptions_search,
        bypass_cache=bypass_cache,
    )

    # ── Step 3: Tool scoring ──────────────────────────────────────────────

    scores = score_tools(common.tool_graph, INVOCATION_BUNDLE_RESOURCES)

    # ── Step 4: Response assembly ─────────────────────────────────────────

    def _section(resource_key: str) -> BaseSuiteSection:
        cls = _SECTION_CLASSES[resource_key]
        pair = invocation.resources.get(resource_key)
        if not pair:
            return cls(show=True, required=False)
        return cls(
            show=True,
            required=False,
            show_ai_generate=scores.best.get(resource_key) is not None,
            current=pair.selected or None,
            resources=pair.suggestions or None,
        )

    return GetSuiteResponse(
        test_id=test_id,
        profile_has_access=True,
        draft_version=invocation.draft_version,
        group_id=group_id,
        names=_section("names"),
        descriptions=_section("descriptions"),
        values=_section("values"),
        flags=_section("flags"),
        departments=_section("departments"),
        keys=_section("keys"),
        endpoints=_section("endpoints"),
        modalities=_section("modalities"),
        temperature_levels=_section("temperature_levels"),
        pricing=_section("pricing"),
        reasoning_levels=_section("reasoning_levels"),
        qualities=_section("qualities"),
        voices=_section("voices"),
    )
