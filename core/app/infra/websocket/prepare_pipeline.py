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
    artifact_type: str,
    requires_draft: bool,
    draft_id: UUID | None,
    # Deprecated params kept for call-site compat — ignored
    resource_types_raw: list[str] | None = None,
    valid_resource_types: list[str] | None = None,
    entry_types: list[str] | None = None,
) -> str | None:
    """Validate generation payload. Returns error string or None if valid."""
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


def enrich_tools_with_permissions(
    tool_dicts: list[dict[str, Any]],
    resource_tools: list[Any],
    config_permissions: list[Any],
) -> list[dict[str, Any]]:
    """Attach _permissions to tools for (artifact, operation) resolution."""
    if not tool_dicts or not resource_tools or not config_permissions:
        return tool_dicts

    tool_perm_ids_by_name: dict[str, list[Any]] = {}
    for rt in resource_tools:
        name = getattr(rt, "name", None)
        perm_ids = getattr(rt, "permission_ids", None)
        if name and perm_ids:
            tool_perm_ids_by_name[name] = perm_ids

    if not tool_perm_ids_by_name:
        return tool_dicts

    perm_by_id = {}
    for p in config_permissions:
        p_id = getattr(p, "id", None)
        if p_id:
            perm_by_id[p_id] = p

    for td in tool_dicts:
        t_name = td.get("name")
        if t_name and t_name in tool_perm_ids_by_name:
            perm_list = []
            for perm_id in tool_perm_ids_by_name[t_name]:
                perm = perm_by_id.get(perm_id)
                if perm and getattr(perm, "active", True):
                    perm_list.append(
                        {
                            "artifact": getattr(perm, "artifact", ""),
                            "operation": getattr(perm, "operation", ""),
                        }
                    )
            if perm_list:
                td["_permissions"] = perm_list

    return tool_dicts


def enrich_tools_with_instruction_templates(
    tool_dicts: list[dict[str, Any]],
    resource_tools: list[Any],
    instructions_by_id: dict[Any, Any],
) -> list[dict[str, Any]]:
    """Attach _instruction_template to tools that have an instruction_id.

    Same pattern as enrich_tools_with_args/args_outputs/permissions.
    The template is a Jinja string rendered with tool execution results.
    """
    if not tool_dicts or not resource_tools or not instructions_by_id:
        return tool_dicts

    tool_instruction_id_by_name: dict[str, Any] = {}
    for rt in resource_tools:
        name = getattr(rt, "name", None)
        iid = getattr(rt, "instruction_id", None)
        if name and iid:
            tool_instruction_id_by_name[name] = iid

    if not tool_instruction_id_by_name:
        return tool_dicts

    for td in tool_dicts:
        t_name = td.get("name")
        if t_name and t_name in tool_instruction_id_by_name:
            iid = tool_instruction_id_by_name[t_name]
            instruction = instructions_by_id.get(iid)
            if instruction:
                template = getattr(instruction, "template", None)
                if template:
                    td["_instruction_template"] = template
                    td["instruction_id"] = str(iid)

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

    encrypted_key = getattr(provider, "key", "") or ""
    if not encrypted_key:
        logger.warning(
            f"No API key for provider '{getattr(provider, 'name', '')}' — skipping"
        )
        return None

    # Decrypt the stored key — providers_resource.key is always encrypted
    try:
        from app.utils.auth.decrypt_api_key import decrypt_api_key
        api_key = decrypt_api_key(encrypted_key)
    except Exception:
        # Fallback: treat as plaintext if decryption fails (e.g. legacy data)
        api_key = encrypted_key

    # Model name: user-facing alias (e.g. "glow-text").
    # The openai/ prefix is added at the litellm SDK call site, not here.
    model_name = getattr(model, "value", None) or model.name

    return LLMConfig(
        model=model_name,
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


def build_canonical_context(
    *,
    operations: list[str] | None = None,
    dangerous: bool = False,
    params: dict[str, Any] | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    """Flat config context for developer instruction templates."""
    return {
        "operations": operations or [],
        "dangerous": dangerous,
        "params": params or {},
        "group_id": group_id,
    }


def build_agent_dispatch(
    *,
    agent_id: UUID,
    agent_resource_types: list[str],
    agent: Any,
    llm_config: LLMConfig,
    all_tool_dicts: list[dict[str, Any]],
    system_prompt: str,
    developer_instruction_templates: list[str],
    payload_metadata: dict[str, Any],
    save: bool | None,
    operations: list[str] | None = None,
    artifact_type: str = "",
    dangerous: bool = False,
    group_id: str | None = None,
    params: dict[str, Any] | None = None,
) -> AgentDispatch:
    """Build a complete AgentDispatch for one agent (pure).

    Scopes tools by operations (mapped to (artifact_type, operation) pairs),
    builds canonical context, renders instructions, builds message list.
    """
    # Filter tools to agent's tool_ids
    agent_tool_id_set = (
        {str(tid) for tid in agent.tool_ids}
        if getattr(agent, "tool_ids", None)
        else set()
    )
    scoped_tools = [
        td for td in all_tool_dicts if str(td.get("id", "")) in agent_tool_id_set
    ]

    # Least privilege: further filter tools to only those whose permissions
    # intersect with the requested operations for this artifact_type.
    if operations:
        perm_set = {(artifact_type, op) for op in operations}
        scoped_tools = [
            td for td in scoped_tools
            if any(
                (tp.get("artifact"), tp.get("operation")) in perm_set
                for tp in (td.get("_permissions") or [])
            )
        ]

    # Exclude tools with no output mappings (can't be executed)
    scoped_tools = [
        td for td in scoped_tools
        if td.get("_args_outputs")
    ]

    # Build flat config context for developer instruction rendering
    jinja_context = build_canonical_context(
        operations=operations,
        dangerous=dangerous,
        params=params,
        group_id=group_id,
    )

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

    # Metadata
    metadata: dict[str, Any] = dict(payload_metadata)
    if save is not None:
        metadata["save"] = save

    return AgentDispatch(
        agent_id=agent_id,
        resource_types=agent_resource_types,
        entry_types=[],
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
    operations: list[str] | None = None,
    artifact_type: str = "",
    tool_graph: Any | None = None,
) -> dict[UUID, list[str]]:
    """Map to agent_id groups using operations or resource_types.

    New path (operations): convert to (artifact_type, operation) pairs and match
    against the tool graph's ResolvedTools. Groups by agent_id → [targets...].

    Fallback path (resource_types): match resource_types against
    ArtifactToolScores.best. Groups by agent_id → [resource_types...].
    """
    agent_groups: dict[UUID, list[str]] = {}

    # Operations-based matching via tool graph
    if operations and tool_graph and hasattr(tool_graph, "tools"):
        perm_set = {(artifact_type, op) for op in operations}
        for resolved_tool in tool_graph.tools:
            if (resolved_tool.target, resolved_tool.operation) in perm_set:
                agent_groups.setdefault(resolved_tool.agent_id, []).append(
                    resolved_tool.target
                )
        # Dedupe resource lists per agent
        agent_groups = {
            aid: list(dict.fromkeys(rts))
            for aid, rts in agent_groups.items()
        }
        return agent_groups

    # Fallback: resource_type scoring
    for rt in resource_types:
        best = scores.best.get(rt)
        if best is not None:
            agent_groups.setdefault(best.agent_id, []).append(rt)

    return agent_groups


# Re-export from canonical location
from app.infra.websocket.pipeline_helpers import (
    aggregate_tool_results as aggregate_tool_results,
)  # noqa: F401
