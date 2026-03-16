"""Canonical agent section assembly."""

from __future__ import annotations

from uuid import UUID

from app.infra.agent.permissions import (
    AGENT_BASIC_RESOURCES,
    AGENT_RESOURCES,
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
from app.infra.common_context import CommonContext
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext
from app.infra.agent.types import (
    AgentDepartmentSection,
    AgentDescriptionSection,
    AgentFlagConfig,
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
    scores: ArtifactToolScores,
    perms: AgentPermissionsContext | None,
    agent_id: UUID | None,
    group_id: UUID | None,
) -> GetAgentApiResponse:
    """Build the canonical agent response bundle from resolved contexts."""
    profile = common.profile

    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in AGENT_RESOURCES
    }
    tool_ids_map: dict[str, UUID | None] = {
        resource: (scores.best[resource].tool_id if scores.best.get(resource) else None)
        for resource in AGENT_RESOURCES
    }

    names_has_tools = scores.has_any.get("names", False)
    descriptions_has_tools = scores.has_any.get("descriptions", False)
    models_has_tools = scores.has_any.get("models", False)
    prompts_has_tools = scores.has_any.get("prompts", False)
    instructions_has_tools = scores.has_any.get("instructions", False)
    departments_has_tools = scores.has_any.get("departments", False)
    tools_has_tools = scores.has_any.get("tools", False)
    temperature_levels_has_tools = scores.has_any.get("temperature_levels", False)
    reasoning_levels_has_tools = scores.has_any.get("reasoning_levels", False)
    voices_has_tools = scores.has_any.get("voices", False)
    qualities_has_tools = scores.has_any.get("qualities", False)
    rubrics_has_tools = scores.has_any.get("rubrics", False)

    missing_tools = get_missing_tools(
        names_has_tools=names_has_tools,
        models_has_tools=models_has_tools,
        prompts_has_tools=prompts_has_tools,
        instructions_has_tools=instructions_has_tools,
    )
    has_agent_access = has_access(
        profile.role,
        profile.department_ids,
        perms.department_ids if perms else [],
    )
    can_edit = compute_can_edit(
        user_role=profile.role,
        has_agent_access=has_agent_access,
        missing_tools=missing_tools,
        agent_id=agent_id,
    )
    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        has_agent_access=has_agent_access,
        missing_tools=missing_tools,
        agent_id=agent_id,
    )

    all_departments = dedupe_by_id(
        agent_ctx.resources["departments"].selected
        + agent_ctx.resources["departments"].suggestions
    )
    all_tools = dedupe_by_id(
        agent_ctx.resources["tools"].selected + agent_ctx.resources["tools"].suggestions
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
    show_ai_generate_map = {
        resource: agent_ids.get(resource) is not None for resource in AGENT_RESOURCES
    }
    basic_show_ai_generate = any(
        show_ai_generate_map.get(resource, False) for resource in AGENT_BASIC_RESOURCES
    )
    general_show_ai_generate = any(show_ai_generate_map.values())

    all_flags = dedupe_by_id(
        agent_ctx.resources["flags"].selected + agent_ctx.resources["flags"].suggestions
    )
    agent_flags = [
        AgentFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]
    current_flags = [
        AgentFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in agent_ctx.resources["flags"].selected
        if flag.id
    ]

    all_names = dedupe_by_id(
        agent_ctx.resources["names"].selected + agent_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        agent_ctx.resources["descriptions"].selected
        + agent_ctx.resources["descriptions"].suggestions
    )
    all_models = dedupe_by_id(
        agent_ctx.resources["models"].selected
        + agent_ctx.resources["models"].suggestions
    )
    all_prompts = dedupe_by_id(
        agent_ctx.resources["prompts"].selected
        + agent_ctx.resources["prompts"].suggestions
    )
    all_instructions = dedupe_by_id(
        agent_ctx.resources["instructions"].selected
        + agent_ctx.resources["instructions"].suggestions
    )
    all_temperature_levels = dedupe_by_id(
        agent_ctx.resources["temperature_levels"].selected
        + agent_ctx.resources["temperature_levels"].suggestions
    )
    all_reasoning_levels = dedupe_by_id(
        agent_ctx.resources["reasoning_levels"].selected
        + agent_ctx.resources["reasoning_levels"].suggestions
    )
    all_voices = dedupe_by_id(
        agent_ctx.resources["voices"].selected
        + agent_ctx.resources["voices"].suggestions
    )
    all_qualities = dedupe_by_id(
        agent_ctx.resources["qualities"].selected
        + agent_ctx.resources["qualities"].suggestions
    )
    all_rubrics = dedupe_by_id(
        agent_ctx.resources["rubrics"].selected
        + agent_ctx.resources["rubrics"].suggestions
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
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetAgentApiResponse(
        actor_name=profile.name,
        agent_exists=agent_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=agent_ctx.draft_version,
        group_id=group_id,
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
