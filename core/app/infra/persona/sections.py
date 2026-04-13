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
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
)
from app.infra.persona.permissions_context import PersonaPermissionsContext
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext, ResourcePair
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
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        persona_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        persona_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )

    # AI generate: simple permission check — can the user draft?
    can_ai_generate = compute_can_draft(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
    )

    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in PERSONA_RESOURCES
    }
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
        + persona.resources["parameters"].suggestions,
        id_attr="parameter_id",
    )
    all_voices = dedupe_by_id(
        persona.resources["voices"].selected + persona.resources["voices"].suggestions
    )

    show_ai_generate = can_ai_generate

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

    suggestions_sets = {
        "names": {item.id for item in persona.resources["names"].suggestions},
        "descriptions": {
            item.id for item in persona.resources["descriptions"].suggestions
        },
        "colors": {item.id for item in persona.resources["colors"].suggestions},
        "icons": {item.id for item in persona.resources["icons"].suggestions},
        "instructions": {
            item.id for item in persona.resources["instructions"].suggestions
        },
        "departments": {
            item.id for item in persona.resources["departments"].suggestions
        },
        "parameter_fields": set(),
        "examples": {item.id for item in persona.resources["examples"].suggestions},
        "parameters": {item.parameter_id for item in persona.resources["parameters"].suggestions},
        "voices": {item.id for item in persona.resources["voices"].suggestions},
    }

    def _model(item, model_cls):
        return model_cls.model_validate(item.model_dump())

    def _model_many(items, model_cls):
        return [_model(item, model_cls) for item in items]

    def _model_many_with_suggested(items, model_cls, suggested_ids: set, id_attr: str = "id"):
        result = []
        for item in items:
            m = model_cls.model_validate(item.model_dump())
            item_id = getattr(item, id_attr, None)
            if item_id and item_id in suggested_ids:
                m.suggested = True
            result.append(m)
        return result

    def _set_suggested(model, item_id, suggested_ids: set):
        if item_id and item_id in suggested_ids:
            model.suggested = True
        return model

    def _department_model(item) -> PersonaDepartmentResource:
        payload = item.model_dump()
        payload["department_id"] = payload.pop("id", None)
        return PersonaDepartmentResource.model_validate(payload)

    # Build field lookup from already-fetched fields catalog to hydrate
    # parameter_field items with name/description from fields_resource.
    field_lookup = {f.id: f for f in persona.resources["fields"].suggestions}

    # Build conditional_parameter_id → parameter_id mapping for nesting.
    cond_param_to_param = {
        cp.id: cp.parameter_id
        for cp in persona.resources.get("conditional_parameters", ResourcePair([], [])).suggestions
    }

    def _parameter_field_model(item) -> PersonaParameterFieldResource:
        payload = item.model_dump()
        field = field_lookup.get(item.field_id)
        if field:
            payload["name"] = field.name
            payload["description"] = field.description
            # Resolve conditional_parameter_ids → parameter_id for nesting
            cond_ids = getattr(field, "conditional_parameter_ids", None) or []
            for cid in cond_ids:
                param_id = cond_param_to_param.get(cid)
                if param_id:
                    payload["conditional_parameter_id"] = str(param_id)
                    break
        return PersonaParameterFieldResource.model_validate(payload)

    return GetPersonaApiResponse(
        actor_name=profile.name,
        persona_exists=persona.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=group_id,
        show_ai_generate=show_ai_generate,
        names=PersonaNameSection(
            resource=_model(persona.resources["names"].selected[0], PersonaNameResource)
            if persona.resources["names"].selected
            else None,
            resources=_model_many_with_suggested(all_names, PersonaNameResource, suggestions_sets.get("names", set())),
        ),
        descriptions=PersonaDescriptionSection(
            resource=_model(
                persona.resources["descriptions"].selected[0],
                PersonaDescriptionResource,
            )
            if persona.resources["descriptions"].selected
            else None,
            resources=_model_many_with_suggested(all_descriptions, PersonaDescriptionResource, suggestions_sets.get("descriptions", set())),
        ),
        colors=PersonaColorSection(
            resource=_model(
                persona.resources["colors"].selected[0], PersonaColorResource
            )
            if persona.resources["colors"].selected
            else None,
            resources=_model_many_with_suggested(all_colors, PersonaColorResource, suggestions_sets.get("colors", set())),
        ),
        icons=PersonaIconSection(
            resource=_model(persona.resources["icons"].selected[0], PersonaIconResource)
            if persona.resources["icons"].selected
            else None,
            resources=_model_many_with_suggested(all_icons, PersonaIconResource, suggestions_sets.get("icons", set())),
        ),
        instructions=PersonaInstructionSection(
            resource=_model(
                persona.resources["instructions"].selected[0],
                PersonaInstructionResource,
            )
            if persona.resources["instructions"].selected
            else None,
            resources=_model_many_with_suggested(all_instructions, PersonaInstructionResource, suggestions_sets.get("instructions", set())),
        ),
        flags=PersonaFlagSection(
            current=current_flag,
            resources=persona_flags,
        ),
        departments=PersonaDepartmentSection(
            current=[
                _department_model(item)
                for item in persona.resources["departments"].selected
            ],
            resources=[
                _set_suggested(_department_model(item), item.id, suggestions_sets.get("departments", set()))
                for item in all_departments
            ],
        ),
        parameter_fields=PersonaParameterFieldSection(
            current=[
                _parameter_field_model(item)
                for item in persona.resources["parameter_fields"].selected
            ],
            resources=[
                _set_suggested(_parameter_field_model(item), item.parameter_id, suggestions_sets.get("parameter_fields", set()))
                for item in persona.resources["parameter_fields"].suggestions
            ],
        ),
        examples=PersonaExampleSection(
            current=_model_many(
                persona.resources["examples"].selected, PersonaExampleResource
            ),
            resources=_model_many_with_suggested(all_examples, PersonaExampleResource, suggestions_sets.get("examples", set())),
        ),
        parameters=PersonaParameterSection(
            current=[item for item in persona.resources["parameters"].selected],
            resources=all_parameters,
        ),
        voices=PersonaVoiceSection(
            current=_model_many(
                persona.resources["voices"].selected, PersonaVoiceResource
            ),
            resources=_model_many_with_suggested(all_voices, PersonaVoiceResource, suggestions_sets.get("voices", set())),
        ),
        fields=persona.resources["fields"].suggestions,
        resolved_parameter_ids=resolved_parameter_ids or None,
    )
