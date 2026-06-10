"""Canonical scenario section assembly."""

from __future__ import annotations

from uuid import UUID

from app.infra.common_context import CommonContext
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.scenario.permissions import (
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
)
from app.infra.scenario.permissions_context import ScenarioPermissionsContext
from app.infra.scenario.types import (
    GetScenarioApiResponse,
    ScenarioDepartment,
    ScenarioDescriptionResource,
    ScenarioDocument,
    ScenarioField,
    ScenarioFlagResource,
    ScenarioImage,
    ScenarioNameResource,
    ScenarioObjective,
    ScenarioOption,
    ScenarioParameter,
    ScenarioPersona,
    ScenarioProblemStatement,
    ScenarioQuestion,
    ScenarioVideo,
)
from app.infra.types import ArtifactContext, ResourcePair


def build_scenario_get_result(
    *,
    common: CommonContext,
    scenario: ArtifactContext,
    perms: ScenarioPermissionsContext | None,
    group_id: UUID | None,
    video_enabled: bool | None = None,
    images_enabled: bool | None = None,
    objectives_enabled: bool | None = None,
    questions_enabled: bool | None = None,
    problem_statement_enabled: bool | None = None,
    include: dict[str, bool] | None = None,
    selected_only: dict[str, bool] | None = None,
    suggested_only: dict[str, bool] | None = None,
) -> GetScenarioApiResponse:
    """Build the canonical scenario response bundle from resolved contexts."""
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

    # AI generate: simple permission check — can the user draft?
    can_ai_generate = compute_can_draft(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
    )

    # Pending IDs from soft draft connections
    pending_ids: set[UUID] = scenario.entries.get("pending_ids", set())

    # ``agent_ids`` decoration is dead weight — the client always shows
    # the "AI generate" button regardless, and the actual agent dispatch
    # happens server-side in ``prepare_generation``. Empty dict keeps the
    # response shape stable for any FE still reading it.
    agent_ids: dict[str, UUID | None] = {}


    scenario_department_ids = [d.id for d in scenario.resources["departments"].selected]
    active_simulation_count = perms.active_simulation_count if perms else 0

    can_edit = compute_can_edit(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        scenario_department_ids=scenario_department_ids,
        active_simulation_count=active_simulation_count,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        scenario_department_ids=scenario_department_ids,
        active_simulation_count=active_simulation_count,
        user_department_ids=profile.department_ids,
    )

    # suggestions first so selected items keep their DB-ordered slot instead
    # of jumping to the top on selection toggle. sorted_dedupe_by_id keeps first.
    all_departments = sorted_dedupe_by_id(
        scenario.resources["departments"].suggestions
        + scenario.resources["departments"].selected
    )
    all_personas = sorted_dedupe_by_id(
        scenario.resources["personas"].suggestions
        + scenario.resources["personas"].selected
    )
    all_documents = sorted_dedupe_by_id(
        scenario.resources["documents"].suggestions
        + scenario.resources["documents"].selected
    )
    all_parameters = sorted_dedupe_by_id(
        scenario.resources["parameters"].suggestions
        + scenario.resources["parameters"].selected,
        id_attr="parameter_id",
    )
    all_parameter_fields = sorted_dedupe_by_id(
        scenario.resources["parameter_fields"].suggestions
        + scenario.resources["parameter_fields"].selected
    )
    all_objectives = scenario.resources["objectives"].selected
    all_images = sorted_dedupe_by_id(
        scenario.resources["images"].suggestions + scenario.resources["images"].selected
    )
    all_videos = sorted_dedupe_by_id(
        scenario.resources["videos"].suggestions + scenario.resources["videos"].selected
    )
    all_questions = sorted_dedupe_by_id(
        scenario.resources["questions"].suggestions
        + scenario.resources["questions"].selected
    )
    all_options = sorted_dedupe_by_id(
        scenario.resources["options"].suggestions
        + scenario.resources["options"].selected
    )

    # Compute video_param_ids BEFORE filtering (needed for persona/document tagging)
    video_param_ids = {
        parameter.parameter_id for parameter in all_parameters if parameter.video_parameter
    }

    # Filter parameters by video_enabled toggle
    # Only exclude video-ONLY parameters (video=true, scenario=false)
    # Keep dual-flagged params like Location/Time that are both scenario + video
    if video_enabled is False:
        all_parameters = [
            p for p in all_parameters
            if not p.video_parameter or p.scenario_parameter
        ]

    show_ai_generate = can_ai_generate

    # Build selected/suggested sets for marking
    suggestions_sets: dict[str, set] = {
        "names": {n.id for n in scenario.resources["names"].suggestions},
        "descriptions": {d.id for d in scenario.resources["descriptions"].suggestions},
        "problem_statements": {
            ps.id for ps in scenario.resources["problem_statements"].suggestions
        },
        "departments": {d.id for d in scenario.resources["departments"].suggestions},
        "personas": {p.id for p in scenario.resources["personas"].suggestions},
        "documents": {d.id for d in scenario.resources["documents"].suggestions},
        "parameters": {p.parameter_id for p in scenario.resources["parameters"].suggestions},
        "objectives": set(),
        "parameter_fields": set(),
        "images": {i.id for i in scenario.resources["images"].suggestions},
        "videos": {v.id for v in scenario.resources["videos"].suggestions},
        "questions": {q.id for q in scenario.resources["questions"].suggestions},
        "options": {o.id for o in scenario.resources["options"].suggestions},
    }

    selected_sets: dict[str, set] = {
        "names": {n.id for n in scenario.resources["names"].selected},
        "descriptions": {d.id for d in scenario.resources["descriptions"].selected},
        "problem_statements": {
            ps.id for ps in scenario.resources["problem_statements"].selected
        },
        "departments": {d.id for d in scenario.resources["departments"].selected},
        "personas": {p.id for p in scenario.resources["personas"].selected},
        "documents": {d.id for d in scenario.resources["documents"].selected},
        "parameters": {p.parameter_id for p in scenario.resources["parameters"].selected},
        "objectives": {o.id for o in scenario.resources["objectives"].selected},
        "parameter_fields": {pf.id for pf in scenario.resources["parameter_fields"].selected},
        "images": {i.id for i in scenario.resources["images"].selected},
        "videos": {v.id for v in scenario.resources["videos"].selected},
        "questions": {q.id for q in scenario.resources["questions"].selected},
        "options": {o.id for o in scenario.resources["options"].selected},
    }

    # Build field lookup from fields catalog for name/description hydration
    field_lookup = {f.id: f for f in scenario.resources["fields"].suggestions}

    # Build conditional_parameter_id → parameter_id mapping for nesting
    cond_param_to_param = {
        cp.id: cp.parameter_id
        for cp in scenario.resources.get("conditional_parameters", ResourcePair([], [])).suggestions
    }

    # Build parameter_id → name lookup for parameter_name hydration
    param_name_lookup = {p.parameter_id: p.name for p in all_parameters}

    # Build field_to_param from both scenario parameter_fields AND persona/document parameter_fields
    persona_pf_pair = scenario.resources.get("persona_parameter_fields")
    persona_pf = persona_pf_pair.suggestions if persona_pf_pair else []
    field_to_param = {
        pf.id: pf.parameter_id
        for pf in list(all_parameter_fields) + list(persona_pf)
        if pf.parameter_id
    }

    def _video_flags_for_field_ids(
        field_ids: list[UUID] | None,
    ) -> tuple[bool, bool]:
        param_ids = {
            field_to_param[field_id]
            for field_id in (field_ids or [])
            if field_id in field_to_param
        }
        has_video = bool(param_ids & video_param_ids)
        has_non_video = bool(param_ids - video_param_ids) or not param_ids
        return has_video, has_non_video

    file_map = {file.files_id: file for file in scenario.entries["files"]}
    image_entry_map = {image.images_id: image for image in scenario.entries["images"]}
    video_entry_map = {video.videos_id: video for video in scenario.entries["videos"]}

    def _to_name(name) -> ScenarioNameResource:
        return ScenarioNameResource(
            id=name.id, name=name.name, generated=name.generated
        )

    def _to_description(description) -> ScenarioDescriptionResource:
        return ScenarioDescriptionResource(
            id=description.id,
            description=description.description,
            generated=description.generated,
        )

    def _to_problem_statement(problem_statement) -> ScenarioProblemStatement:
        return ScenarioProblemStatement(
            problem_statement_id=problem_statement.id,
            name=problem_statement.name,
            problem_statement=problem_statement.problem_statement,
            generated=problem_statement.generated,
        )

    def _to_department(department) -> ScenarioDepartment:
        return ScenarioDepartment(
            department_id=department.id,
            name=department.name,
            description=department.description,
            generated=department.generated,
        )

    def _to_persona(persona) -> ScenarioPersona:
        video_persona, non_video_persona = _video_flags_for_field_ids(
            persona.parameter_field_ids
        )
        return ScenarioPersona(
            persona_id=persona.id,
            name=persona.name,
            description=persona.description,
            color=persona.color,
            icon=persona.icon,
            parameter_ids=None,
            field_ids=persona.parameter_field_ids,
            example=persona.examples[0] if persona.examples else None,
            video_persona=video_persona,
            non_video_persona=non_video_persona,
        )

    def _to_document(document) -> ScenarioDocument:
        video_document, non_video_document = _video_flags_for_field_ids(
            document.parameter_field_ids
        )
        file_entry = file_map.get(document.file_id) if document.file_id else None
        return ScenarioDocument(
            document_id=document.id,
            name=document.name,
            description=document.description,
            file_id=document.file_id,
            text_id=document.text_id,
            upload_id=file_entry.upload_id if file_entry else None,
            file_path=file_entry.file_path if file_entry else None,
            mime_type=file_entry.mime_type if file_entry else None,
            html=document.template,
            parameter_ids=None,
            field_ids=document.parameter_field_ids,
            parent_document_id=None,
            video_document=video_document,
            non_video_document=non_video_document,
        )

    def _to_parameter(parameter) -> ScenarioParameter:
        return ScenarioParameter(
            parameter_id=parameter.parameter_id,
            name=parameter.name,
            description=parameter.description,
            document_parameter=parameter.document_parameter,
            persona_parameter=parameter.persona_parameter,
            scenario_parameter=parameter.scenario_parameter,
            video_parameter=parameter.video_parameter,
            non_video_parameter=not parameter.video_parameter
            if parameter.video_parameter is not None
            else True,
        )

    def _to_field(field) -> ScenarioField:
        field_id = getattr(field, "field_id", None) or field.id
        catalog_field = field_lookup.get(field_id)
        # Resolve conditional_parameter_ids → parameter_ids for nesting
        resolved_cond_param_ids = None
        if catalog_field:
            cond_ids = getattr(catalog_field, "conditional_parameter_ids", None) or []
            resolved = [cond_param_to_param[cid] for cid in cond_ids if cid in cond_param_to_param]
            if resolved:
                resolved_cond_param_ids = resolved
        return ScenarioField(
            id=getattr(field, "id", None),
            field_id=field_id,
            name=catalog_field.name if catalog_field else None,
            description=catalog_field.description if catalog_field else None,
            parameter_id=field.parameter_id,
            parameter_name=param_name_lookup.get(field.parameter_id) if field.parameter_id else None,
            conditional_parameter_ids=resolved_cond_param_ids,
            generated=field.generated,
        )

    def _to_objective(objective) -> ScenarioObjective:
        return ScenarioObjective(
            id=objective.id,
            objective=objective.objective,
            generated=objective.generated,
        )

    def _to_image(image) -> ScenarioImage:
        entry = image_entry_map.get(image.id)
        return ScenarioImage(
            image_id=image.id,
            name=image.name,
            file_path=entry.file_path if entry else None,
            mime_type=entry.mime_type if entry else None,
            upload_id=entry.upload_id if entry else None,
            generated=image.generated,
        )

    def _to_video(video) -> ScenarioVideo:
        entry = video_entry_map.get(video.id)
        return ScenarioVideo(
            video_id=video.id,
            name=video.name,
            file_path=entry.file_path if entry else None,
            mime_type=entry.mime_type if entry else None,
            upload_id=entry.upload_id if entry else None,
            generated=video.generated,
        )

    def _to_question(question) -> ScenarioQuestion:
        return ScenarioQuestion(
            question_id=question.id,
            question_text=question.question_text,
            allow_multiple=question.allow_multiple,
            generated=question.generated,
        )

    def _to_option(option) -> ScenarioOption:
        return ScenarioOption(
            option_id=option.id,
            option_text=option.option_text,
            is_correct=option.is_correct,
            question_id=option.question_id,
            generated=option.generated,
        )

    # Build flat flag list — one row per flags_resource entry (value=true/false).
    all_flags = sorted_dedupe_by_id(
        scenario.resources["flags"].suggestions + scenario.resources["flags"].selected
    )
    selected_flag_ids = {flag.id for flag in scenario.resources["flags"].selected}
    suggested_flag_ids = {flag.id for flag in scenario.resources["flags"].suggestions}
    flags_flat = [
        ScenarioFlagResource(
            id=flag.id,
            name=getattr(flag, "name", None),
            type=getattr(flag, "type", None),
            value=getattr(flag, "value", None),
            description=flag.description,
            icon_id=getattr(flag, "icon_id", None),
            icon=getattr(flag, "icon", None),
            generated=flag.generated,
            suggested=flag.id in suggested_flag_ids,
            selected=flag.id in selected_flag_ids,
            pending=flag.id in pending_ids,
        )
        for flag in all_flags
        if flag.id and getattr(flag, "type", None) and getattr(flag, "type", None) != "scenario_parameter"
    ]

    # Convert all resources using _to_* converters
    all_names_conv = [
        _to_name(name)
        for name in sorted_dedupe_by_id(
            scenario.resources["names"].suggestions
            + scenario.resources["names"].selected
        )
    ]
    all_descriptions_conv = [
        _to_description(description)
        for description in sorted_dedupe_by_id(
            scenario.resources["descriptions"].suggestions
            + scenario.resources["descriptions"].selected
        )
    ]
    all_problem_statements_conv = [
        _to_problem_statement(problem_statement)
        for problem_statement in sorted_dedupe_by_id(
            scenario.resources["problem_statements"].suggestions
            + scenario.resources["problem_statements"].selected
        )
    ]
    all_departments_conv = [
        _to_department(department) for department in all_departments
    ]
    all_personas_conv = [_to_persona(persona) for persona in all_personas]
    all_documents_conv = [_to_document(document) for document in all_documents]
    all_parameters_conv = [_to_parameter(parameter) for parameter in all_parameters]
    all_fields_conv = [_to_field(field) for field in all_parameter_fields]

    # Filter by video_enabled mode switch
    if video_enabled is True:
        # Video mode: only video-capable entities
        all_personas_conv = [p for p in all_personas_conv if p.video_persona]
        all_documents_conv = [d for d in all_documents_conv if d.video_document]
    elif video_enabled is False:
        # Non-video mode: only non-video entities, exclude video-only fields
        all_personas_conv = [p for p in all_personas_conv if p.non_video_persona]
        all_documents_conv = [d for d in all_documents_conv if d.non_video_document]
        all_fields_conv = [
            f for f in all_fields_conv
            if not f.parameter_id or f.parameter_id not in video_param_ids
        ]
    all_objectives_conv = [_to_objective(objective) for objective in all_objectives]
    all_images_conv = [_to_image(image) for image in all_images]
    all_videos_conv = [_to_video(video) for video in all_videos]
    all_questions_conv = [_to_question(question) for question in all_questions]
    all_options_conv = [_to_option(option) for option in all_options]

    resolved_parameter_ids = list(
        {
            str(parameter_field.parameter_id)
            for parameter_field in scenario.resources["parameter_fields"].selected
            if parameter_field.parameter_id
        }
    )

    # Helper to apply _model_many_with_flags for sections with custom model builders
    # (the _to_* converters already produce the right model, so we just mark flags)
    def _mark_flags(items, suggested_ids: set, selected_ids: set, id_attr: str = "id"):
        for item in items:
            item_id = getattr(item, id_attr, None)
            if item_id and item_id in suggested_ids:
                item.suggested = True
            if item_id and item_id in selected_ids:
                item.selected = True
            if item_id and item_id in pending_ids:
                item.pending = True
        return items

    # Mark selected/suggested on all converted lists
    sug = suggestions_sets
    sel = selected_sets

    _mark_flags(all_names_conv, sug["names"], sel["names"])
    _mark_flags(all_descriptions_conv, sug["descriptions"], sel["descriptions"])
    _mark_flags(all_problem_statements_conv, sug["problem_statements"], sel["problem_statements"], id_attr="problem_statement_id")
    _mark_flags(all_departments_conv, sug["departments"], sel["departments"], id_attr="department_id")
    _mark_flags(all_personas_conv, sug["personas"], sel["personas"], id_attr="persona_id")
    _mark_flags(all_documents_conv, sug["documents"], sel["documents"], id_attr="document_id")
    _mark_flags(all_parameters_conv, sug["parameters"], sel["parameters"], id_attr="parameter_id")
    # parameter_fields are keyed by the junction row id (parameter_fields_resource.id):
    # selected_sets["parameter_fields"] collects pf.id, and the client picker
    # emits those same ids. Matching by field_id would never align, so
    # selected/suggested flags never got set.
    _mark_flags(all_fields_conv, sug["parameter_fields"], sel["parameter_fields"], id_attr="id")
    _mark_flags(all_objectives_conv, sug["objectives"], sel["objectives"])
    _mark_flags(all_images_conv, sug["images"], sel["images"], id_attr="image_id")
    _mark_flags(all_videos_conv, sug["videos"], sel["videos"], id_attr="video_id")
    _mark_flags(all_questions_conv, sug["questions"], sel["questions"], id_attr="question_id")
    _mark_flags(all_options_conv, sug["options"], sel["options"], id_attr="option_id")

    return GetScenarioApiResponse(
        actor_name=profile.name,
        scenario_exists=scenario.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_scenario_context``). ``None`` when no draft was active.
        draft_name=scenario.entries.get("draft_name") if scenario.entries else None,
        show_ai_generate=show_ai_generate,
        resolved_parameter_ids=resolved_parameter_ids or None,
        names=_filter_section(all_names_conv, "names") if inc.get("names", True) else None,
        descriptions=_filter_section(all_descriptions_conv, "descriptions") if inc.get("descriptions", True) else None,
        problem_statements=_filter_section(all_problem_statements_conv, "problem_statements") if inc.get("problem_statements", True) else None,
        flags=_filter_section(flags_flat, "flags") if inc.get("flags", True) else None,
        departments=_filter_section(all_departments_conv, "departments") if inc.get("departments", True) else None,
        personas=_filter_section(all_personas_conv, "personas") if inc.get("personas", True) else None,
        documents=_filter_section(all_documents_conv, "documents") if inc.get("documents", True) else None,
        parameters=_filter_section(all_parameters_conv, "parameters") if inc.get("parameters", True) else None,
        parameter_fields=_filter_section(all_fields_conv, "parameter_fields") if inc.get("parameter_fields", True) else None,
        objectives=_filter_section(all_objectives_conv, "objectives") if inc.get("objectives", True) else None,
        images=_filter_section(all_images_conv, "images") if inc.get("images", True) else None,
        videos=_filter_section(all_videos_conv, "videos") if inc.get("videos", True) else None,
        questions=_filter_section(all_questions_conv, "questions") if inc.get("questions", True) else None,
        options=_filter_section(all_options_conv, "options") if inc.get("options", True) else None,
    )
