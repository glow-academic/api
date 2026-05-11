"""Resolve websocket context — multi-artifact composition + system resolution.

Given a profile_id and list of artifact requests, resolves:
  1. Common context (profile + tool_graph + runs)
  2. Each artifact context in parallel (via resolver registry)
  3. Cross-artifact tool scoring (picks best system per resource)
  4. System contexts for winning systems in parallel
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

from app.infra.attempt.context import resolve_attempt_context
from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.persona.context import resolve_persona_context
from app.infra.system_context import resolve_system_context
from app.infra.tool_graph import score_tools
from app.infra.types import (
    ArtifactContext,
    ArtifactRequest,
    WebsocketContext,
)

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
    modalities: list[str] | None = None,
    bypass_cache: bool = False,
) -> WebsocketContext | None:
    """Resolve context for AI generation — agent chain + tool scoring.

    Steps:
      1. resolve_common_context(profile_id) → profile, tool_graph
      2. Score tools using static scoring_resources from artifact config
      3. Collect winning system_ids from scored tools
      4. Resolve system contexts in parallel (agents, models, providers, tools)
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

    scores = score_tools(common.tool_graph, all_scoring_resources, modalities=modalities)

    # ── Step 3: Collect winning system_ids ────────────────────────────────

    system_ids: set[UUID] = set()
    for best_tool in scores.best.values():
        if best_tool is not None:
            system_ids.add(best_tool.system_id)

    # ── Step 4: Resolve system contexts in parallel ──────────────────────

    if system_ids:
        system_contexts = await asyncio.gather(
            *[
                resolve_system_context(
                    pool,
                    redis,
                    system_id=sid,
                    bypass_cache=bypass_cache,
                )
                for sid in system_ids
            ]
        )
        system_contexts = [sc for sc in system_contexts if sc is not None]
    else:
        system_contexts = []

    # ── Step 5: Dedupe + flatten ──────────────────────────────────────────

    all_agents = dedupe_by_id([a for sc in system_contexts for a in sc.agents])
    all_models = dedupe_by_id([m for sc in system_contexts for m in sc.models])
    all_providers = dedupe_by_id([p for sc in system_contexts for p in sc.providers])
    all_tools = dedupe_by_id([t for sc in system_contexts for t in sc.tools])
    all_args = dedupe_by_id([a for sc in system_contexts for a in sc.args])
    all_args_outputs = dedupe_by_id(
        [ao for sc in system_contexts for ao in sc.args_outputs]
    )
    all_permissions = dedupe_by_id(
        [p for sc in system_contexts for p in sc.permissions]
    )
    all_prompts = dedupe_by_id([p for sc in system_contexts for p in sc.prompts])
    all_instructions = dedupe_by_id(
        [i for sc in system_contexts for i in sc.instructions]
    )
    all_tool_instructions = dedupe_by_id(
        [i for sc in system_contexts for i in sc.tool_instructions]
    )
    all_rubrics = dedupe_by_id([r for sc in system_contexts for r in sc.rubrics])

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
        tool_graph=common.tool_graph,
    )
