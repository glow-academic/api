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

from app.infra.agent.context import resolve_agent_context
from app.infra.attempt.context import resolve_attempt_context
from app.infra.auth.context import resolve_auth_context
from app.infra.cohort.context import resolve_cohort_context
from app.infra.common_context import resolve_common_context
from app.infra.department.context import resolve_department_context
from app.infra.document.context import resolve_document_context
from app.infra.eval.context import resolve_eval_context
from app.infra.field.context import resolve_field_context
from app.infra.helpers import dedupe_by_id
from app.infra.model.context import resolve_model_context
from app.infra.parameter.context import resolve_parameter_context
from app.infra.persona.context import resolve_persona_context
from app.infra.profile.context import resolve_profile_context
from app.infra.provider.context import resolve_provider_context
from app.infra.rubric.context import resolve_rubric_context
from app.infra.scenario.context import resolve_scenario_context
from app.infra.setting.context import resolve_setting_context
from app.infra.simulation.context import resolve_simulation_context
from app.infra.system_context import resolve_system_context
from app.infra.tool.context import resolve_tool_context
from app.infra.tool_graph import resolve_tool_graph, score_tools
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
# Scenario generation — the agent fills problem statement, objectives, media,
# parameter fields, etc. Mirrors the resource bank that ``resolve_scenario_context``
# returns.
SCENARIO_SCORING_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "problem_statements",
    "flags",
    "departments",
    "personas",
    "documents",
    "parameters",
    "parameter_fields",
    "objectives",
    "images",
    "videos",
    "questions",
    "options",
    "fields",
    "conditional_parameters",
}
# Simulation generation — picks scenarios + per-scenario config.
SIMULATION_SCORING_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "scenarios",
    "scenario_flags",
    "scenario_positions",
    "scenario_rubrics",
    "scenario_time_limits",
    "rubrics",
}
# Cohort generation — picks simulations + profile-persona bindings.
COHORT_SCORING_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "simulations",
    "simulation_positions",
    "simulation_availability",
    "profiles",
    "profile_personas",
    "personas",
}
# CRUD-artifact scoring sets — derived from each artifact's resource bank
# (the ``"key": ResourcePair(...)`` entries in their respective context.py).
AGENT_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "models", "prompts", "instructions", "flags",
    "departments", "tools", "temperature_levels", "reasoning_levels", "voices",
    "qualities", "rubrics",
}
AUTH_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "protocols", "slugs", "items",
}
DEPARTMENT_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "settings",
}
DOCUMENT_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "parameter_fields",
    "parameters", "files", "images", "texts",
}
EVAL_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "models", "model_flags",
    "model_rubrics", "model_positions", "rubrics",
}
FIELD_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "conditional_parameters",
}
MODEL_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "values", "providers",
    "modalities", "temperature_levels", "pricing", "reasoning_levels",
    "qualities", "voices",
}
PARAMETER_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "parameter_fields",
}
PROFILE_SCORING_RESOURCES: set[str] = {
    "names", "emails", "flags", "departments", "roles",
}
PROVIDER_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "values", "endpoints", "keys",
}
RUBRIC_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "points",
    "standard_groups", "standards",
}
SETTING_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "colors", "flags", "departments", "logins",
    "systems", "mcp", "thresholds", "provider_keys", "auth_item_keys",
    "auth_item_values",
}
TOOL_SCORING_RESOURCES: set[str] = {
    "names", "descriptions", "flags", "departments", "args", "arg_positions",
    "args_outputs", "permissions", "instructions",
}
# System "generate" has no artifact-specific context — register an empty set.
SYSTEM_SCORING_RESOURCES: set[str] = set()


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


async def _resolve_system_context_for_websocket(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    bypass_cache: bool = False,
    **_ignored: Any,
) -> ArtifactContext:
    """System generation has no artifact-specific context — empty context."""
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
    "scenario": ArtifactResolverConfig(
        resolver=resolve_scenario_context,
        scoring_resources=SCENARIO_SCORING_RESOURCES,
        id_kwarg="scenario_id",
    ),
    "simulation": ArtifactResolverConfig(
        resolver=resolve_simulation_context,
        scoring_resources=SIMULATION_SCORING_RESOURCES,
        id_kwarg="simulation_id",
    ),
    "cohort": ArtifactResolverConfig(
        resolver=resolve_cohort_context,
        scoring_resources=COHORT_SCORING_RESOURCES,
        id_kwarg="cohort_id",
    ),
    # CRUD-artifact resolvers — wired so generate works for every artifact.
    "agent": ArtifactResolverConfig(
        resolver=resolve_agent_context,
        scoring_resources=AGENT_SCORING_RESOURCES,
        id_kwarg="agent_id",
    ),
    "auth": ArtifactResolverConfig(
        resolver=resolve_auth_context,
        scoring_resources=AUTH_SCORING_RESOURCES,
        id_kwarg="auth_id",
    ),
    "department": ArtifactResolverConfig(
        resolver=resolve_department_context,
        scoring_resources=DEPARTMENT_SCORING_RESOURCES,
        id_kwarg="department_id",
    ),
    "document": ArtifactResolverConfig(
        resolver=resolve_document_context,
        scoring_resources=DOCUMENT_SCORING_RESOURCES,
        id_kwarg="document_id",
    ),
    "eval": ArtifactResolverConfig(
        resolver=resolve_eval_context,
        scoring_resources=EVAL_SCORING_RESOURCES,
        id_kwarg="eval_id",
    ),
    "field": ArtifactResolverConfig(
        resolver=resolve_field_context,
        scoring_resources=FIELD_SCORING_RESOURCES,
        id_kwarg="field_id",
    ),
    "model": ArtifactResolverConfig(
        resolver=resolve_model_context,
        scoring_resources=MODEL_SCORING_RESOURCES,
        id_kwarg="model_id",
    ),
    "parameter": ArtifactResolverConfig(
        resolver=resolve_parameter_context,
        scoring_resources=PARAMETER_SCORING_RESOURCES,
        id_kwarg="parameter_id",
    ),
    "profile": ArtifactResolverConfig(
        resolver=resolve_profile_context,
        scoring_resources=PROFILE_SCORING_RESOURCES,
        id_kwarg="profile_id",
    ),
    "provider": ArtifactResolverConfig(
        resolver=resolve_provider_context,
        scoring_resources=PROVIDER_SCORING_RESOURCES,
        id_kwarg="provider_id",
    ),
    "rubric": ArtifactResolverConfig(
        resolver=resolve_rubric_context,
        scoring_resources=RUBRIC_SCORING_RESOURCES,
        id_kwarg="rubric_id",
    ),
    "setting": ArtifactResolverConfig(
        resolver=resolve_setting_context,
        scoring_resources=SETTING_SCORING_RESOURCES,
        id_kwarg="setting_id",
    ),
    "tool": ArtifactResolverConfig(
        resolver=resolve_tool_context,
        scoring_resources=TOOL_SCORING_RESOURCES,
        id_kwarg="tool_id",
    ),
    "system": ArtifactResolverConfig(
        resolver=_resolve_system_context_for_websocket,
        scoring_resources=SYSTEM_SCORING_RESOURCES,
        id_kwarg="entity_id",
    ),
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
    # tool_graph no longer carried on CommonContext — resolve directly.

    tool_graph = (
        await resolve_tool_graph(pool, profile.settings_id, redis, bypass_cache)
        if profile.settings_id
        else None
    )

    all_scoring_resources: set[str] = set()
    for req in requests:
        config = ARTIFACT_RESOLVERS.get(req.artifact_type)
        if config is None:
            raise ValueError(f"Unknown artifact type: {req.artifact_type}")
        all_scoring_resources.add(req.artifact_type)
        all_scoring_resources |= config.scoring_resources

    from app.infra.tool_graph import SettingsToolGraph
    scores = score_tools(
        tool_graph or SettingsToolGraph(tools=[]),
        all_scoring_resources,
        modalities=modalities,
    )

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
        tool_graph=tool_graph or SettingsToolGraph(tools=[]),
    )
