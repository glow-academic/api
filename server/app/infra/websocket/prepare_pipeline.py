"""Pure functions for the generation preparation pipeline.

Extracted from generate_prepare.py — all functions are pure (no I/O, no globals).
They accept resolved data and return structured results.

TODOs:
    - TODO: Resolve agent input modalities from model → modalities_resource (is_input)
            and pass to post_process_media_sentinels. Currently passes None (allow all).
    - TODO: Support multipart message persistence (text + image blocks) in MessageSpec.
            Currently raw_text is always a string even for media messages.
    - TODO: Build entry_actions alongside resource_actions in aggregate_tool_results.
            Currently only resource_type/resource_id are extracted.
    - TODO: Add resolution phase logic — compare competing soft units for the same
            (target_type, target_name) across agents, run test framework, promote winner.
"""

from __future__ import annotations

import copy
from typing import Any
from uuid import UUID

from app.infra.generation import render_developer_instructions
from app.infra.generation.media_context import (
    has_media_sentinels,
    post_process_media_sentinels,
)
from app.infra.websocket.prepare_types import (
    AgentDispatch,
    LLMConfig,
    MessageSpec,
)
from app.registry.modalities import get_tool_output_modalities
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_payload(
    *,
    resource_types_raw: list[str],
    artifact_type: str,
    valid_resource_types: list[str],
    entry_types: list[str],
    requires_draft: bool,
    draft_id: UUID | None,
) -> str | None:
    """Validate generation payload. Returns error string or None if valid."""
    if not resource_types_raw:
        return "resource_types must be provided"

    all_valid = set(valid_resource_types) | set(entry_types)
    invalid = [rt for rt in resource_types_raw if rt not in all_valid]
    if invalid:
        return f"Invalid resource types: {', '.join(invalid)}"

    if requires_draft and not draft_id:
        return f"draft_id is required for {artifact_type} generation"

    return None


# ---------------------------------------------------------------------------
# Agent group building
# ---------------------------------------------------------------------------


def compute_agent_modalities(
    agent_id: UUID,
    agents_by_id: dict[UUID, Any],
    tools_by_id: dict[UUID, Any],
) -> frozenset[str]:
    """Compute output modalities an agent supports from its tools."""
    agent = agents_by_id.get(agent_id)
    if not agent:
        return frozenset({"call"})
    modalities: set[str] = set()
    for tid in getattr(agent, "tool_ids", None) or []:
        tool = tools_by_id.get(tid)
        if tool:
            modalities |= get_tool_output_modalities(
                getattr(tool, "operation", None),
                getattr(tool, "resources", None),
                getattr(tool, "entries", None),
                getattr(tool, "artifacts", None),
            )
    return frozenset(modalities) if modalities else frozenset({"call"})


def build_agent_groups(
    *,
    resource_types: list[str],
    config_systems: list[Any],
    config_agents: list[Any],
    agents_by_id: dict[UUID, Any],
    tools_by_id: dict[UUID, Any],
    systems_by_id: dict[UUID, Any],
    resource_system_ids: dict[str, UUID],
    resource_agent_ids: dict[str, UUID],
    requested_modality: str = "call",
) -> dict[UUID, list[str]]:
    """Map resource_types → agent_id groups via system → agent resolution.

    Uses modality-aware scoring: prefers the most specialized agent whose
    tool-derived output modalities include the requested modality.

    Falls back through: systems → legacy resource_agent_ids → first agent.
    """
    agent_groups: dict[UUID, list[str]] = {}

    if config_systems:
        default_system_id = next(iter(systems_by_id), None)
        for rt in resource_types:
            system_id = resource_system_ids.get(rt) or default_system_id
            system = systems_by_id.get(system_id) if system_id else None
            candidate_ids = (getattr(system, "agent_ids", None) or []) if system else []
            candidates = [aid for aid in candidate_ids if aid in agents_by_id]
            if not candidates:
                continue

            # Score: prefer agents supporting requested modality with fewest total
            scored = []
            for aid in candidates:
                agent_mods = compute_agent_modalities(aid, agents_by_id, tools_by_id)
                if requested_modality in agent_mods:
                    scored.append((len(agent_mods), aid))

            if scored:
                scored.sort()
                resolved_id = scored[0][1]
            else:
                resolved_id = candidates[0]

            agent_groups.setdefault(resolved_id, []).append(rt)

    # Legacy fallback: resource_agent_ids
    if not agent_groups:
        for rt in resource_types:
            aid = resource_agent_ids.get(rt)
            if aid is not None:
                agent_groups.setdefault(aid, []).append(rt)

    if not agent_groups:
        for _rt, aid in resource_agent_ids.items():
            if aid is not None:
                agent_groups[aid] = resource_types
                break

    # Final fallback: first agent
    if not agent_groups and config_agents:
        first = config_agents[0]
        if first.id:
            agent_groups[first.id] = resource_types

    return agent_groups


# ---------------------------------------------------------------------------
# Jinja context
# ---------------------------------------------------------------------------


def dump_fetcher_result(result: object) -> dict[str, Any]:
    """Dump a fetcher result into a dict with resources, entries, config-chain fields."""
    dumped: dict[str, Any] = {}

    for ns in ("resources", "entries"):
        val = getattr(result, ns, None)
        if val and hasattr(val, "model_dump"):
            dumped[ns] = val.model_dump(mode="json")

    for key in (
        "agents",
        "systems",
        "models",
        "providers",
        "tools",
        "args",
        "args_outputs",
        "profile",
        "params",
    ):
        val = getattr(result, key, None)
        if val is None:
            continue
        if hasattr(val, "model_dump"):
            dumped[key] = val.model_dump(mode="json")
        elif isinstance(val, list):
            dumped[key] = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in val
            ]
        else:
            dumped[key] = val

    return dumped


def build_namespaced_context(
    artifact_results: dict[str, dict[str, dict[str, Any]]],
    entry_results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the namespaced Jinja context: artifacts.{name}.{operation}.{...}."""
    context: dict[str, Any] = {"artifacts": {}}

    for name, ops in artifact_results.items():
        context["artifacts"][name] = ops

    if entry_results:
        for name, ops in entry_results.items():
            context["artifacts"].setdefault(name, {}).update(ops)

    return context


# ---------------------------------------------------------------------------
# Tool enrichment
# ---------------------------------------------------------------------------


def enrich_tools_with_args(
    tool_dicts: list[dict[str, Any]],
    resource_tools: list[Any],
    config_args: list[Any],
) -> list[dict[str, Any]]:
    """Resolve args_ids on tools against pre-fetched args list."""
    if not tool_dicts or not resource_tools or not config_args:
        return tool_dicts

    arg_by_id: dict[Any, Any] = {}
    for arg in config_args:
        arg_id = getattr(arg, "id", None)
        if arg_id:
            arg_by_id[arg_id] = arg

    if not arg_by_id:
        return tool_dicts

    tool_arg_ids_by_name: dict[str, list[Any]] = {}
    for rt in resource_tools:
        name = getattr(rt, "name", None)
        a_ids = getattr(rt, "args_ids", None)
        if name and a_ids:
            tool_arg_ids_by_name[name] = a_ids

    if not tool_arg_ids_by_name:
        return tool_dicts

    for td in tool_dicts:
        t_name = td.get("name")
        if not t_name or t_name not in tool_arg_ids_by_name:
            continue

        arguments: dict[str, Any] = {}
        argument_descriptions: dict[str, str] = {}
        argument_defaults: dict[str, Any] = {}

        for arg_id in tool_arg_ids_by_name[t_name]:
            arg = arg_by_id.get(arg_id)
            if not arg:
                continue
            arg_name = getattr(arg, "name", None)
            if not arg_name:
                continue

            field_type = getattr(arg, "field_type", "string") or "string"
            required = bool(getattr(arg, "required", False))
            arguments[arg_name] = {"type": field_type, "required": required}

            desc = getattr(arg, "description", None)
            if desc:
                argument_descriptions[arg_name] = desc
            default_value = getattr(arg, "default_value", None)
            if default_value is not None and default_value != "":
                argument_defaults[arg_name] = default_value

        td["arguments"] = arguments
        td["argument_descriptions"] = argument_descriptions
        td["argument_defaults"] = argument_defaults

    return tool_dicts


def enrich_tools_with_args_outputs(
    tool_dicts: list[dict[str, Any]],
    resource_tools: list[Any],
    config_args_outputs: list[Any],
) -> list[dict[str, Any]]:
    """Attach _args_outputs to tools for output schema resolution."""
    if not tool_dicts or not resource_tools or not config_args_outputs:
        return tool_dicts

    tool_output_ids_by_name: dict[str, list[Any]] = {}
    for rt in resource_tools:
        name = getattr(rt, "name", None)
        ao_ids = getattr(rt, "args_output_ids", None)
        if name and ao_ids:
            tool_output_ids_by_name[name] = ao_ids

    if not tool_output_ids_by_name:
        return tool_dicts

    ao_by_id = {}
    for ao in config_args_outputs:
        ao_id = getattr(ao, "id", None)
        if ao_id:
            ao_by_id[ao_id] = ao

    for td in tool_dicts:
        t_name = td.get("name")
        if t_name and t_name in tool_output_ids_by_name:
            ao_list = []
            for ao_id in tool_output_ids_by_name[t_name]:
                ao = ao_by_id.get(ao_id)
                if ao:
                    ao_list.append(
                        {
                            "name": getattr(ao, "name", ""),
                            "template": getattr(ao, "template", ""),
                        }
                    )
            if ao_list:
                td["_args_outputs"] = ao_list

    return tool_dicts


def compute_createable_resources(config_tools: list[Any]) -> set[str]:
    """Compute the set of resource/entry types that have 'create' tools."""
    createable: set[str] = set()
    for tool in config_tools:
        if getattr(tool, "operation", None) == "create":
            type_name = (
                (getattr(tool, "resources", None) or [None])[0]
                or (getattr(tool, "entries", None) or [None])[0]
                or None
            )
            if type_name:
                createable.add(type_name)
    return createable


def compute_all_artifact_types(tool_dicts: list[dict[str, Any]]) -> list[str]:
    """Extract unique artifact types from all tools."""
    return list({a for td in tool_dicts for a in (td.get("artifacts") or []) if a})


# ---------------------------------------------------------------------------
# Per-agent dispatch building
# ---------------------------------------------------------------------------


def resolve_agent_config(
    agent: Any,
    models_by_id: dict[UUID, Any],
    providers_by_id: dict[UUID, Any],
) -> LLMConfig | None:
    """Walk agent → model → provider chain. Returns None if chain is broken."""
    model = models_by_id.get(agent.model_id) if agent.model_id else None
    if not model:
        logger.warning(f"Agent '{getattr(agent, 'name', '?')}' has no model — skipping")
        return None

    provider = (
        providers_by_id.get(model.provider_id)
        if getattr(model, "provider_id", None)
        else None
    )
    if not provider:
        logger.warning(
            f"Model '{getattr(model, 'name', '?')}' has no provider — skipping"
        )
        return None

    api_key = getattr(provider, "key", "") or ""
    if not api_key:
        logger.warning(
            f"No API key for provider '{getattr(provider, 'name', '')}' — skipping"
        )
        return None

    return LLMConfig(
        model=getattr(model, "value", None) or model.name,
        api_key=api_key,
        base_url=getattr(provider, "endpoint", "") or "",
        temperature=getattr(agent, "temperature", 0.0) or 0.0,
        reasoning=getattr(agent, "reasoning", None),
        provider=getattr(provider, "value", None)
        or getattr(provider, "name", "")
        or "",
        voice=getattr(agent, "voice", None),
        quality=getattr(agent, "quality", None),
    )


def build_agent_dispatch(
    *,
    agent_id: UUID,
    agent_resource_types: list[str],
    agent: Any,
    llm_config: LLMConfig,
    jinja_context_base: dict[str, Any],
    createable_resources: set[str],
    all_tool_dicts: list[dict[str, Any]],
    all_artifact_types: list[str],
    system_prompt: str,
    developer_instruction_templates: list[str],
    payload_metadata: dict[str, Any],
    save: bool | None,
) -> AgentDispatch:
    """Build a complete AgentDispatch for one agent (pure).

    Scopes resource/entry types, clones jinja context, renders instructions,
    builds message list, filters tools.
    """
    # Scope types
    scoped_resource_types = [
        rt for rt in agent_resource_types if rt in createable_resources
    ]
    scoped_entry_types = [
        rt for rt in agent_resource_types if rt not in createable_resources
    ]

    # Clone and inject per-agent context
    jinja_context = copy.deepcopy(jinja_context_base)
    jinja_context["resource_types"] = scoped_resource_types
    jinja_context["entry_types"] = scoped_entry_types
    jinja_context["artifact_types"] = all_artifact_types

    if "resources" in jinja_context:
        jinja_context["resources"]["types"] = scoped_resource_types
    if "entries" in jinja_context:
        jinja_context["entries"]["types"] = scoped_entry_types

    # Render developer instructions
    rendered_developer_messages = render_developer_instructions(
        templates=developer_instruction_templates,
        jinja_context=jinja_context,
    )

    # Build messages
    messages: list[MessageSpec] = []

    if system_prompt:
        messages.append(
            MessageSpec(
                role="system",
                content=system_prompt,
                raw_text=system_prompt,
                persist=True,
            )
        )

    for m in rendered_developer_messages:
        if has_media_sentinels(m):
            # TODO: resolve agent_input_modalities from agent's model → modalities_resource
            content_blocks = post_process_media_sentinels(
                m, agent_input_modalities=None
            )
            messages.append(
                MessageSpec(
                    role="developer",
                    content=content_blocks,
                    raw_text=m,
                    persist=True,
                )
            )
        else:
            messages.append(
                MessageSpec(
                    role="developer",
                    content=m,
                    raw_text=m,
                    persist=True,
                )
            )

    # extra_messages are NOT persisted (they come pre-persisted, e.g. chat history)
    # TODO: extra_messages should be passed in from payload, not accessed here

    # user_instructions are persisted
    # TODO: user_instructions should be passed in from payload, not accessed here

    # Filter tools to agent's tool_ids
    agent_tool_id_set = (
        {str(tid) for tid in agent.tool_ids}
        if getattr(agent, "tool_ids", None)
        else set()
    )
    scoped_tools = [
        td for td in all_tool_dicts if str(td.get("id", "")) in agent_tool_id_set
    ]

    # Metadata
    metadata: dict[str, Any] = dict(payload_metadata)
    if save is not None:
        metadata["save"] = save

    return AgentDispatch(
        agent_id=agent_id,
        resource_types=scoped_resource_types,
        entry_types=scoped_entry_types,
        messages=messages,
        llm_config=llm_config,
        scoped_tools=scoped_tools,
        metadata=metadata,
        developer_instruction_templates=developer_instruction_templates or None,
    )


# ---------------------------------------------------------------------------
# Tool result aggregation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# WebsocketContext → agent groups (replaces build_agent_groups for ws_ctx path)
# ---------------------------------------------------------------------------


def build_agent_groups_from_scores(
    *,
    resource_types: list[str],
    scores: Any,
) -> dict[UUID, list[str]]:
    """Map resource_types → agent_id groups using ArtifactToolScores.best.

    Each resource_type maps to the best ResolvedTool's agent_id via score_tools.
    Groups by agent_id → [resource_types...].
    """
    agent_groups: dict[UUID, list[str]] = {}

    for rt in resource_types:
        best = scores.best.get(rt)
        if best is not None:
            agent_groups.setdefault(best.agent_id, []).append(rt)

    return agent_groups


def build_jinja_from_ws_ctx(
    ws_ctx: Any,
    entry_results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build namespaced Jinja context from WebsocketContext.artifacts.

    Maps ws_ctx.artifacts (keyed "get.persona" etc) into the shape
    build_namespaced_context produces: {artifacts: {name: {operation: {resources: ..., entries: ...}}}}.
    """
    context: dict[str, Any] = {"artifacts": {}}

    for key, art_ctx in ws_ctx.artifacts.items():
        # key is "get.persona" → split into operation="get", name="persona"
        parts = key.split(".", 1)
        if len(parts) != 2:
            continue
        operation, name = parts

        # Flatten resources: "get.names" → just the list under "names"
        resources_flat: dict[str, Any] = {}
        for rkey, rval in art_ctx.resources.items():
            # rkey is "get.names" or "search.names"
            rparts = rkey.split(".", 1)
            if len(rparts) == 2:
                resources_flat[rkey] = rval

        # Flatten entries similarly
        entries_flat: dict[str, Any] = {}
        for ekey, eval_ in art_ctx.entries.items():
            entries_flat[ekey] = eval_

        artifact_data: dict[str, Any] = {
            "resources": resources_flat,
            "entries": entries_flat,
        }

        context["artifacts"].setdefault(name, {})[operation] = artifact_data

    # Merge entry_results (problems, messages) same as build_namespaced_context
    if entry_results:
        for name, ops in entry_results.items():
            context["artifacts"].setdefault(name, {}).update(ops)

    return context


# Re-export from canonical location
from app.infra.websocket.pipeline_helpers import (
    aggregate_tool_results as aggregate_tool_results,
)  # noqa: F401
