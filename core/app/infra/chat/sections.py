"""Canonical section builder for chat bundle responses."""

from __future__ import annotations

from uuid import UUID

from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext
from app.infra.chat.types import (
    BaseChatSection,
    ChatDepartmentSection,
    ChatDescriptionSection,
    ChatDocumentSection,
    ChatFieldSection,
    ChatFlagSection,
    ChatImageSection,
    ChatNameSection,
    ChatObjectiveSection,
    ChatOptionSection,
    ChatParameterFieldSection,
    ChatPersonaSection,
    ChatProblemStatementSection,
    ChatQuestionSection,
    ChatScenarioSection,
    ChatVideoSection,
    GetChatResponse,
)

_SECTION_CLASSES: dict[str, type[BaseChatSection]] = {
    "names": ChatNameSection,
    "descriptions": ChatDescriptionSection,
    "flags": ChatFlagSection,
    "departments": ChatDepartmentSection,
    "personas": ChatPersonaSection,
    "documents": ChatDocumentSection,
    "parameter_fields": ChatParameterFieldSection,
    "scenarios": ChatScenarioSection,
    "fields": ChatFieldSection,
    "questions": ChatQuestionSection,
    "options": ChatOptionSection,
    "videos": ChatVideoSection,
    "images": ChatImageSection,
    "problem_statements": ChatProblemStatementSection,
    "objectives": ChatObjectiveSection,
}


def _build_chat_section(
    resource_key: str,
    *,
    context: ArtifactContext,
    scores: ArtifactToolScores,
) -> BaseChatSection:
    cls = _SECTION_CLASSES[resource_key]

    # Section absent from context → disabled (hidden)
    pair = context.resources.get(resource_key)
    if pair is None:
        return cls(show=False, required=False)

    return cls(
        show=True,
        required=False,
        show_ai_generate=scores.best.get(resource_key) is not None,
        current=pair.selected or None,
        resources=pair.suggestions or None,
    )


def build_chat_get_result(
    *,
    context: ArtifactContext,
    scores: ArtifactToolScores,
    group_id: UUID,
    chat_entry_id: UUID | None,
    attempt_id: UUID | None,
) -> GetChatResponse:
    """Build the canonical chat bundle payload from resolved context."""
    kw = dict(context=context, scores=scores)
    return GetChatResponse(
        chat_entry_id=chat_entry_id or group_id,
        attempt_id=attempt_id,
        group_id=group_id,
        names=_build_chat_section("names", **kw),
        descriptions=_build_chat_section("descriptions", **kw),
        flags=_build_chat_section("flags", **kw),
        departments=_build_chat_section("departments", **kw),
        personas=_build_chat_section("personas", **kw),
        documents=_build_chat_section("documents", **kw),
        parameter_fields=_build_chat_section("parameter_fields", **kw),
        scenarios=_build_chat_section("scenarios", **kw),
        fields=_build_chat_section("fields", **kw),
        questions=_build_chat_section("questions", **kw),
        options=_build_chat_section("options", **kw),
        videos=_build_chat_section("videos", **kw),
        images=_build_chat_section("images", **kw),
        problem_statements=_build_chat_section("problem_statements", **kw),
        objectives=_build_chat_section("objectives", **kw),
    )
