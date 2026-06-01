"""Canonical agent section assembly."""

from __future__ import annotations

from uuid import UUID

from app.infra.agent.permissions import (
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_instructions_required,
    compute_models_required,
    compute_name_required,
    compute_prompts_required,
    compute_qualities_required,
    compute_reasoning_levels_required,
    compute_rubrics_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_instructions,
    compute_show_models,
    compute_show_name,
    compute_show_prompts,
    compute_show_qualities,
    compute_show_reasoning_levels,
    compute_show_rubrics,
    compute_show_temperature_levels,
    compute_show_tools,
    compute_show_voices,
    compute_temperature_levels_required,
    compute_tools_required,
    compute_voices_required,
    get_missing_tools,
    has_access,
)
from app.infra.agent.permissions_context import AgentPermissionsContext
from app.infra.agent.types import (
    AgentDepartmentSection,
    AgentDescriptionSection,
    AgentFlagResource,
    AgentFlagSection,
    AgentInstructionSection,
    AgentModelSection,
    AgentNameSection,
    AgentPromptSection,
    AgentQualitySection,
    AgentReasoningLevelSection,
    AgentRubricSection,
    AgentTemperatureLevelSection,
    AgentToolSection,
    AgentVoiceSection,
    GetAgentApiResponse,
)
from app.infra.common_context import CommonContext
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.types import ArtifactContext


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive a flag key/label from names like 'agent_active'."""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("agent_", "")
    label = key.replace("_", " ").title()
    return (key, label)


def build_agent_get_result(
    *,
    common: CommonContext,
    agent_ctx: ArtifactContext,
    perms: AgentPermissionsContext | None,
    agent_id: UUID | None,
    group_id: UUID | None,
) -> GetAgentApiResponse:
    """Build the canonical agent response bundle from resolved contexts."""
    profile = common.profile

    # ``agent_ids`` decoration is dead weight — the client always shows
    # the "AI generate" button regardless, and the actual agent dispatch
    # happens server-side in ``prepare_generation``. Empty dict keeps the
    # response shape stable for any FE still reading it.
    agent_ids: dict[str, UUID | None] = {}

    # Tool-graph scoring decoration is dead weight — pass ``True`` so
    # every ``compute_show_*`` helper renders the section.
    names_has_tools = True
    descriptions_has_tools = True
    models_has_tools = True
    prompts_has_tools = True
    instructions_has_tools = True
    departments_has_tools = True
    tools_has_tools = True
    temperature_levels_has_tools = True
    reasoning_levels_has_tools = True
    voices_has_tools = True
    qualities_has_tools = True
    rubrics_has_tools = True

    missing_tools = get_missing_tools(
        names_has_tools=names_has_tools,
        models_has_tools=models_has_tools,
        prompts_has_tools=prompts_has_tools,
        instructions_has_tools=instructions_has_tools,
    )
    has_agent_access = has_access(
        profile.role_level,
        profile.department_ids,
        perms.department_ids if perms else [],
    )
    can_edit = compute_can_edit(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        has_agent_access=has_agent_access,
        missing_tools=missing_tools,
        agent_id=agent_id,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        has_agent_access=has_agent_access,
        missing_tools=missing_tools,
        agent_id=agent_id,
    )

    # Compose suggestions first so selected items keep their natural DB-ordered
    # slot instead of jumping to the top on selection toggle. sorted_dedupe_by_id keeps
    # the first occurrence.
    all_departments = sorted_dedupe_by_id(
        agent_ctx.resources["departments"].suggestions
        + agent_ctx.resources["departments"].selected
    )
    all_tools = sorted_dedupe_by_id(
        agent_ctx.resources["tools"].suggestions + agent_ctx.resources["tools"].selected
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(descriptions_has_tools),
        "models": compute_show_models(models_has_tools),
        "prompts": compute_show_prompts(prompts_has_tools),
        "instructions": compute_show_instructions(instructions_has_tools),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(
            departments_has_tools, len(all_departments) > 0
        ),
        "tools": compute_show_tools(tools_has_tools, len(all_tools) > 0),
        "temperature_levels": compute_show_temperature_levels(
            temperature_levels_has_tools
        ),
        "reasoning_levels": compute_show_reasoning_levels(reasoning_levels_has_tools),
        "voices": compute_show_voices(voices_has_tools),
        "qualities": compute_show_qualities(qualities_has_tools),
        "rubrics": compute_show_rubrics(rubrics_has_tools),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "models": compute_models_required(),
        "prompts": compute_prompts_required(),
        "instructions": compute_instructions_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(show_flags_map["departments"]),
        "tools": compute_tools_required(),
        "temperature_levels": compute_temperature_levels_required(),
        "reasoning_levels": compute_reasoning_levels_required(),
        "voices": compute_voices_required(),
        "qualities": compute_qualities_required(),
        "rubrics": compute_rubrics_required(),
    }
    # Always-show semantics: dispatch happens server-side in
    # ``prepare_generation``.
    show_ai_generate_map: dict[str, bool] = {}
    basic_show_ai_generate = True
    general_show_ai_generate = True

    all_flags = sorted_dedupe_by_id(
        agent_ctx.resources["flags"].suggestions + agent_ctx.resources["flags"].selected
    )
    agent_flags = [
        AgentFlagResource(
            id=flag.id,
            name=getattr(flag, "name", None),
            type=getattr(flag, "type", None),
            value=getattr(flag, "value", None),
            description=flag.description,
            icon_id=flag.icon_id,
            icon=flag.icon,
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]
    current_flags = [
        AgentFlagResource(
            id=flag.id,
            name=getattr(flag, "name", None),
            type=getattr(flag, "type", None),
            value=getattr(flag, "value", None),
            description=flag.description,
            icon_id=flag.icon_id,
            icon=flag.icon,
            generated=flag.generated,
        )
        for flag in agent_ctx.resources["flags"].selected
        if flag.id
    ]

    all_names = sorted_dedupe_by_id(
        agent_ctx.resources["names"].suggestions + agent_ctx.resources["names"].selected
    )
    all_descriptions = sorted_dedupe_by_id(
        agent_ctx.resources["descriptions"].suggestions
        + agent_ctx.resources["descriptions"].selected
    )
    all_models = sorted_dedupe_by_id(
        agent_ctx.resources["models"].suggestions
        + agent_ctx.resources["models"].selected
    )
    all_prompts = sorted_dedupe_by_id(
        agent_ctx.resources["prompts"].suggestions
        + agent_ctx.resources["prompts"].selected
    )
    all_instructions = sorted_dedupe_by_id(
        agent_ctx.resources["instructions"].suggestions
        + agent_ctx.resources["instructions"].selected
    )
    all_temperature_levels = sorted_dedupe_by_id(
        agent_ctx.resources["temperature_levels"].suggestions
        + agent_ctx.resources["temperature_levels"].selected
    )
    all_reasoning_levels = sorted_dedupe_by_id(
        agent_ctx.resources["reasoning_levels"].suggestions
        + agent_ctx.resources["reasoning_levels"].selected
    )
    all_voices = sorted_dedupe_by_id(
        agent_ctx.resources["voices"].suggestions
        + agent_ctx.resources["voices"].selected
    )
    all_qualities = sorted_dedupe_by_id(
        agent_ctx.resources["qualities"].suggestions
        + agent_ctx.resources["qualities"].selected
    )
    all_rubrics = sorted_dedupe_by_id(
        agent_ctx.resources["rubrics"].suggestions
        + agent_ctx.resources["rubrics"].selected
    )

    suggestions_map = {
        "names": [item.id for item in agent_ctx.resources["names"].suggestions],
        "descriptions": [
            item.id for item in agent_ctx.resources["descriptions"].suggestions
        ],
        "models": [item.id for item in agent_ctx.resources["models"].suggestions],
        "prompts": [item.id for item in agent_ctx.resources["prompts"].suggestions],
        "instructions": [
            item.id for item in agent_ctx.resources["instructions"].suggestions
        ],
        "departments": [
            item.id for item in agent_ctx.resources["departments"].suggestions
        ],
        "tools": [item.id for item in agent_ctx.resources["tools"].suggestions],
        "temperature_levels": [
            item.id for item in agent_ctx.resources["temperature_levels"].suggestions
        ],
        "reasoning_levels": [
            item.id for item in agent_ctx.resources["reasoning_levels"].suggestions
        ],
        "voices": [item.id for item in agent_ctx.resources["voices"].suggestions],
        "qualities": [item.id for item in agent_ctx.resources["qualities"].suggestions],
        "rubrics": [item.id for item in agent_ctx.resources["rubrics"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
        }

    return GetAgentApiResponse(
        actor_name=profile.name,
        agent_exists=agent_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_agent_context``). ``None`` when no draft was active.
        draft_name=agent_ctx.entries.get("draft_name") if agent_ctx.entries else None,
        basic_show_ai_generate=basic_show_ai_generate,
        general_show_ai_generate=general_show_ai_generate,
        names=AgentNameSection(
            **_section("names"),
            resource=agent_ctx.resources["names"].selected[0]
            if agent_ctx.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=AgentDescriptionSection(
            **_section("descriptions"),
            resource=agent_ctx.resources["descriptions"].selected[0]
            if agent_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
        ),
        models=AgentModelSection(
            **_section("models"),
            resource=agent_ctx.resources["models"].selected[0]
            if agent_ctx.resources["models"].selected
            else None,
            resources=all_models,
        ),
        prompts=AgentPromptSection(
            **_section("prompts"),
            resource=agent_ctx.resources["prompts"].selected[0]
            if agent_ctx.resources["prompts"].selected
            else None,
            resources=all_prompts,
        ),
        instructions=AgentInstructionSection(
            **_section("instructions"),
            resource=agent_ctx.resources["instructions"].selected[0]
            if agent_ctx.resources["instructions"].selected
            else None,
            resources=all_instructions,
        ),
        flags=AgentFlagSection(
            **_section("flags"),
            current=current_flags or None,
            resources=agent_flags,
        ),
        departments=AgentDepartmentSection(
            **_section("departments"),
            current=agent_ctx.resources["departments"].selected or None,
            resources=all_departments,
        ),
        tools=AgentToolSection(
            **_section("tools"),
            current=agent_ctx.resources["tools"].selected or None,
            resources=all_tools,
        ),
        temperature_levels=AgentTemperatureLevelSection(
            **_section("temperature_levels"),
            resource=agent_ctx.resources["temperature_levels"].selected[0]
            if agent_ctx.resources["temperature_levels"].selected
            else None,
            resources=all_temperature_levels,
        ),
        reasoning_levels=AgentReasoningLevelSection(
            **_section("reasoning_levels"),
            resource=agent_ctx.resources["reasoning_levels"].selected[0]
            if agent_ctx.resources["reasoning_levels"].selected
            else None,
            resources=all_reasoning_levels,
        ),
        voices=AgentVoiceSection(
            **_section("voices"),
            current=agent_ctx.resources["voices"].selected or None,
            resources=all_voices,
        ),
        qualities=AgentQualitySection(
            **_section("qualities"),
            current=agent_ctx.resources["qualities"].selected or None,
            resources=all_qualities,
        ),
        rubrics=AgentRubricSection(
            **_section("rubrics"),
            current=agent_ctx.resources["rubrics"].selected or None,
            resources=all_rubrics,
        ),
    )
