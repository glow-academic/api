"""Resolve websocket context — multi-artifact composition + agent resolution.

Given a profile_id and list of artifact requests, resolves:
  1. Common context (profile + tool_graph + runs)
  2. Score tools using static scoring_resources from artifact config
  3. Collect winning agent_ids from scored tools
  4. Resolve agent contexts in parallel (agents, models, providers, tools)
  5. Compiled, namespaced WebsocketContext

Composes existing infra functions — no raw SQL.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.attempt.context import resolve_attempt_context
from app.infra.persona.context import resolve_persona_context
from app.infra.tool_graph import score_tools
from app.infra.types import (
    ArtifactContext,
    ArtifactRequest,
    WebsocketContext,
)
from app.tools.resources.agents.get import get_agents
from app.tools.resources.args.get import get_args
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.models.get import get_models
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.prompts.get import get_prompts
from app.tools.resources.providers.get import get_providers
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.tools.get import get_tools

# Scoring resource sets per artifact type (avoids importing route-layer modules)
PERSONA_SCORING_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "colors",
    "icons",
    "instructions",
    "flags",
    "departments",
    "parameter_fields",
    "examples",
    "voices",
}
# Attempt generation currently needs both chat bootstrap resources and grade resources.
ATTEMPT_SCORING_RESOURCES: set[str] = {
    "personas",
    "scenarios",
    "parameters",
    "fields",
    "feedbacks",
    "strengths",
    "improvements",
    "analyses",
    "highlights",
    "replacements",
}
# Test grading — the grading agent scores agent output against a rubric.
TEST_SCORING_RESOURCES: set[str] = {
    "feedbacks",
    "grades",
}
# TODO: SCENARIO_SCORING_RESOURCES, SIMULATION_SCORING_RESOURCES, etc.


# ---------------------------------------------------------------------------
# Artifact resolver registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArtifactResolverConfig:
    """Configuration for resolving one artifact type's context."""

    resolver: Callable[..., Coroutine[Any, Any, ArtifactContext]]
    scoring_resources: set[str]
    id_kwarg: str  # kwarg name for artifact ID (e.g., "persona_id")


async def _resolve_attempt_context_for_websocket(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    attempt_id: UUID,
    bypass_cache: bool = False,
    **_ignored: Any,
) -> ArtifactContext:
    """Adapter for attempt context into the generic websocket registry."""
    return await resolve_attempt_context(
        pool,
        redis,
        attempt_id=attempt_id,
        bypass_cache=bypass_cache,
    )


async def _resolve_test_context_for_websocket(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    bypass_cache: bool = False,
    **_ignored: Any,
) -> ArtifactContext:
    """Test grading has no artifact-specific context — just tool scoring."""
    return ArtifactContext(resources={}, entries={})


ARTIFACT_RESOLVERS: dict[str, ArtifactResolverConfig] = {
    "attempt": ArtifactResolverConfig(
        resolver=_resolve_attempt_context_for_websocket,
        scoring_resources=ATTEMPT_SCORING_RESOURCES,
        id_kwarg="attempt_id",
    ),
    "persona": ArtifactResolverConfig(
        resolver=resolve_persona_context,
        scoring_resources=PERSONA_SCORING_RESOURCES,
        id_kwarg="persona_id",
    ),
    "test": ArtifactResolverConfig(
        resolver=_resolve_test_context_for_websocket,
        scoring_resources=TEST_SCORING_RESOURCES,
        id_kwarg="test_id",
    ),
    # TODO: "scenario", "simulation", "cohort"
}


# ---------------------------------------------------------------------------
# resolve_websocket_context
# ---------------------------------------------------------------------------


async def resolve_websocket_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    requests: list[ArtifactRequest],
    bypass_cache: bool = False,
) -> WebsocketContext | None:
    """Resolve context for AI generation — agent chain + tool scoring.

    Steps:
      1. resolve_common_context(profile_id) → profile, tool_graph
      2. Score tools using static scoring_resources from artifact config
      3. Collect winning agent_ids from scored tools
      4. Resolve agent contexts (agents → models, providers, tools, etc.)
      5. Dedupe + flatten all resolved config
      6. Return WebsocketContext
    """

    # ── Step 1: Common context (profile + tool_graph) ───────────────────

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )

    if common is None:
        return None

    profile = common.profile

    # ── Step 2: Tool scoring (uses static scoring_resources from config) ──

    all_scoring_resources: set[str] = set()
    for req in requests:
        config = ARTIFACT_RESOLVERS.get(req.artifact_type)
        if config is None:
            raise ValueError(f"Unknown artifact type: {req.artifact_type}")
        all_scoring_resources.add(req.artifact_type)
        all_scoring_resources |= config.scoring_resources

    scores = score_tools(common.tool_graph, all_scoring_resources)

    # ── Step 3: Collect winning agent_ids ────────────────────────────────

    agent_ids: set[UUID] = set()
    for best_tool in scores.best.values():
        if best_tool is not None:
            agent_ids.add(best_tool.agent_id)

    if not agent_ids:
        return WebsocketContext(
            scores=scores,
            agents=[],
            models=[],
            providers=[],
            tools=[],
            args=[],
            args_outputs=[],
            permissions=[],
            prompts=[],
            instructions=[],
            tool_instructions=[],
            rubrics=[],
            profile=profile,
            resolution_strategy=None,
            resolution_threshold=None,
        )

    # ── Step 4: Resolve agent contexts ──────────────────────────────────
    # Fetch agents, then hydrate their full resource chain (models, tools,
    # providers, args, prompts, instructions, rubrics).

    async with pool.acquire() as conn:
        agents = await get_agents(
            conn, list(agent_ids), redis, bypass_cache
        )

    if not agents:
        return WebsocketContext(
            scores=scores,
            agents=[],
            models=[],
            providers=[],
            tools=[],
            args=[],
            args_outputs=[],
            permissions=[],
            prompts=[],
            instructions=[],
            tool_instructions=[],
            rubrics=[],
            profile=profile,
            resolution_strategy=None,
            resolution_threshold=None,
        )

    # Collect IDs for next level
    model_ids = list({a.model_id for a in agents if a.model_id})
    tool_ids = list({tid for a in agents for tid in (a.tool_ids or [])})
    prompt_ids = list({a.prompt_id for a in agents if a.prompt_id})
    instruction_ids = list({iid for a in agents for iid in (a.instruction_ids or [])})
    rubric_ids = list({a.rubric_id for a in agents if a.rubric_id})

    # Parallel fetch: models + tools + prompts + instructions + rubrics

    async def _get_models() -> list:
        if not model_ids:
            return []
        async with pool.acquire() as conn:
            return await get_models(conn, model_ids, redis, bypass_cache)

    async def _get_tools() -> list:
        if not tool_ids:
            return []
        async with pool.acquire() as conn:
            return await get_tools(conn, tool_ids, redis, bypass_cache)

    async def _get_prompts() -> list:
        if not prompt_ids:
            return []
        async with pool.acquire() as conn:
            return await get_prompts(conn, prompt_ids, redis, bypass_cache)

    async def _get_instructions() -> list:
        if not instruction_ids:
            return []
        async with pool.acquire() as conn:
            return await get_instructions(conn, instruction_ids, redis, bypass_cache)

    async def _get_rubrics() -> list:
        if not rubric_ids:
            return []
        async with pool.acquire() as conn:
            return await get_rubrics(conn, rubric_ids, redis, bypass_cache)

    (
        models,
        tools_list,
        prompts_list,
        instructions_list,
        rubrics_list,
    ) = await asyncio.gather(
        _get_models(),
        _get_tools(),
        _get_prompts(),
        _get_instructions(),
        _get_rubrics(),
    )

    # Collect tool instruction_ids (Layer 3 response templates)
    tool_instruction_ids = list({
        t.instruction_id for t in tools_list
        if getattr(t, "instruction_id", None)
    })
    if tool_instruction_ids:
        async with pool.acquire() as conn:
            tool_instructions_list = await get_instructions(
                conn, tool_instruction_ids, redis, bypass_cache
            )
    else:
        tool_instructions_list = []

    # Collect IDs for final level
    provider_ids = list({m.provider_id for m in models if m.provider_id})
    args_ids = list({aid for t in tools_list for aid in (t.args_ids or [])})
    args_output_ids = list({aoid for t in tools_list for aoid in (t.args_output_ids or [])})
    permission_ids = list({pid for t in tools_list for pid in (t.permission_ids or [])})

    # Parallel fetch: providers + args + args_outputs + permissions

    async def _get_providers() -> list:
        if not provider_ids:
            return []
        async with pool.acquire() as conn:
            return await get_providers(conn, provider_ids, redis, bypass_cache)

    async def _get_args() -> list:
        if not args_ids:
            return []
        async with pool.acquire() as conn:
            return await get_args(conn, args_ids, redis, bypass_cache)

    async def _get_args_outputs() -> list:
        if not args_output_ids:
            return []
        async with pool.acquire() as conn:
            return await get_args_outputs(conn, args_output_ids, redis, bypass_cache)

    async def _get_permissions() -> list:
        if not permission_ids:
            return []
        async with pool.acquire() as conn:
            return await get_permissions(conn, permission_ids, redis, bypass_cache)

    providers, args_list, args_outputs_list, permissions_list = await asyncio.gather(
        _get_providers(),
        _get_args(),
        _get_args_outputs(),
        _get_permissions(),
    )

    # ── Step 5: Dedupe + flatten ──────────────────────────────────────────

    all_agents = dedupe_by_id(agents)
    all_models = dedupe_by_id(models)
    all_providers = dedupe_by_id(providers)
    all_tools = dedupe_by_id(tools_list)
    all_args = dedupe_by_id(args_list)
    all_args_outputs = dedupe_by_id(args_outputs_list)
    all_permissions = dedupe_by_id(permissions_list)
    all_prompts = dedupe_by_id(prompts_list)
    all_instructions = dedupe_by_id(instructions_list)
    all_tool_instructions = dedupe_by_id(tool_instructions_list)
    all_rubrics = dedupe_by_id(rubrics_list)

    # ── Step 6: Return ───────────────────────────────────────────────────

    return WebsocketContext(
        scores=scores,
        agents=all_agents,
        models=all_models,
        providers=all_providers,
        tools=all_tools,
        args=all_args,
        args_outputs=all_args_outputs,
        permissions=all_permissions,
        prompts=all_prompts,
        instructions=all_instructions,
        tool_instructions=all_tool_instructions,
        rubrics=all_rubrics,
        profile=profile,
        resolution_strategy=None,
        resolution_threshold=None,
    )
