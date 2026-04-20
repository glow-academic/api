"""Canonical persona section assembly.

Pure/shared shaping for persona artifact state. This module is intentionally
transport-agnostic: HTTP, MCP, CLI, and socket callers can all reuse it.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.common_context import CommonContext
from app.infra.helpers import sorted_dedupe_by_id
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
    PersonaDepartmentResource,
    PersonaDescriptionResource,
    PersonaExampleResource,
    PersonaFlagConfig,
    PersonaIconResource,
    PersonaInstructionResource,
    PersonaNameResource,
    PersonaParameterFieldResource,
    PersonaVoiceResource,
)


def build_persona_get_result(
    *,
    common: CommonContext,
    persona: ArtifactContext,
    scores: ArtifactToolScores,
    perms: PersonaPermissionsContext | None,
    group_id: UUID | None,
    include: dict[str, bool] | None = None,
    selected_only: dict[str, bool] | None = None,
    suggested_only: dict[str, bool] | None = None,
) -> GetPersonaApiResponse:
    """Build the canonical persona response bundle from resolved contexts."""
    inc = include or {}
    sel_only = selected_only or {}
    sug_only = suggested_only or {}

    def _filter_section(items: list | None, section: str) -> list | None:
        """Apply selected_only and suggested_only filters to a section's items."""
        if items is None:
            return None
        if sel_only.get(section):
            items = [i for i in items if getattr(i, "selected", False)]
        if sug_only.get(section):
            items = [i for i in items if getattr(i, "suggested", False)]
        return items
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

    # Pending IDs from soft draft connections
    pending_ids: set[UUID] = persona.entries.get("pending_ids", set())

    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in PERSONA_RESOURCES
    }
    # Compose suggestions first so the natural DB order (created_at / search column)
    # is preserved. sorted_dedupe_by_id keeps the first occurrence, so a selected item
    # that also appears in suggestions stays in its suggestion-order slot instead
    # of jumping to the top. Selected items not in suggestions (e.g. filtered out)
    # still surface at the end as a fallback.
    all_names = sorted_dedupe_by_id(
        persona.resources["names"].suggestions + persona.resources["names"].selected
    )
    all_descriptions = sorted_dedupe_by_id(
        persona.resources["descriptions"].suggestions
        + persona.resources["descriptions"].selected
    )
    all_colors = sorted_dedupe_by_id(
        persona.resources["colors"].suggestions + persona.resources["colors"].selected
    )
    all_icons = sorted_dedupe_by_id(
        persona.resources["icons"].suggestions + persona.resources["icons"].selected
    )
    all_instructions = sorted_dedupe_by_id(
        persona.resources["instructions"].suggestions
        + persona.resources["instructions"].selected
    )
    all_departments = sorted_dedupe_by_id(
        persona.resources["departments"].suggestions
        + persona.resources["departments"].selected
    )
    all_examples = sorted_dedupe_by_id(
        persona.resources["examples"].suggestions
        + persona.resources["examples"].selected
    )
    all_parameters = sorted_dedupe_by_id(
        persona.resources["parameters"].suggestions
        + persona.resources["parameters"].selected,
        id_attr="parameter_id",
    )
    # Root parameters (not the target of any field's conditional_parameter_id)
    # come before conditional children. Python sort is stable, so chronological
    # (UUID v7) order is preserved within each tier.
    _conditional_target_ids = {
        cp.parameter_id
        for cp in persona.resources.get(
            "conditional_parameters", ResourcePair([], [])
        ).suggestions
        if getattr(cp, "parameter_id", None)
    }
    all_parameters = sorted(
        all_parameters,
        key=lambda p: getattr(p, "parameter_id", None) in _conditional_target_ids,
    )
    all_voices = sorted_dedupe_by_id(
        persona.resources["voices"].suggestions + persona.resources["voices"].selected
    )

    show_ai_generate = can_ai_generate

    all_flags = sorted_dedupe_by_id(
        persona.resources["flags"].suggestions + persona.resources["flags"].selected
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

    selected_sets = {
        "names": {item.id for item in persona.resources["names"].selected},
        "descriptions": {item.id for item in persona.resources["descriptions"].selected},
        "colors": {item.id for item in persona.resources["colors"].selected},
        "icons": {item.id for item in persona.resources["icons"].selected},
        "instructions": {item.id for item in persona.resources["instructions"].selected},
        "departments": {item.id for item in persona.resources["departments"].selected},
        "parameter_fields": {item.id for item in persona.resources["parameter_fields"].selected},
        "examples": {item.id for item in persona.resources["examples"].selected},
        "voices": {item.id for item in persona.resources["voices"].selected},
    }

    def _model_many_with_flags(items, model_cls, suggested_ids: set, selected_ids: set, id_attr: str = "id"):
        result = []
        for item in items:
            m = model_cls.model_validate(item.model_dump())
            item_id = getattr(item, id_attr, None)
            if item_id and item_id in suggested_ids:
                m.suggested = True
            if item_id and item_id in selected_ids:
                m.selected = True
            if item_id and item_id in pending_ids:
                m.pending = True
            result.append(m)
        return result

    def _department_model(item) -> PersonaDepartmentResource:
        payload = item.model_dump()
        payload["department_id"] = payload.pop("id", None)
        return PersonaDepartmentResource.model_validate(payload)

    def _department_many_with_flags(items, suggested_ids: set, selected_ids: set):
        result = []
        for item in items:
            m = _department_model(item)
            if item.id and item.id in suggested_ids:
                m.suggested = True
            if item.id and item.id in selected_ids:
                m.selected = True
            if item.id and item.id in pending_ids:
                m.pending = True
            result.append(m)
        return result

    # Build field lookup from already-fetched fields catalog to hydrate
    # parameter_field items with name/description from fields_resource.
    field_lookup = {f.id: f for f in persona.resources["fields"].suggestions}

    # Build conditional_parameter_id -> parameter_id mapping for nesting.
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
            # Resolve conditional_parameter_ids -> parameter_id for nesting
            cond_ids = getattr(field, "conditional_parameter_ids", None) or []
            for cid in cond_ids:
                param_id = cond_param_to_param.get(cid)
                if param_id:
                    payload["conditional_parameter_id"] = str(param_id)
                    break
        return PersonaParameterFieldResource.model_validate(payload)

    def _parameter_field_many_with_flags(items, suggested_ids: set, selected_ids: set):
        result = []
        for item in items:
            m = _parameter_field_model(item)
            if item.id and item.id in suggested_ids:
                m.suggested = True
            if item.id and item.id in selected_ids:
                m.selected = True
            if item.id and item.id in pending_ids:
                m.pending = True
            result.append(m)
        return result

    # Build flat flag list with selected marked
    selected_flag_ids = {flag.id for flag in persona.resources["flags"].selected}
    flags_flat = []
    for flag in all_flags:
        if flag.id:
            fc = PersonaFlagConfig(
                key=flag.name,
                label=flag.name,
                description=flag.description,
                icon_id=flag.icon_id,
                flag_option_id=flag.id,
                generated=flag.generated,
                selected=flag.id in selected_flag_ids,
                pending=flag.id in pending_ids,
            )
            flags_flat.append(fc)

    # Dedupe parameter_fields: suggestions first so selected items keep their
    # natural slot (see rationale on the other dedupe calls above).
    all_parameter_fields = sorted_dedupe_by_id(
        persona.resources["parameter_fields"].suggestions
        + persona.resources["parameter_fields"].selected
    )

    return GetPersonaApiResponse(
        actor_name=profile.name,
        persona_exists=persona.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=group_id,
        show_ai_generate=show_ai_generate,
        names=_filter_section(_model_many_with_flags(all_names, PersonaNameResource, suggestions_sets.get("names", set()), selected_sets.get("names", set())), "names") if inc.get("names", True) else None,
        descriptions=_filter_section(_model_many_with_flags(all_descriptions, PersonaDescriptionResource, suggestions_sets.get("descriptions", set()), selected_sets.get("descriptions", set())), "descriptions") if inc.get("descriptions", True) else None,
        colors=_filter_section(_model_many_with_flags(all_colors, PersonaColorResource, suggestions_sets.get("colors", set()), selected_sets.get("colors", set())), "colors") if inc.get("colors", True) else None,
        icons=_filter_section(_model_many_with_flags(all_icons, PersonaIconResource, suggestions_sets.get("icons", set()), selected_sets.get("icons", set())), "icons") if inc.get("icons", True) else None,
        instructions=_filter_section(_model_many_with_flags(all_instructions, PersonaInstructionResource, suggestions_sets.get("instructions", set()), selected_sets.get("instructions", set())), "instructions") if inc.get("instructions", True) else None,
        flags=_filter_section(flags_flat, "flags") if inc.get("flags", True) else None,
        departments=_filter_section(_department_many_with_flags(all_departments, suggestions_sets.get("departments", set()), selected_sets.get("departments", set())), "departments") if inc.get("departments", True) else None,
        parameter_fields=_filter_section(_parameter_field_many_with_flags(all_parameter_fields, suggestions_sets.get("parameter_fields", set()), selected_sets.get("parameter_fields", set())), "parameter_fields") if inc.get("parameter_fields", True) else None,
        examples=_filter_section(_model_many_with_flags(all_examples, PersonaExampleResource, suggestions_sets.get("examples", set()), selected_sets.get("examples", set())), "examples") if inc.get("examples", True) else None,
        parameters=list(all_parameters) if inc.get("parameters", True) else None,
        voices=_filter_section(_model_many_with_flags(all_voices, PersonaVoiceResource, suggestions_sets.get("voices", set()), selected_sets.get("voices", set())), "voices") if inc.get("voices", True) else None,
        fields=persona.resources["fields"].suggestions,
        resolved_parameter_ids=resolved_parameter_ids or None,
    )
