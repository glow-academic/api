"""Canonical shared attempt GET operation."""

from __future__ import annotations

from collections import defaultdict as _defaultdict
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.context import resolve_attempt_context
from app.infra.attempt.permissions import (
    check_attempt_access,
    compute_achieved_standards,
    compute_attempt_aggregates,
    compute_chat_position_and_current,
    compute_continuation_options,
    compute_current_chat_index,
    compute_passed_standards,
    compute_percentage,
    compute_total_possible_points,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.attempt.types import (
    AggregatedResults,
    AnalysisEntry,
    AttemptData,
    AttemptEntries,
    AttemptInternalData,
    AttemptResources,
    ChatData,
    ContentEntry,
    DocumentEntry,
    FeedbackEntry,
    GetAttemptDetailResponse,
    GradeData,
    GradingStateData,
    HighlightEntry,
    HintEntry,
    ImageEntry,
    MessageData,
    MessageFeedbackEntry,
    ObjectiveEntry,
    OptionEntry,
    PersonaEntry,
    ProblemStatementEntry,
    QuestionEntry,
    QuizResponse,
    ReplacementEntry,
    RubricEntry,
    RubricStructureData,
    ScenarioEntry,
    SimulationData,
    StandardEntry,
    StandardGroupEntry,
    StandardGroupMeta,
    StandardMeta,
    TimerData,
    VideoEntry,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


def _format_timer(
    elapsed: int, limit_seconds: int | None, infinite_mode: bool, negative: bool = False
) -> TimerData:
    """Format timer data."""
    if limit_seconds is None or limit_seconds == 0:
        return TimerData(
            elapsed=elapsed,
            limit=None,
            exceeded=False,
            formatted="",
            negative=negative,
        )

    remaining = limit_seconds - elapsed
    if not negative:
        remaining = max(remaining, 0)
    exceeded = remaining <= 0 if infinite_mode else elapsed > limit_seconds

    abs_remaining = abs(remaining)
    hours = abs_remaining // 3600
    minutes = (abs_remaining % 3600) // 60
    seconds = abs_remaining % 60
    sign = "-" if remaining < 0 else ""
    formatted = f"{sign}{hours}h {minutes}m {seconds}s"

    return TimerData(
        elapsed=elapsed,
        limit=limit_seconds,
        exceeded=exceeded,
        formatted=formatted,
        negative=negative,
    )


async def get_attempt_internal(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    attempt_id: UUID,
    bypass_cache: bool = False,
) -> AttemptInternalData:
    """Core attempt detail fetcher with no HTTP concerns."""
    requester = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache
    )
    profiles_id = requester.profiles_id if requester else None
    requester_role: str | None = requester.role if requester else None

    ctx = await resolve_attempt_context(
        pool,
        redis,
        attempt_id=attempt_id,
        bypass_cache=bypass_cache,
    )

    attempts = ctx.entries.get("attempts", [])
    chats_result = ctx.entries.get("chats", [])
    messages_result = ctx.entries.get("messages", [])
    contents_result = ctx.entries.get("contents", [])
    strengths_result = ctx.entries.get("strengths", [])
    improvements_result = ctx.entries.get("improvements", [])
    hints_result = ctx.entries.get("hints", [])
    grades_result = ctx.entries.get("grades", [])
    responses_result = ctx.entries.get("responses", [])
    highlights_result = ctx.entries.get("highlights", [])
    replacements_result = ctx.entries.get("replacements", [])
    feedbacks_result = ctx.entries.get("feedbacks", [])
    analyses_result = ctx.entries.get("analyses", [])

    if not attempts:
        return AttemptInternalData(
            actor_name=None,
            attempt_exists=False,
            access_denied=True,
            is_own_attempt=False,
            practice=False,
            profiles_id=profiles_id,
            profile_name=None,
            simulation_name=None,
            training_id=None,
            chat_entry_id=None,
            group_id=None,
        )

    attempt_item = attempts[0]

    def _res(key: str) -> list:
        return ctx.resources[key].selected if key in ctx.resources else []

    simulations_list = _res("simulations")
    profiles_list = _res("profiles")
    simulation_map = {s.id: s for s in simulations_list}
    profile_map = {p.id: p for p in profiles_list}

    contents_by_message: dict[UUID, list] = _defaultdict(list)
    for content in contents_result:
        if content.message_id:
            contents_by_message[content.message_id].append(content)

    strengths_by_message: dict[UUID, list] = _defaultdict(list)
    for strength in strengths_result:
        if strength.message_id:
            strengths_by_message[strength.message_id].append(strength)

    improvements_by_message: dict[UUID, list] = _defaultdict(list)
    for improvement in improvements_result:
        if improvement.message_id:
            improvements_by_message[improvement.message_id].append(improvement)

    hints_by_message: dict[UUID, list] = _defaultdict(list)
    for hint in hints_result:
        if hint.message_id:
            hints_by_message[hint.message_id].append(hint)

    highlights_by_strength: dict[UUID, list] = _defaultdict(list)
    for highlight in highlights_result:
        if highlight.strength_id:
            highlights_by_strength[highlight.strength_id].append(highlight)

    replacements_by_improvement: dict[UUID, list] = _defaultdict(list)
    for replacement in replacements_result:
        if replacement.improvement_id:
            replacements_by_improvement[replacement.improvement_id].append(replacement)

    grades_by_chat: dict[UUID, Any] = {}
    for grade in grades_result:
        if grade.chat_id:
            grades_by_chat[grade.chat_id] = grade

    feedbacks_by_grade: dict[UUID, list] = _defaultdict(list)
    for feedback in feedbacks_result:
        if feedback.grade_id:
            feedbacks_by_grade[feedback.grade_id].append(feedback)

    analyses_by_grade: dict[UUID, list] = _defaultdict(list)
    for analysis in analyses_result:
        if analysis.grade_id:
            analyses_by_grade[analysis.grade_id].append(analysis)

    responses_by_chat: dict[UUID, list] = _defaultdict(list)
    for response in responses_result:
        if response.chat_id:
            responses_by_chat[response.chat_id].append(response)

    practice = attempt_item.practice or False

    simulation_name: str | None = None
    if attempt_item.simulation_id and attempt_item.simulation_id in simulation_map:
        simulation_name = simulation_map[attempt_item.simulation_id].name

    profile_name: str | None = None
    if attempt_item.profile_id and attempt_item.profile_id in profile_map:
        profile_name = profile_map[attempt_item.profile_id].name

    attempt_owner_role: str | None = None
    if attempt_item.profile_id and attempt_item.profile_id in profile_map:
        attempt_owner_role = profile_map[attempt_item.profile_id].role

    if not check_attempt_access(
        attempt_item.profile_id,
        profiles_id,
        request_role=requester_role,
        attempt_role=attempt_owner_role,
    ):
        return AttemptInternalData(
            actor_name=profile_name,
            attempt_exists=True,
            access_denied=True,
            is_own_attempt=False,
            practice=practice,
            profiles_id=profiles_id,
            profile_name=profile_name,
            simulation_name=simulation_name,
            training_id=None,
            chat_entry_id=None,
            group_id=None,
        )

    chat_entry_id = attempt_item.chat_entry_id
    training_id = chat_entry_id
    first_chat_item = chats_result[0] if chats_result else None
    group_id = first_chat_item.group_id if first_chat_item else None
    time_limit_seconds = sum(chat.time_limit_seconds or 0 for chat in chats_result)
    allows_negative_time = any(chat.negative or False for chat in chats_result)

    resource_meta: dict[str, dict[UUID, dict]] = {
        "images": {},
        "videos": {},
        "documents": {},
        "personas": {},
        "objectives": {},
        "questions": {},
        "options": {},
        "problem_statements": {},
        "scenarios": {},
        "rubrics": {},
        "standard_groups": {},
        "standards": {},
    }

    image_entry_map = {
        image.images_id: image for image in ctx.entries.get("images", [])
    }
    video_entry_map = {
        video.videos_id: video for video in ctx.entries.get("videos", [])
    }
    file_entry_map = {file.files_id: file for file in ctx.entries.get("files", [])}

    for item in _res("images"):
        if item.id:
            entry = image_entry_map.get(item.id)
            resource_meta["images"][item.id] = {
                "name": item.name,
                "description": item.description,
                "upload_id": entry.upload_id if entry else None,
            }
    for item in _res("videos"):
        if item.id:
            entry = video_entry_map.get(item.id)
            resource_meta["videos"][item.id] = {
                "name": item.name,
                "description": item.description,
                "upload_id": entry.upload_id if entry else None,
            }
    for item in _res("documents"):
        if item.id:
            file_entry = file_entry_map.get(item.file_id) if item.file_id else None
            resource_meta["documents"][item.id] = {
                "name": item.name,
                "description": item.description,
                "upload_id": file_entry.upload_id if file_entry else None,
                "template": item.template,
            }
    for item in _res("personas"):
        if item.id:
            resource_meta["personas"][item.id] = {
                "name": item.name,
                "icon": item.icon,
                "color": item.color,
                "instructions": item.instructions,
                "examples": item.examples,
            }
    for item in _res("objectives"):
        if item.id:
            resource_meta["objectives"][item.id] = {"objective": item.objective}
    for item in _res("questions"):
        if item.id:
            resource_meta["questions"][item.id] = {
                "question_text": item.question_text,
                "allow_multiple": item.allow_multiple,
                "time": item.time,
            }
    for item in _res("options"):
        if item.id:
            resource_meta["options"][item.id] = {
                "option_text": item.option_text,
                "is_correct": item.is_correct,
                "question_id": item.question_id,
            }
    for item in _res("problem_statements"):
        if item.id:
            resource_meta["problem_statements"][item.id] = {
                "problem_statement": item.problem_statement,
            }
    for item in _res("scenarios"):
        if item.id:
            resource_meta["scenarios"][item.id] = {
                "name": item.name,
                "description": item.description,
            }
    for item in _res("rubrics"):
        if item.id:
            resource_meta["rubrics"][item.id] = {
                "name": item.name,
                "description": item.description,
                "total_points": item.total_points,
                "pass_points": item.pass_points,
            }
    for item in _res("standard_groups"):
        if item.id:
            resource_meta["standard_groups"][item.id] = {
                "name": item.name,
                "description": item.description,
                "points": item.points,
                "pass_points": item.pass_points,
            }
    for item in _res("standards"):
        if item.id:
            resource_meta["standards"][item.id] = {
                "name": item.name,
                "description": item.description,
                "points": item.points,
                "standard_group_id": item.standard_group_id,
            }

    resources_payload = AttemptResources(
        images={
            str(k): ImageEntry(
                image_id=k,
                upload_id=v.get("upload_id"),
                name=v.get("name"),
                description=v.get("description"),
            )
            for k, v in resource_meta["images"].items()
        }
        or None,
        videos={
            str(k): VideoEntry(
                video_id=k,
                upload_id=v.get("upload_id"),
                name=v.get("name"),
                description=v.get("description"),
            )
            for k, v in resource_meta["videos"].items()
        }
        or None,
        documents={
            str(k): DocumentEntry(
                document_id=k,
                upload_id=v.get("upload_id"),
                name=v.get("name"),
                description=v.get("description"),
                template=v.get("template"),
            )
            for k, v in resource_meta["documents"].items()
        }
        or None,
        personas={
            str(k): PersonaEntry(
                id=k,
                name=v.get("name"),
                icon=v.get("icon"),
                color=v.get("color"),
                instructions=v.get("instructions"),
                examples=v.get("examples"),
            )
            for k, v in resource_meta["personas"].items()
        }
        or None,
        objectives={
            str(k): ObjectiveEntry(objective_id=k, objective=v.get("objective"))
            for k, v in resource_meta["objectives"].items()
        }
        or None,
        questions={
            str(k): QuestionEntry(
                question_id=k,
                question_text=v.get("question_text"),
                allow_multiple=v.get("allow_multiple"),
                times=([v.get("time")] if v.get("time") is not None else None),
            )
            for k, v in resource_meta["questions"].items()
        }
        or None,
        options={
            str(k): OptionEntry(
                option_id=k,
                question_id=v.get("question_id"),
                option_text=v.get("option_text"),
                is_correct=v.get("is_correct"),
            )
            for k, v in resource_meta["options"].items()
        }
        or None,
        problem_statements={
            str(k): ProblemStatementEntry(
                problem_statement_id=k, problem_statement=v.get("problem_statement")
            )
            for k, v in resource_meta["problem_statements"].items()
        }
        or None,
        scenarios={
            str(k): ScenarioEntry(
                scenario_id=k, name=v.get("name"), description=v.get("description")
            )
            for k, v in resource_meta["scenarios"].items()
        }
        or None,
        rubrics={
            str(k): RubricEntry(
                rubric_id=k,
                name=v.get("name"),
                description=v.get("description"),
                total_points=v.get("total_points"),
                pass_points=v.get("pass_points"),
            )
            for k, v in resource_meta["rubrics"].items()
        }
        or None,
        standard_groups={
            str(k): StandardGroupEntry(
                standard_group_id=k,
                name=v.get("name"),
                description=v.get("description"),
                points=v.get("points"),
                pass_points=v.get("pass_points"),
            )
            for k, v in resource_meta["standard_groups"].items()
        }
        or None,
        standards={
            str(k): StandardEntry(
                standard_id=k,
                standard_group_id=v.get("standard_group_id"),
                name=v.get("name"),
                description=v.get("description"),
                points=v.get("points"),
            )
            for k, v in resource_meta["standards"].items()
        }
        or None,
    )

    messages_payload: list[MessageData] = []
    is_own_attempt = attempt_item.profile_id == profiles_id
    for msg in messages_result:
        msg_feedbacks: list[MessageFeedbackEntry] = []
        for idx, strength in enumerate(strengths_by_message.get(msg.message_id, [])):
            highlights = [
                HighlightEntry(section=highlight.section, idx=highlight.idx)
                for highlight in highlights_by_strength.get(strength.strength_id, [])
            ]
            msg_feedbacks.append(
                MessageFeedbackEntry(
                    id=f"{msg.message_id}-strength-{idx}",
                    name=strength.name,
                    description=strength.description,
                    type="strength",
                    highlights=highlights if highlights else None,
                    replaces=None,
                )
            )
        for idx, improvement in enumerate(
            improvements_by_message.get(msg.message_id, [])
        ):
            replaces = [
                ReplacementEntry(
                    section=replacement.section,
                    replace=replacement.replace_text,
                    idx=replacement.idx,
                )
                for replacement in replacements_by_improvement.get(
                    improvement.improvement_id, []
                )
            ]
            msg_feedbacks.append(
                MessageFeedbackEntry(
                    id=f"{msg.message_id}-improvement-{idx}",
                    name=improvement.name,
                    description=improvement.description,
                    type="improvement",
                    highlights=None,
                    replaces=replaces if replaces else None,
                )
            )
        msg_hints_list = hints_by_message.get(msg.message_id, [])
        hints: list[HintEntry] | None = (
            [HintEntry(hint=hint.hint, idx=hint.idx) for hint in msg_hints_list]
            if msg_hints_list
            else None
        )
        msg_contents = contents_by_message.get(msg.message_id, [])
        contents: list[ContentEntry] | None = None
        if msg_contents:
            contents = []
            for content in msg_contents:
                persona_meta = (
                    resource_meta["personas"].get(content.persona_id, {})
                    if content.persona_id
                    else {}
                )
                if msg.type == "query":
                    name = "You" if is_own_attempt else profile_name
                    color = None
                    icon = "User"
                else:
                    name = persona_meta.get("name")
                    color = persona_meta.get("color")
                    icon = persona_meta.get("icon")
                contents.append(
                    ContentEntry(
                        content=content.content,
                        name=name,
                        color=color,
                        icon=icon,
                        created_at=content.created_at.isoformat()
                        if content.created_at
                        else None,
                    )
                )
        messages_payload.append(
            MessageData(
                id=msg.message_id,
                chat_id=msg.chat_id,
                type=msg.type,
                created_at=msg.created_at.isoformat() if msg.created_at else None,
                completed=msg.completed,
                contents=contents,
                feedbacks=msg_feedbacks if msg_feedbacks else None,
                hints=hints,
                parent_message_id=msg.parent_message_id,
                sibling_index=msg.sibling_index,
                sibling_count=msg.sibling_count,
            )
        )

    chats: list[ChatData] = []
    for chat_item in chats_result:
        grade = None
        if chat_item.grade_score is not None or chat_item.grade_passed is not None:
            rubric_meta = (
                resource_meta["rubrics"].get(chat_item.rubric_id, {})
                if chat_item.rubric_id
                else {}
            )
            grade = GradeData(
                score=chat_item.grade_score,
                passed=chat_item.grade_passed,
                time_taken=chat_item.grade_time_taken,
                total_points=rubric_meta.get("total_points"),
                pass_points=rubric_meta.get("pass_points"),
            )
        chat_grade_obj = grades_by_chat.get(chat_item.chat_id)
        chat_grade_id = chat_grade_obj.grade_id if chat_grade_obj else None
        feedbacks: list[FeedbackEntry] = []
        chat_feedbacks = (
            feedbacks_by_grade.get(chat_grade_id, []) if chat_grade_id else []
        )
        for feedback in chat_feedbacks:
            std_group_id = None
            if feedback.standard_id:
                std_meta = resource_meta["standards"].get(feedback.standard_id, {})
                std_group_id = std_meta.get("standard_group_id")
            feedbacks.append(
                FeedbackEntry(
                    id=feedback.feedback_id,
                    standard_id=feedback.standard_id,
                    standard_group_id=std_group_id,
                    total=feedback.total,
                    feedback=feedback.feedback,
                )
            )
        analyses_entries: list[AnalysisEntry] | None = None
        chat_analyses = (
            analyses_by_grade.get(chat_grade_id, []) if chat_grade_id else []
        )
        if chat_analyses:
            analyses_entries = [
                AnalysisEntry(content=analysis.content) for analysis in chat_analyses
            ]
        grading_state_data: GradingStateData | None = None
        if grade or chat_feedbacks:
            achieved_dict: dict[str, bool] = {}
            passed_dict: dict[str, bool] = {}
            feedback_dict: dict[str, str] = {}
            if chat_feedbacks:
                feedbacks_dicts = [
                    {"standard_id": feedback.standard_id, "total": feedback.total}
                    for feedback in chat_feedbacks
                ]
                achieved_raw = compute_achieved_standards(feedbacks_dicts)
                if achieved_raw:
                    for achieved in achieved_raw:
                        std_id = achieved.get("standard_id")
                        if std_id:
                            achieved_dict[str(std_id)] = achieved.get("achieved", False)
                passed_raw = compute_passed_standards(
                    feedbacks_dicts,
                    resource_meta["standard_groups"],
                    resource_meta["standards"],
                )
                if passed_raw:
                    for passed in passed_raw:
                        std_id = passed.get("standard_id")
                        if std_id:
                            passed_dict[str(std_id)] = passed.get("passed", False)
                for feedback in chat_feedbacks:
                    if feedback.standard_id and feedback.feedback:
                        feedback_dict[str(feedback.standard_id)] = feedback.feedback
            grading_state_data = GradingStateData(
                achieved_standards=achieved_dict if achieved_dict else None,
                passed_standards=passed_dict if passed_dict else None,
                feedback_by_standard_id=feedback_dict if feedback_dict else None,
            )
        chats.append(
            ChatData(
                id=chat_item.chat_id,
                created_at=chat_item.chat_created_at.isoformat()
                if chat_item.chat_created_at
                else None,
                completed=chat_item.completed,
                grade=grade,
                feedbacks=feedbacks,
                analyses=analyses_entries,
                show_problem_statement=chat_item.show_problem_statement,
                show_objectives=chat_item.show_objectives,
                copy_paste_allowed=chat_item.copy_paste_allowed,
                text_enabled=chat_item.text_enabled,
                audio_enabled=chat_item.audio_enabled,
                grading_state=grading_state_data,
                scenario_id=chat_item.scenario_id,
                problem_statement_id=chat_item.problem_statement_id,
                objective_ids=chat_item.objective_ids,
                persona_ids=chat_item.persona_ids,
                image_ids=chat_item.image_ids,
                video_ids=chat_item.video_ids,
                question_ids=chat_item.question_ids,
                option_ids=chat_item.option_ids,
                responses=(
                    [
                        QuizResponse(
                            question_id=response.question_id,
                            option_id=response.option_id,
                            completed=response.completed,
                            created_at=response.created_at,
                        )
                        for response in responses_by_chat.get(chat_item.chat_id, [])
                    ]
                    or None
                ),
                document_ids=chat_item.document_ids,
                rubric_id=chat_item.rubric_id,
                standard_group_ids=chat_item.standard_group_ids,
                standard_ids=chat_item.standard_ids,
            )
        )

    attempt = AttemptData(
        id=attempt_item.attempt_id,
        created_at=attempt_item.attempt_created_at.isoformat()
        if attempt_item.attempt_created_at
        else None,
        infinite_mode=attempt_item.infinite_mode,
        profile_id=attempt_item.profile_id,
        profile_name=profile_name,
        department_id=attempt_item.department_id,
        cohort_id=attempt_item.cohort_id if not practice else None,
        is_archived=False if practice else None,
    )
    simulation = SimulationData(
        id=attempt_item.simulation_id,
        name=simulation_name,
        description=None,
        time_limit=time_limit_seconds if time_limit_seconds > 0 else None,
        hints_enabled=first_chat_item.hints_enabled if first_chat_item else None,
        objectives_enabled=first_chat_item.show_objectives if first_chat_item else None,
        image_input_active=first_chat_item.show_images if first_chat_item else None,
        copy_paste_allowed=first_chat_item.copy_paste_allowed
        if first_chat_item
        else None,
        practice_simulation=practice,
        rubric_id=first_chat_item.rubric_id if first_chat_item else None,
    )

    compute_chat_position_and_current(chats)
    aggregates = compute_attempt_aggregates(chats)
    total_chats = aggregates["total_chats"]
    completed_chats = aggregates["completed_chats"]
    total_score = aggregates["total_score"]
    all_passed = aggregates["all_passed"]
    elapsed_seconds = aggregates["elapsed_seconds"]
    timer = _format_timer(
        elapsed=elapsed_seconds,
        limit_seconds=time_limit_seconds if time_limit_seconds > 0 else None,
        infinite_mode=attempt_item.infinite_mode or False,
        negative=allows_negative_time,
    )
    total_possible = compute_total_possible_points(chats)
    percentage = compute_percentage(total_score, total_possible)
    aggregated_results = AggregatedResults(
        total_score=total_score,
        total_possible_points=float(total_possible),
        percentage=percentage,
        passed=all_passed,
        chats_completed=completed_chats,
        total_chats=total_chats,
    )
    current_chat_index = compute_current_chat_index(chats)
    expected_chat_count = total_chats
    is_active = not timer.exceeded if timer else True

    all_standard_group_ids = [
        standard_group_id
        for chat in chats_result
        for standard_group_id in (chat.standard_group_ids or [])
    ]
    all_standard_ids = [
        standard_id
        for chat in chats_result
        for standard_id in (chat.standard_ids or [])
    ]

    rubric_structure: RubricStructureData | None = None
    if all_standard_group_ids or all_standard_ids:
        standard_groups_dict: dict[str, list[str]] = {}
        for std_id in set(all_standard_ids):
            std_meta = resource_meta["standards"].get(std_id, {})
            sg_id = std_meta.get("standard_group_id")
            if sg_id:
                sg_id_str = str(sg_id)
                standard_groups_dict.setdefault(sg_id_str, []).append(str(std_id))
        standard_groups_mapping_dict: dict[str, StandardGroupMeta] = {}
        for sg_id in set(all_standard_group_ids):
            sg_meta = resource_meta["standard_groups"].get(sg_id, {})
            standard_groups_mapping_dict[str(sg_id)] = StandardGroupMeta(
                name=sg_meta.get("name"),
                description=sg_meta.get("description"),
                points=sg_meta.get("points"),
                pass_points=sg_meta.get("pass_points"),
            )
        standards_mapping_dict: dict[str, StandardMeta] = {}
        for std_id in set(all_standard_ids):
            std_meta = resource_meta["standards"].get(std_id, {})
            standards_mapping_dict[str(std_id)] = StandardMeta(
                name=std_meta.get("name"),
                description=std_meta.get("description"),
                points=std_meta.get("points"),
            )
        rubric_structure = RubricStructureData(
            standard_groups=standard_groups_dict if standard_groups_dict else None,
            standard_groups_mapping=standard_groups_mapping_dict
            if standard_groups_mapping_dict
            else None,
            standards_mapping=standards_mapping_dict
            if standards_mapping_dict
            else None,
        )

    all_chats_completed = all(chat.completed for chat in chats) if chats else False
    show_results = all_chats_completed
    should_show_controls = is_active and not all_chats_completed
    current_chat_id: str | None = None
    has_messages = False
    if should_show_controls and chats and current_chat_index is not None:
        current_chat = chats[current_chat_index]
        current_chat_id = str(current_chat.id)
        has_messages = any(
            message.chat_id == current_chat.id for message in messages_result
        )

    has_remaining = (
        expected_chat_count is not None
        and expected_chat_count > 0
        and completed_chats < expected_chat_count
    )
    is_lobby = (
        all_chats_completed
        and bool(has_remaining)
        and is_active
        and bool(chat_entry_id)
    )

    continuation_options = None
    previous_chats = ctx.entries.get("previous_chats", [])
    if is_lobby and not practice and previous_chats:
        try:
            scenario_names: dict[str, str] = {}
            for sid, meta in resource_meta.get("scenarios", {}).items():
                name = meta.get("name") if isinstance(meta, dict) else None
                if name:
                    scenario_names[str(sid)] = name
            continuation_options = compute_continuation_options(
                current_chats=chats_result,
                previous_chats=previous_chats,
                scenario_names=scenario_names,
            )
        except Exception:
            continuation_options = None

    return AttemptInternalData(
        actor_name=profile_name,
        attempt_exists=True,
        access_denied=False,
        is_own_attempt=is_own_attempt,
        practice=practice,
        profiles_id=profiles_id,
        profile_name=profile_name,
        simulation_name=simulation_name,
        training_id=training_id,
        chat_entry_id=chat_entry_id,
        group_id=group_id,
        agent_ids={},
        attempt_item=attempt_item,
        chats_result=chats_result,
        messages_result=messages_result,
        resource_meta=resource_meta,
        resources_payload=resources_payload,
        chats=chats,
        messages=messages_payload,
        attempt=attempt,
        simulation=simulation,
        timer=timer,
        aggregated_results=aggregated_results,
        current_chat_index=current_chat_index,
        expected_chat_count=expected_chat_count,
        is_active=is_active,
        is_lobby=is_lobby,
        show_results=show_results,
        should_show_controls=should_show_controls,
        current_chat_id=current_chat_id,
        has_messages=has_messages,
        rubric_structure=rubric_structure,
        continuation_options=continuation_options,
    )


async def get_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    attempt_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str,
) -> tuple[GetAttemptDetailResponse, bool]:
    """Resolve the canonical attempt detail response with shared caching."""
    tags = ["attempt"]
    body_dict = {"attempt_id": str(attempt_id)}
    cache_key_val = cache_key(cache_key_path, body_dict)

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=redis)
        if cached:
            return GetAttemptDetailResponse.model_validate(cached["data"]), True

    data = await get_attempt_internal(
        pool,
        redis,
        profile_id=profile_id,
        attempt_id=attempt_id,
        bypass_cache=bypass_cache,
    )

    if not data.attempt_exists or data.access_denied:
        return (
            GetAttemptDetailResponse(
                attempt_exists=data.attempt_exists,
                access_denied=data.access_denied,
                actor_name=data.actor_name,
            ),
            False,
        )

    api_response = GetAttemptDetailResponse(
        actor_name=data.actor_name,
        attempt_exists=True,
        access_denied=False,
        attempt=data.attempt,
        simulation=data.simulation,
        timer=data.timer,
        aggregated_results=data.aggregated_results,
        current_chat_index=data.current_chat_index,
        expected_chat_count=data.expected_chat_count,
        is_active=data.is_active,
        is_lobby=data.is_lobby,
        show_results=data.show_results,
        should_show_controls=data.should_show_controls,
        current_chat_id=data.current_chat_id,
        has_messages=data.has_messages,
        is_own_attempt=data.is_own_attempt,
        available_continuation_options=data.continuation_options,
        rubric_structure=data.rubric_structure,
        training_id=data.training_id,
        chat_entry_id=data.chat_entry_id,
        resources=data.resources_payload,
        entries=AttemptEntries(
            attempt=[data.attempt_item] if data.attempt_item else None,
            attempt_chat=data.chats,
            attempt_message=data.messages,
        ),
    )

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=redis,
    )
    return api_response, False
