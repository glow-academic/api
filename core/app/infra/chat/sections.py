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
    pair = context.resources.get(resource_key)
    if not pair:
        return cls(show=True, required=False)
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
    return GetChatResponse(
        chat_entry_id=chat_entry_id or group_id,
        attempt_id=attempt_id,
        group_id=group_id,
        draft_version=context.draft_version,
        names=_build_chat_section("names", context=context, scores=scores),
        descriptions=_build_chat_section(
            "descriptions", context=context, scores=scores
        ),
        flags=_build_chat_section("flags", context=context, scores=scores),
        departments=_build_chat_section("departments", context=context, scores=scores),
        personas=_build_chat_section("personas", context=context, scores=scores),
        documents=_build_chat_section("documents", context=context, scores=scores),
        parameter_fields=_build_chat_section(
            "parameter_fields", context=context, scores=scores
        ),
        scenarios=_build_chat_section("scenarios", context=context, scores=scores),
        fields=_build_chat_section("fields", context=context, scores=scores),
        questions=_build_chat_section("questions", context=context, scores=scores),
        options=_build_chat_section("options", context=context, scores=scores),
        videos=_build_chat_section("videos", context=context, scores=scores),
        images=_build_chat_section("images", context=context, scores=scores),
        problem_statements=_build_chat_section(
            "problem_statements", context=context, scores=scores
        ),
        objectives=_build_chat_section("objectives", context=context, scores=scores),
    )
