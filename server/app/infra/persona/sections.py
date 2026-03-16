"""Canonical persona section assembly.

Pure/shared shaping for persona artifact state. This module is intentionally
transport-agnostic: HTTP, MCP, CLI, and socket callers can all reuse it.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.common_context import CommonContext
from app.infra.helpers import dedupe_by_id
from app.infra.persona.permissions import (
    PERSONA_RESOURCES,
    compute_can_edit,
    compute_color_required,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_examples_required,
    compute_flag_required,
    compute_icon_required,
    compute_instructions_required,
    compute_name_required,
    compute_parameter_fields_required,
    compute_parameters_required,
    compute_show_ai_generate,
    compute_show_color,
    compute_show_departments,
    compute_show_description,
    compute_show_examples,
    compute_show_flag,
    compute_show_icon,
    compute_show_instructions,
    compute_show_name,
    compute_show_parameter_fields,
    compute_show_parameters,
    compute_show_voices,
    compute_voices_required,
)
from app.infra.persona.permissions_context import PersonaPermissionsContext
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext
from app.infra.persona.types import (
    GetPersonaApiResponse,
    PersonaColorResource,
    PersonaColorSection,
    PersonaDepartmentResource,
    PersonaDepartmentSection,
    PersonaDescriptionResource,
    PersonaDescriptionSection,
    PersonaExampleResource,
    PersonaExampleSection,
    PersonaFlagConfig,
    PersonaFlagSection,
    PersonaIconResource,
    PersonaIconSection,
    PersonaInstructionResource,
    PersonaInstructionSection,
    PersonaNameResource,
    PersonaNameSection,
    PersonaParameterFieldResource,
    PersonaParameterFieldSection,
    PersonaParameterSection,
    PersonaVoiceResource,
    PersonaVoiceSection,
)


def build_persona_get_result(
    *,
    common: CommonContext,
    persona: ArtifactContext,
    scores: ArtifactToolScores,
    perms: PersonaPermissionsContext | None,
    group_id: UUID | None,
) -> GetPersonaApiResponse:
    """Build the canonical persona response bundle from resolved contexts."""
    profile = common.profile

    perms_department_ids = perms.department_ids if perms else []
    perms_scenario_count = perms.active_scenario_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        persona_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        persona_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )

    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in PERSONA_RESOURCES
    }
    tool_ids_map: dict[str, UUID | None] = {
        resource: (scores.best[resource].tool_id if scores.best.get(resource) else None)
        for resource in PERSONA_RESOURCES
    }

    names_has_tools = scores.has_any.get("names", False)
    colors_has_tools = scores.has_any.get("colors", False)
    icons_has_tools = scores.has_any.get("icons", False)
    instructions_has_tools = scores.has_any.get("instructions", False)

    all_names = dedupe_by_id(
        persona.resources["names"].selected + persona.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        persona.resources["descriptions"].selected
        + persona.resources["descriptions"].suggestions
    )
    all_colors = dedupe_by_id(
        persona.resources["colors"].selected + persona.resources["colors"].suggestions
    )
    all_icons = dedupe_by_id(
        persona.resources["icons"].selected + persona.resources["icons"].suggestions
    )
    all_instructions = dedupe_by_id(
        persona.resources["instructions"].selected
        + persona.resources["instructions"].suggestions
    )
    all_departments = dedupe_by_id(
        persona.resources["departments"].selected
        + persona.resources["departments"].suggestions
    )
    all_examples = dedupe_by_id(
        persona.resources["examples"].selected
        + persona.resources["examples"].suggestions
    )
    all_parameters = dedupe_by_id(
        persona.resources["parameters"].selected
        + persona.resources["parameters"].suggestions
    )
    all_voices = dedupe_by_id(
        persona.resources["voices"].selected + persona.resources["voices"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "colors": compute_show_color(colors_has_tools, len(all_colors)),
        "icons": compute_show_icon(icons_has_tools, len(all_icons)),
        "instructions": compute_show_instructions(instructions_has_tools),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "parameter_fields": compute_show_parameter_fields(
            len(persona.resources["fields"].suggestions)
        ),
        "examples": compute_show_examples(len(all_examples)),
        "parameters": compute_show_parameters(len(all_parameters)),
        "voices": compute_show_voices(len(all_voices)),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "colors": compute_color_required(),
        "icons": compute_icon_required(),
        "instructions": compute_instructions_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "parameter_fields": compute_parameter_fields_required(),
        "examples": compute_examples_required(),
        "parameters": compute_parameters_required(),
        "voices": compute_voices_required(),
    }

    show_ai_generate_map = {
        resource: compute_show_ai_generate(agent_ids, resource)
        for resource in PERSONA_RESOURCES
    }

    basic_show_ai_generate = any(
        [
            show_ai_generate_map.get("names", False),
            show_ai_generate_map.get("descriptions", False),
            show_ai_generate_map.get("flags", False),
            show_ai_generate_map.get("departments", False),
        ]
    )
    content_show_ai_generate = any(
        [
            show_ai_generate_map.get("instructions", False),
            show_ai_generate_map.get("examples", False),
            show_ai_generate_map.get("voices", False),
        ]
    )
    parameters_step_show_ai_generate = any(
        [
            show_ai_generate_map.get("parameters", False),
            show_ai_generate_map.get("parameter_fields", False),
        ]
    )

    all_flags = dedupe_by_id(
        persona.resources["flags"].selected + persona.resources["flags"].suggestions
    )
    persona_flags = [
        PersonaFlagConfig(
            key=flag.name,
            label=flag.name,
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]

    current_flag = None
    if persona.resources["flags"].selected:
        flag = persona.resources["flags"].selected[0]
        current_flag = PersonaFlagConfig(
            key=flag.name,
            label=flag.name,
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            generated=flag.generated,
        )

    resolved_parameter_ids = list(
        {
            str(parameter_field.parameter_id)
            for parameter_field in persona.resources["parameter_fields"].selected
            if parameter_field.parameter_id
        }
    )

    suggestions_map = {
        "names": [item.id for item in persona.resources["names"].suggestions],
        "descriptions": [
            item.id for item in persona.resources["descriptions"].suggestions
        ],
        "colors": [item.id for item in persona.resources["colors"].suggestions],
        "icons": [item.id for item in persona.resources["icons"].suggestions],
        "instructions": [
            item.id for item in persona.resources["instructions"].suggestions
        ],
        "departments": [
            item.id for item in persona.resources["departments"].suggestions
        ],
        "parameter_fields": [],
        "examples": [item.id for item in persona.resources["examples"].suggestions],
        "parameters": [item.id for item in persona.resources["parameters"].suggestions],
        "voices": [item.id for item in persona.resources["voices"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    def _model(item, model_cls):
        return model_cls.model_validate(item.model_dump())

    def _model_many(items, model_cls):
        return [_model(item, model_cls) for item in items]

    def _department_model(item) -> PersonaDepartmentResource:
        payload = item.model_dump()
        payload["department_id"] = payload.pop("id", None)
        return PersonaDepartmentResource.model_validate(payload)

    return GetPersonaApiResponse(
        actor_name=profile.name,
        persona_exists=persona.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=persona.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        content_show_ai_generate=content_show_ai_generate,
        parameters_step_show_ai_generate=parameters_step_show_ai_generate,
        names=PersonaNameSection(
            **_section("names"),
            resource=_model(persona.resources["names"].selected[0], PersonaNameResource)
            if persona.resources["names"].selected
            else None,
            resources=_model_many(all_names, PersonaNameResource),
        ),
        descriptions=PersonaDescriptionSection(
            **_section("descriptions"),
            resource=_model(
                persona.resources["descriptions"].selected[0],
                PersonaDescriptionResource,
            )
            if persona.resources["descriptions"].selected
            else None,
            resources=_model_many(all_descriptions, PersonaDescriptionResource),
        ),
        colors=PersonaColorSection(
            **_section("colors"),
            resource=_model(
                persona.resources["colors"].selected[0], PersonaColorResource
            )
            if persona.resources["colors"].selected
            else None,
            resources=_model_many(all_colors, PersonaColorResource),
        ),
        icons=PersonaIconSection(
            **_section("icons"),
            resource=_model(persona.resources["icons"].selected[0], PersonaIconResource)
            if persona.resources["icons"].selected
            else None,
            resources=_model_many(all_icons, PersonaIconResource),
        ),
        instructions=PersonaInstructionSection(
            **_section("instructions"),
            resource=_model(
                persona.resources["instructions"].selected[0],
                PersonaInstructionResource,
            )
            if persona.resources["instructions"].selected
            else None,
            resources=_model_many(all_instructions, PersonaInstructionResource),
        ),
        flags=PersonaFlagSection(
            **_section("flags"),
            current=current_flag,
            resources=persona_flags,
        ),
        departments=PersonaDepartmentSection(
            **_section("departments"),
            current=[
                _department_model(item)
                for item in persona.resources["departments"].selected
            ],
            resources=[_department_model(item) for item in all_departments],
        ),
        parameter_fields=PersonaParameterFieldSection(
            **_section("parameter_fields"),
            current=_model_many(
                persona.resources["parameter_fields"].selected,
                PersonaParameterFieldResource,
            ),
            resources=_model_many(
                persona.resources["parameter_fields"].suggestions,
                PersonaParameterFieldResource,
            ),
        ),
        examples=PersonaExampleSection(
            **_section("examples"),
            current=_model_many(
                persona.resources["examples"].selected, PersonaExampleResource
            ),
            resources=_model_many(all_examples, PersonaExampleResource),
        ),
        parameters=PersonaParameterSection(
            **_section("parameters"),
            current=[item for item in persona.resources["parameters"].selected],
            resources=all_parameters,
        ),
        voices=PersonaVoiceSection(
            **_section("voices"),
            current=_model_many(
                persona.resources["voices"].selected, PersonaVoiceResource
            ),
            resources=_model_many(all_voices, PersonaVoiceResource),
        ),
        fields=persona.resources["fields"].suggestions,
        resolved_parameter_ids=resolved_parameter_ids or None,
    )
