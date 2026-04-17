"""Canonical chat section assembly."""

from __future__ import annotations

from uuid import UUID

from app.infra.common_context import CommonContext
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext
from app.infra.chat.types import (
    ChatDepartmentResource,
    ChatDescriptionResource,
    ChatDocumentResource,
    ChatFieldResource,
    ChatFlagResource,
    ChatImageResource,
    ChatNameResource,
    ChatObjectiveResource,
    ChatOptionResource,
    ChatParameterFieldResource,
    ChatPersonaResource,
    ChatProblemStatementResource,
    ChatQuestionResource,
    ChatScenarioResource,
    ChatVideoResource,
    GetChatResponse,
)

CHAT_SECTIONS = [
    "names",
    "descriptions",
    "flags",
    "departments",
    "personas",
    "documents",
    "parameter_fields",
    "scenarios",
    "fields",
    "questions",
    "options",
    "videos",
    "images",
    "problem_statements",
    "objectives",
]


def build_chat_get_result(
    *,
    common: CommonContext,
    context: ArtifactContext,
    scores: ArtifactToolScores,
    chat_entry_id: UUID | None,
    attempt_id: UUID | None,
    include: dict[str, bool] | None = None,
    selected_only: dict[str, bool] | None = None,
    suggested_only: dict[str, bool] | None = None,
) -> GetChatResponse:
    """Build the canonical chat response bundle from resolved context."""
    inc = include or {}
    sel_only = selected_only or {}
    sug_only = suggested_only or {}
    pending_ids: set[UUID] = context.entries.get("pending_ids", set())

    def _filter(items: list | None, section: str) -> list | None:
        if items is None:
            return None
        if sel_only.get(section):
            items = [item for item in items if getattr(item, "selected", False)]
        if sug_only.get(section):
            items = [item for item in items if getattr(item, "suggested", False)]
        return items

    def _ids_from(section: str, id_attr: str) -> list[UUID]:
        pair = context.resources.get(section)
        if not pair:
            return []
        return [
            item_id
            for item in (getattr(item, id_attr, None) for item in pair.selected)
            if item_id is not None
        ]

    def _model_many(section: str, items, model_cls, *, id_attr: str = "id", rename: dict[str, str] | None = None):
        pair = context.resources.get(section)
        selected_ids = {
            getattr(item, id_attr, None) for item in (pair.selected if pair else [])
        }
        suggested_ids = {
            getattr(item, id_attr, None) for item in (pair.suggestions if pair else [])
        }
        result = []
        for item in items:
            payload = item.model_dump()
            if rename:
                for src, dst in rename.items():
                    payload[dst] = payload.pop(src, None)
            model = model_cls.model_validate(payload)
            item_id = getattr(item, id_attr, None)
            if item_id and item_id in selected_ids:
                model.selected = True
            if item_id and item_id in suggested_ids:
                model.suggested = True
            if item_id and item_id in pending_ids:
                model.pending = True
            result.append(model)
        return result

    def _section(section: str, model_cls, *, id_attr: str = "id", rename: dict[str, str] | None = None):
        if inc.get(section) is False:
            return None
        pair = context.resources.get(section)
        if pair is None:
            return None
        all_items = dedupe_by_id(pair.selected + pair.suggestions, id_attr=id_attr)
        return _filter(
            _model_many(section, all_items, model_cls, id_attr=id_attr, rename=rename),
            section,
        )

    names = _section("names", ChatNameResource)
    descriptions = _section("descriptions", ChatDescriptionResource)
    flags = _section("flags", ChatFlagResource)
    departments = _section(
        "departments",
        ChatDepartmentResource,
        rename={"id": "department_id"},
    )
    personas = _section(
        "personas",
        ChatPersonaResource,
        rename={"id": "persona_id"},
    )
    documents = _section(
        "documents",
        ChatDocumentResource,
        rename={"id": "document_id"},
    )
    parameter_fields = _section("parameter_fields", ChatParameterFieldResource)
    scenarios = _section(
        "scenarios",
        ChatScenarioResource,
        rename={"id": "scenario_id"},
    )
    fields = _section(
        "fields",
        ChatFieldResource,
        rename={"id": "field_id"},
    )
    questions = _section(
        "questions",
        ChatQuestionResource,
        rename={"id": "question_id"},
    )
    options = _section(
        "options",
        ChatOptionResource,
        rename={"id": "option_id"},
    )
    videos = _section(
        "videos",
        ChatVideoResource,
        rename={"id": "video_id"},
    )
    images = _section(
        "images",
        ChatImageResource,
        rename={"id": "image_id"},
    )
    problem_statements = _section(
        "problem_statements",
        ChatProblemStatementResource,
        rename={"id": "problem_statement_id"},
    )
    objectives = _section("objectives", ChatObjectiveResource)

    show_ai_generate = any(scores.best.get(section) is not None for section in CHAT_SECTIONS)

    return GetChatResponse(
        actor_name=common.profile.name,
        chat_exists=context.entries.get("chat_exists"),
        can_edit=True,
        disabled_reason=None,
        group_id=context.group_id,
        show_ai_generate=show_ai_generate,
        profile_has_access=True,
        simulation_name=None,
        chat_entry_id=chat_entry_id,
        attempt_id=attempt_id,
        names=names,
        descriptions=descriptions,
        flags=flags,
        departments=departments,
        personas=personas,
        documents=documents,
        parameter_fields=parameter_fields,
        scenarios=scenarios,
        fields=fields,
        questions=questions,
        options=options,
        videos=videos,
        images=images,
        problem_statements=problem_statements,
        objectives=objectives,
        name_ids=_ids_from("names", "id"),
        description_ids=_ids_from("descriptions", "id"),
        flag_ids=_ids_from("flags", "id"),
        department_ids=_ids_from("departments", "id"),
        persona_ids=_ids_from("personas", "id"),
        document_ids=_ids_from("documents", "id"),
        parameter_field_ids=_ids_from("parameter_fields", "id"),
        scenario_ids=_ids_from("scenarios", "id"),
        field_ids=_ids_from("fields", "id"),
        question_ids=_ids_from("questions", "id"),
        option_ids=_ids_from("options", "id"),
        video_ids=_ids_from("videos", "id"),
        image_ids=_ids_from("images", "id"),
        problem_statement_ids=_ids_from("problem_statements", "id"),
        objective_ids=_ids_from("objectives", "id"),
    )
