"""Canonical scenario section assembly."""

from __future__ import annotations

from uuid import UUID

from app.infra.common_context import CommonContext
from app.infra.helpers import dedupe_by_id
from app.infra.scenario.permissions import (
    SCENARIO_BASIC_RESOURCES,
    SCENARIO_CONTENT_RESOURCES,
    SCENARIO_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_documents_required,
    compute_fields_required,
    compute_flag_required,
    compute_images_required,
    compute_name_required,
    compute_objectives_required,
    compute_parameters_required,
    compute_personas_required,
    compute_problem_statement_required,
    compute_questions_required,
    compute_show_departments,
    compute_show_description,
    compute_show_documents,
    compute_show_fields,
    compute_show_flag,
    compute_show_images,
    compute_show_name,
    compute_show_objectives,
    compute_show_parameters,
    compute_show_personas,
    compute_show_problem_statement,
    compute_show_questions,
    compute_show_videos,
    compute_videos_required,
)
from app.infra.scenario.permissions_context import ScenarioPermissionsContext
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext
from app.infra.scenario.types import (
    GetScenarioApiResponse,
    ScenarioDepartment,
    ScenarioDepartmentSection,
    ScenarioDescriptionResource,
    ScenarioDescriptionSection,
    ScenarioDocument,
    ScenarioDocumentSection,
    ScenarioField,
    ScenarioFlagConfig,
    ScenarioFlagSection,
    ScenarioImage,
    ScenarioImageSection,
    ScenarioNameResource,
    ScenarioNameSection,
    ScenarioObjective,
    ScenarioObjectiveSection,
    ScenarioOption,
    ScenarioOptionSection,
    ScenarioParameter,
    ScenarioParameterFieldSection,
    ScenarioParameterSection,
    ScenarioPersona,
    ScenarioPersonaSection,
    ScenarioProblemStatement,
    ScenarioProblemStatementSection,
    ScenarioQuestion,
    ScenarioQuestionSection,
    ScenarioVideo,
    ScenarioVideoSection,
)


def build_scenario_get_result(
    *,
    common: CommonContext,
    scenario: ArtifactContext,
    scores: ArtifactToolScores,
    perms: ScenarioPermissionsContext | None,
    group_id: UUID | None,
) -> GetScenarioApiResponse:
    """Build the canonical scenario response bundle from resolved contexts."""
    profile = common.profile

    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in SCENARIO_RESOURCES
    }
    tool_ids_map: dict[str, UUID | None] = {
        resource: (scores.best[resource].tool_id if scores.best.get(resource) else None)
        for resource in SCENARIO_RESOURCES
    }

    scenario_department_ids = [d.id for d in scenario.resources["departments"].selected]
    active_simulation_count = perms.active_simulation_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        scenario_department_ids=scenario_department_ids,
        active_simulation_count=active_simulation_count,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        scenario_department_ids=scenario_department_ids,
        active_simulation_count=active_simulation_count,
        user_department_ids=profile.department_ids,
    )

    all_departments = dedupe_by_id(
        scenario.resources["departments"].selected
        + scenario.resources["departments"].suggestions
    )
    all_personas = dedupe_by_id(
        scenario.resources["personas"].selected
        + scenario.resources["personas"].suggestions
    )
    all_documents = dedupe_by_id(
        scenario.resources["documents"].selected
        + scenario.resources["documents"].suggestions
    )
    all_parameters = dedupe_by_id(
        scenario.resources["parameters"].selected
        + scenario.resources["parameters"].suggestions
    )
    all_parameter_fields = dedupe_by_id(
        scenario.resources["parameter_fields"].selected
        + scenario.resources["parameter_fields"].suggestions
    )
    all_objectives = scenario.resources["objectives"].selected
    all_images = dedupe_by_id(
        scenario.resources["images"].selected + scenario.resources["images"].suggestions
    )
    all_videos = dedupe_by_id(
        scenario.resources["videos"].selected + scenario.resources["videos"].suggestions
    )
    all_questions = dedupe_by_id(
        scenario.resources["questions"].selected
        + scenario.resources["questions"].suggestions
    )
    all_options = dedupe_by_id(
        scenario.resources["options"].selected
        + scenario.resources["options"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(),
        "descriptions": compute_show_description(),
        "problem_statements": compute_show_problem_statement(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "personas": compute_show_personas(len(all_personas)),
        "documents": compute_show_documents(len(all_documents)),
        "parameters": compute_show_parameters(len(all_parameters)),
        "fields": compute_show_fields(len(all_parameter_fields)),
        "objectives": compute_show_objectives(len(all_objectives)),
        "images": compute_show_images(len(all_images)),
        "videos": compute_show_videos(len(all_videos)),
        "questions": compute_show_questions(len(all_questions)),
        "options": len(all_options) > 0,
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "problem_statements": compute_problem_statement_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "personas": compute_personas_required(),
        "documents": compute_documents_required(),
        "parameters": compute_parameters_required(),
        "fields": compute_fields_required(),
        "objectives": compute_objectives_required(),
        "images": compute_images_required(),
        "videos": compute_videos_required(),
        "questions": compute_questions_required(),
        "options": False,
    }

    show_ai_generate_map = {
        resource: agent_ids.get(resource) is not None for resource in SCENARIO_RESOURCES
    }
    basic_show_ai_generate = any(
        show_ai_generate_map.get(resource, False)
        for resource in SCENARIO_BASIC_RESOURCES
    )
    content_show_ai_generate = any(
        show_ai_generate_map.get(resource, False)
        for resource in SCENARIO_CONTENT_RESOURCES
    )

    suggestions_map: dict[str, list[UUID]] = {
        "names": [n.id for n in scenario.resources["names"].suggestions],
        "descriptions": [d.id for d in scenario.resources["descriptions"].suggestions],
        "problem_statements": [
            ps.id for ps in scenario.resources["problem_statements"].suggestions
        ],
        "departments": [d.id for d in scenario.resources["departments"].suggestions],
        "personas": [p.id for p in scenario.resources["personas"].suggestions],
        "documents": [d.id for d in scenario.resources["documents"].suggestions],
        "parameters": [p.id for p in scenario.resources["parameters"].suggestions],
        "objectives": [],
        "images": [i.id for i in scenario.resources["images"].suggestions],
        "videos": [v.id for v in scenario.resources["videos"].suggestions],
        "questions": [q.id for q in scenario.resources["questions"].suggestions],
        "options": [o.id for o in scenario.resources["options"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    video_param_ids = {
        parameter.id for parameter in all_parameters if parameter.video_parameter
    }
    field_to_param = {
        parameter_field.id: parameter_field.parameter_id
        for parameter_field in all_parameter_fields
        if parameter_field.parameter_id
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
            parameter_id=parameter.id,
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
        return ScenarioField(
            field_id=getattr(field, "field_id", None) or field.id,
            parameter_id=field.parameter_id,
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

    all_flags = dedupe_by_id(
        scenario.resources["flags"].selected + scenario.resources["flags"].suggestions
    )
    scenario_flags = [
        ScenarioFlagConfig(
            key=flag.type,
            label=flag.name,
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            generated=flag.generated,
            video_flag=flag.type == "questions_enabled",
        )
        for flag in all_flags
        if flag.id and flag.type and flag.type != "scenario_parameter"
    ]
    scenario_flags.sort(key=lambda flag: flag.video_flag or False)

    current_flag_ids = {flag.id for flag in scenario.resources["flags"].selected}

    all_names = [
        _to_name(name)
        for name in dedupe_by_id(
            scenario.resources["names"].selected
            + scenario.resources["names"].suggestions
        )
    ]
    all_descriptions_conv = [
        _to_description(description)
        for description in dedupe_by_id(
            scenario.resources["descriptions"].selected
            + scenario.resources["descriptions"].suggestions
        )
    ]
    all_problem_statements = [
        _to_problem_statement(problem_statement)
        for problem_statement in dedupe_by_id(
            scenario.resources["problem_statements"].selected
            + scenario.resources["problem_statements"].suggestions
        )
    ]
    all_departments_conv = [
        _to_department(department) for department in all_departments
    ]
    all_personas_conv = [_to_persona(persona) for persona in all_personas]
    all_documents_conv = [_to_document(document) for document in all_documents]
    all_parameters_conv = [_to_parameter(parameter) for parameter in all_parameters]
    all_fields_conv = [_to_field(field) for field in all_parameter_fields]
    all_objectives_conv = [_to_objective(objective) for objective in all_objectives]
    all_images_conv = [_to_image(image) for image in all_images]
    all_videos_conv = [_to_video(video) for video in all_videos]
    all_questions_conv = [_to_question(question) for question in all_questions]
    all_options_conv = [_to_option(option) for option in all_options]

    current_departments = [
        _to_department(department)
        for department in scenario.resources["departments"].selected
    ]
    current_personas = [
        _to_persona(persona) for persona in scenario.resources["personas"].selected
    ]
    current_documents = [
        _to_document(document) for document in scenario.resources["documents"].selected
    ]
    current_parameters = [
        _to_parameter(parameter)
        for parameter in scenario.resources["parameters"].selected
    ]
    current_fields = [
        _to_field(field) for field in scenario.resources["parameter_fields"].selected
    ]
    current_objectives = [
        _to_objective(objective)
        for objective in scenario.resources["objectives"].selected
    ]
    current_images = [
        _to_image(image) for image in scenario.resources["images"].selected
    ]
    current_videos = [
        _to_video(video) for video in scenario.resources["videos"].selected
    ]
    current_questions = [
        _to_question(question) for question in scenario.resources["questions"].selected
    ]
    current_options = [
        _to_option(option) for option in scenario.resources["options"].selected
    ]

    resolved_parameter_ids = list(
        {
            str(parameter_field.parameter_id)
            for parameter_field in scenario.resources["parameter_fields"].selected
            if parameter_field.parameter_id
        }
    )

    return GetScenarioApiResponse(
        actor_name=profile.name,
        scenario_exists=scenario.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=scenario.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        content_show_ai_generate=content_show_ai_generate,
        resolved_parameter_ids=resolved_parameter_ids or None,
        names=ScenarioNameSection(
            **_section("names"),
            resource=_to_name(scenario.resources["names"].selected[0])
            if scenario.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=ScenarioDescriptionSection(
            **_section("descriptions"),
            resource=_to_description(scenario.resources["descriptions"].selected[0])
            if scenario.resources["descriptions"].selected
            else None,
            resources=all_descriptions_conv,
        ),
        problem_statements=ScenarioProblemStatementSection(
            **_section("problem_statements"),
            resource=_to_problem_statement(
                scenario.resources["problem_statements"].selected[0]
            )
            if scenario.resources["problem_statements"].selected
            else None,
            resources=all_problem_statements,
        ),
        flags=ScenarioFlagSection(
            **_section("flags"),
            current=[
                flag
                for flag in scenario_flags
                if flag.flag_option_id in current_flag_ids
            ],
            resources=scenario_flags,
        ),
        departments=ScenarioDepartmentSection(
            **_section("departments"),
            current=current_departments,
            resources=all_departments_conv,
        ),
        personas=ScenarioPersonaSection(
            **_section("personas"),
            current=current_personas,
            resources=all_personas_conv,
        ),
        documents=ScenarioDocumentSection(
            **_section("documents"),
            current=current_documents,
            resources=all_documents_conv,
        ),
        parameters=ScenarioParameterSection(
            **_section("parameters"),
            current=current_parameters,
            resources=all_parameters_conv,
        ),
        parameter_fields=ScenarioParameterFieldSection(
            **_section("fields"),
            current=current_fields,
            resources=all_fields_conv,
        ),
        objectives=ScenarioObjectiveSection(
            **_section("objectives"),
            current=current_objectives,
            resources=all_objectives_conv,
        ),
        images=ScenarioImageSection(
            **_section("images"),
            current=current_images,
            resources=all_images_conv,
        ),
        videos=ScenarioVideoSection(
            **_section("videos"),
            current=current_videos,
            resources=all_videos_conv,
        ),
        questions=ScenarioQuestionSection(
            **_section("questions"),
            current=current_questions,
            resources=all_questions_conv,
        ),
        options=ScenarioOptionSection(
            **_section("options"),
            current=current_options,
            resources=all_options_conv,
        ),
    )
