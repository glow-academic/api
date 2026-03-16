"""Resolve attempt context — black-box tools only.

Attempt detail is a single-attempt view with chats, messages, and nested entries.
Uses attempt_mv, attempt_chat_mv, attempt_message_mv, and 10 child entry MVs.
Also fetches entry MVs for files/images/videos and previous attempts for continuation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_analysis.search import search_attempt_analyses
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_content.search import search_attempt_contents
from app.tools.entries.attempt_feedback.search import (
    search_attempt_feedback_entries,
)
from app.tools.entries.attempt_grade.search import search_attempt_grades
from app.tools.entries.attempt_highlight.search import (
    search_attempt_highlights,
)
from app.tools.entries.attempt_hint.search import search_attempt_hints
from app.tools.entries.attempt_improvement.search import (
    search_attempt_improvements,
)
from app.tools.entries.attempt_message.search import search_attempt_messages
from app.tools.entries.attempt_replacement.search import (
    search_attempt_replacements,
)
from app.tools.entries.attempt_responses.search import (
    search_attempt_responses,
)
from app.tools.entries.attempt_strength.search import search_attempt_strengths
from app.tools.entries.files.search import search_files
from app.tools.entries.images.search import search_images
from app.tools.entries.videos.search import search_videos
from app.tools.resources.documents.get import get_documents
from app.tools.resources.images.get import get_images
from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.options.get import get_options
from app.tools.resources.personas.get import get_personas
from app.tools.resources.problem_statements.get import get_problem_statements
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.questions.get import get_questions
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.get import get_standards
from app.tools.resources.videos.get import get_videos


async def resolve_attempt_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    attempt_id: UUID,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve attempt context for get.py.

    Entries:
      - attempts, chats, messages (Phase 1)
      - contents, strengths, improvements, hints, grades, responses (Phase 2)
      - highlights, replacements, feedbacks, analyses (Phase 3)
      - files, images, videos (Phase 5 — entry MVs for upload enrichment)
      - previous_attempts, previous_chats (Phase 1B — for continuation options)

    Resources:
      - scenarios, personas, images, videos, documents, objectives,
        questions, options, problem_statements, rubrics,
        standard_groups, standards, simulations, profiles
    """

    # ── Phase 1: Parallel fetch core entries ────────────────────────
    async def _fetch_attempts() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempts(
                c, attempt_ids=[attempt_id], limit=1
            )
            return items

    async def _fetch_chats() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_chats(
                c, attempt_ids=[attempt_id], sort_order="asc", limit=100000
            )
            return items

    async def _fetch_messages() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_messages(
                c, attempt_ids=[attempt_id], limit=100000
            )
            return items

    attempts, chats, messages = await asyncio.gather(
        _fetch_attempts(),
        _fetch_chats(),
        _fetch_messages(),
    )

    if not attempts:
        return _empty_context()

    attempt = attempts[0]

    # ── Phase 1B: Previous attempts + chats (for continuation) ───
    async def _fetch_previous_attempts() -> list:
        if not attempt.profile_id or attempt.practice:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_attempts(
                c,
                profile_ids=[attempt.profile_id],
                simulation_ids=(
                    [attempt.simulation_id] if attempt.simulation_id else None
                ),
                practice=False,
                limit=100000,
            )
            return items

    previous_attempts = await _fetch_previous_attempts()
    other_attempt_ids = [
        a.attempt_id for a in previous_attempts if a.attempt_id != attempt_id
    ]

    async def _fetch_previous_chats() -> list:
        if not other_attempt_ids:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_chats(
                c, attempt_ids=other_attempt_ids, sort_order="asc", limit=100000
            )
            return items

    previous_chats = await _fetch_previous_chats()

    # ── Phase 2: Child entries by message_ids/chat_ids ──────────────
    message_ids = [m.message_id for m in messages]
    chat_ids = [ch.chat_id for ch in chats]

    async def _fetch_contents() -> list:
        if not message_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_contents(
                c, message_ids=message_ids, limit=100000
            )

    async def _fetch_strengths() -> list:
        if not message_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_strengths(
                c, message_ids=message_ids, limit=100000
            )

    async def _fetch_improvements() -> list:
        if not message_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_improvements(
                c, message_ids=message_ids, limit=100000
            )

    async def _fetch_hints() -> list:
        if not message_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_hints(c, message_ids=message_ids, limit=100000)

    async def _fetch_grades() -> list:
        if not chat_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_grades(c, chat_ids=chat_ids, limit=100000)

    async def _fetch_responses() -> list:
        if not chat_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_responses(c, chat_ids=chat_ids, limit=100000)

    (
        contents,
        strengths,
        improvements,
        hints,
        grades,
        responses,
    ) = await asyncio.gather(
        _fetch_contents(),
        _fetch_strengths(),
        _fetch_improvements(),
        _fetch_hints(),
        _fetch_grades(),
        _fetch_responses(),
    )

    # ── Phase 3: Grandchild entries ─────────────────────────────────
    strength_ids = [s.strength_id for s in strengths]
    improvement_ids = [i.improvement_id for i in improvements]
    grade_ids = [g.grade_id for g in grades]

    async def _fetch_highlights() -> list:
        if not strength_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_highlights(
                c, strength_ids=strength_ids, limit=100000
            )

    async def _fetch_replacements() -> list:
        if not improvement_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_replacements(
                c, improvement_ids=improvement_ids, limit=100000
            )

    async def _fetch_feedbacks() -> list:
        if not grade_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_feedback_entries(
                c, grade_ids=grade_ids, limit=100000
            )

    async def _fetch_analyses() -> list:
        if not grade_ids:
            return []
        async with pool.acquire() as c:
            return await search_attempt_analyses(c, grade_ids=grade_ids, limit=100000)

    highlights, replacements, feedbacks, analyses = await asyncio.gather(
        _fetch_highlights(),
        _fetch_replacements(),
        _fetch_feedbacks(),
        _fetch_analyses(),
    )

    # ── Phase 4: Collect resource IDs ───────────────────────────────
    scenario_ids_set: set[UUID] = set()
    persona_ids_set: set[UUID] = set()
    image_ids_set: set[UUID] = set()
    video_ids_set: set[UUID] = set()
    document_ids_set: set[UUID] = set()
    objective_ids_set: set[UUID] = set()
    question_ids_set: set[UUID] = set()
    option_ids_set: set[UUID] = set()
    problem_statement_ids_set: set[UUID] = set()
    rubric_ids_set: set[UUID] = set()
    standard_group_ids_set: set[UUID] = set()
    standard_ids_set: set[UUID] = set()
    simulation_ids_set: set[UUID] = set()
    profile_ids_set: set[UUID] = set()

    # From attempt
    if attempt.simulation_id:
        simulation_ids_set.add(attempt.simulation_id)
    if attempt.profile_id:
        profile_ids_set.add(attempt.profile_id)

    # From chats
    for ch in chats:
        if ch.scenario_id:
            scenario_ids_set.add(ch.scenario_id)
        if ch.rubric_id:
            rubric_ids_set.add(ch.rubric_id)
        if ch.problem_statement_id:
            problem_statement_ids_set.add(ch.problem_statement_id)
        for pid in ch.persona_ids or []:
            persona_ids_set.add(pid)
        for iid in ch.image_ids or []:
            image_ids_set.add(iid)
        for vid in ch.video_ids or []:
            video_ids_set.add(vid)
        for did in ch.document_ids or []:
            document_ids_set.add(did)
        for oid in ch.objective_ids or []:
            objective_ids_set.add(oid)
        for qid in ch.question_ids or []:
            question_ids_set.add(qid)
        for optid in ch.option_ids or []:
            option_ids_set.add(optid)
        for sgid in ch.standard_group_ids or []:
            standard_group_ids_set.add(sgid)
        for sid in ch.standard_ids or []:
            standard_ids_set.add(sid)

    # ── Phase 5: Parallel resource hydration + entry MV fetches ───
    async def _get(getter: Callable, ids_set: set[UUID]) -> list:
        if not ids_set:
            return []
        async with pool.acquire() as c:
            return await getter(c, list(ids_set), redis, bypass_cache=bypass_cache)

    # Entry MV fetches for file enrichment (like scenario pattern)
    async def _fetch_file_entries() -> list:
        # Documents have file_id — collect from document resources after hydration
        # We need document resources first, so we'll fetch file entries after
        return []

    async def _fetch_image_entries() -> list:
        if not image_ids_set:
            return []
        async with pool.acquire() as c:
            return await search_images(c, images_ids=list(image_ids_set), limit=200)

    async def _fetch_video_entries() -> list:
        if not video_ids_set:
            return []
        async with pool.acquire() as c:
            return await search_videos(c, videos_ids=list(video_ids_set), limit=200)

    (
        scenarios_res,
        personas_res,
        images_res,
        videos_res,
        documents_res,
        objectives_res,
        questions_res,
        options_res,
        problem_statements_res,
        rubrics_res,
        standard_groups_res,
        standards_res,
        simulations_res,
        profiles_res,
        image_entries,
        video_entries,
    ) = await asyncio.gather(
        _get(get_scenarios, scenario_ids_set),
        _get(get_personas, persona_ids_set),
        _get(get_images, image_ids_set),
        _get(get_videos, video_ids_set),
        _get(get_documents, document_ids_set),
        _get(get_objectives, objective_ids_set),
        _get(get_questions, question_ids_set),
        _get(get_options, option_ids_set),
        _get(get_problem_statements, problem_statement_ids_set),
        _get(get_rubrics, rubric_ids_set),
        _get(get_standard_groups, standard_group_ids_set),
        _get(get_standards, standard_ids_set),
        _get(get_simulations, simulation_ids_set),
        _get(get_profiles, profile_ids_set),
        _fetch_image_entries(),
        _fetch_video_entries(),
    )

    # Phase 5B: File entries need document file_ids (from hydrated documents)
    all_doc_file_ids = [d.file_id for d in documents_res if d.file_id]

    async def _fetch_file_entries_real() -> list:
        if not all_doc_file_ids:
            return []
        async with pool.acquire() as c:
            return await search_files(c, files_ids=all_doc_file_ids, limit=200)

    file_entries = await _fetch_file_entries_real()

    # ── Phase 6: Return ArtifactContext ─────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "attempts": attempts,
            "chats": chats,
            "messages": messages,
            "contents": contents,
            "strengths": strengths,
            "improvements": improvements,
            "hints": hints,
            "grades": grades,
            "responses": responses,
            "highlights": highlights,
            "replacements": replacements,
            "feedbacks": feedbacks,
            "analyses": analyses,
            "files": file_entries,
            "images": image_entries,
            "videos": video_entries,
            "previous_attempts": previous_attempts,
            "previous_chats": previous_chats,
        },
        resources={
            "scenarios": ResourcePair(selected=scenarios_res, suggestions=[]),
            "personas": ResourcePair(selected=personas_res, suggestions=[]),
            "images": ResourcePair(selected=images_res, suggestions=[]),
            "videos": ResourcePair(selected=videos_res, suggestions=[]),
            "documents": ResourcePair(selected=documents_res, suggestions=[]),
            "objectives": ResourcePair(selected=objectives_res, suggestions=[]),
            "questions": ResourcePair(selected=questions_res, suggestions=[]),
            "options": ResourcePair(selected=options_res, suggestions=[]),
            "problem_statements": ResourcePair(
                selected=problem_statements_res, suggestions=[]
            ),
            "rubrics": ResourcePair(selected=rubrics_res, suggestions=[]),
            "standard_groups": ResourcePair(
                selected=standard_groups_res, suggestions=[]
            ),
            "standards": ResourcePair(selected=standards_res, suggestions=[]),
            "simulations": ResourcePair(selected=simulations_res, suggestions=[]),
            "profiles": ResourcePair(selected=profiles_res, suggestions=[]),
        },
    )


def _empty_context() -> ArtifactContext:
    """Return an empty ArtifactContext when attempt not found."""
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={},
        resources={},
    )
