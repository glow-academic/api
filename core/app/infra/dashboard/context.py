"""Resolve dashboard context — multi-phase data fetch + resource hydration.

Dashboard is a metrics endpoint with no artifact table and no drafts.
Two context resolvers:
  - resolve_dashboard_context: metrics bundle (header, primary, secondary, footer)
  - resolve_dashboard_search_context: history table (attempt list, paginated)

All data fetched via black-box entry search tools + resource get tools.
Aggregation and stitching done in Python.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# ---------------------------------------------------------------------------
# Dashboard context types
# ---------------------------------------------------------------------------


class RubricScoreItem:
    """Single (chat, standard_group) rubric score row."""

    __slots__ = (
        "chat_id",
        "standard_group_id",
        "rubric_id",
        "score_percent",
        "simulation_id",
        "profile_id",
        "cohort_id",
        "department_id",
        "attempt_date",
        "attempt_type",
        "is_archived",
    )

    def __init__(
        self,
        chat_id: UUID,
        standard_group_id: UUID,
        rubric_id: UUID | None = None,
        score_percent: float | None = None,
        simulation_id: UUID | None = None,
        profile_id: UUID | None = None,
        cohort_id: UUID | None = None,
        department_id: UUID | None = None,
        attempt_date: date | None = None,
        attempt_type: str | None = None,
        is_archived: bool = False,
    ) -> None:
        self.chat_id = chat_id
        self.standard_group_id = standard_group_id
        self.rubric_id = rubric_id
        self.score_percent = score_percent
        self.simulation_id = simulation_id
        self.profile_id = profile_id
        self.cohort_id = cohort_id
        self.department_id = department_id
        self.attempt_date = attempt_date
        self.attempt_type = attempt_type
        self.is_archived = is_archived


class RubricScoresResponse:
    """Response from rubric scores query."""

    __slots__ = ("items", "total_count")

    def __init__(
        self,
        items: list[RubricScoreItem] | None = None,
        total_count: int = 0,
    ) -> None:
        self.items = items or []
        self.total_count = total_count


class MessageStats:
    """Message statistics for a single chat."""

    __slots__ = ("chat_id", "num_messages_total", "avg_response_sec")

    def __init__(
        self,
        chat_id: UUID,
        num_messages_total: int = 0,
        avg_response_sec: float | None = None,
    ) -> None:
        self.chat_id = chat_id
        self.num_messages_total = num_messages_total
        self.avg_response_sec = avg_response_sec


# Entry search tools
# Settings
from app.infra.identity.settings import resolve_thresholds
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_chat.types import (
    ChatItem,
    GetAttemptChatResponse,
)
from app.tools.entries.attempt_feedback.search import (
    search_attempt_feedback_entries,
)
from app.tools.entries.attempt_grade.search import search_attempt_grades
from app.tools.entries.attempt_message.search import search_attempt_messages
from app.tools.entries.attempt_message_completion.search import (
    search_attempt_message_completions,
)

# Resource get tools
from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.documents.get import get_documents
from app.tools.resources.fields.get import get_fields
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.personas.get import get_personas
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.get import get_standards


def _to_chat_item(r: GetAttemptChatResponse) -> ChatItem:
    """Convert a GetAttemptChatResponse (raw MV row) to ChatItem."""
    return ChatItem(
        chat_id=r.chat_id,
        attempt_id=r.attempt_id,
        chat_entry_id=r.chat_entry_id,
        group_id=r.group_id,
        attempt_chat_id=r.chat_entry_id,  # attempt_chat_id = chat_entry_id
        profile_id=r.profile_id,
        cohort_id=r.cohort_id,
        department_id=r.department_id,
        simulation_id=r.simulation_id,
        scenario_id=r.scenario_id,
        persona_ids=r.persona_ids,
        rubric_id=r.rubric_id,
        grade_score=r.grade_score,
        grade_total_points=r.grade_total_points,
        grade_pass_points=r.grade_pass_points,
        grade_passed=r.grade_passed,
        grade_time_taken=r.grade_time_taken,
        completed=r.completed or False,
        attempt_number=r.attempt_number or 0,
        chat_created_at=r.chat_created_at,
        attempt_date=r.attempt_date,
        attempt_type=r.attempt_type,
        is_archived=r.is_archived or False,
        infinite_mode=r.infinite_mode or False,
        document_ids=r.document_ids or [],
    )


# ---------------------------------------------------------------------------
# Black-box entry tool aggregations (replacing compiled SQL)
# ---------------------------------------------------------------------------


async def _compute_message_stats(
    pool: asyncpg.Pool,
    chat_ids: list[UUID],
) -> dict[UUID, MessageStats]:
    """Compute message stats using search_attempt_messages + search_attempt_message_completions.

    - num_messages_total: count of messages per chat
    - avg_response_sec: avg(completion.created_at - message.created_at) for response messages
    """
    if not chat_ids:
        return {}

    # Step 1: Fetch all messages for these chats
    async with pool.acquire() as c:
        messages, _total_count = await search_attempt_messages(
            c, chat_ids=chat_ids, limit=500000
        )

    if not messages:
        return {}

    # Step 2: Count messages per chat, collect response message_ids + created_at
    msg_count: dict[UUID, int] = defaultdict(int)
    response_msg_created: dict[UUID, datetime] = {}  # message_id → created_at
    response_msg_chat: dict[UUID, UUID] = {}  # message_id → chat_id

    for msg in messages:
        if msg.chat_id:
            msg_count[msg.chat_id] += 1
        if msg.type == "response" and msg.chat_id and msg.created_at:
            response_msg_created[msg.message_id] = msg.created_at
            response_msg_chat[msg.message_id] = msg.chat_id

    # Step 3: Fetch completions for response messages to get completion timestamps
    response_times: dict[UUID, list[float]] = defaultdict(list)  # chat_id → [seconds]
    if response_msg_created:
        async with pool.acquire() as c:
            completions = await search_attempt_message_completions(
                c,
                attempt_message_ids=list(response_msg_created.keys()),
                limit=500000,
            )

        # Use the latest completion per message
        latest_completion: dict[UUID, datetime] = {}
        for comp in completions:
            if comp.attempt_message_id and comp.created_at:
                existing = latest_completion.get(comp.attempt_message_id)
                if existing is None or comp.created_at > existing:
                    latest_completion[comp.attempt_message_id] = comp.created_at

        for msg_id, comp_time in latest_completion.items():
            msg_time = response_msg_created.get(msg_id)
            chat_id = response_msg_chat.get(msg_id)
            if msg_time and chat_id:
                delta_sec = (comp_time - msg_time).total_seconds()
                if delta_sec >= 0:
                    response_times[chat_id].append(delta_sec)

    # Step 4: Build stats map
    stats_map: dict[UUID, MessageStats] = {}
    for cid in msg_count:
        times = response_times.get(cid)
        avg_sec = round(sum(times) / len(times), 2) if times else None
        stats_map[cid] = MessageStats(
            chat_id=cid,
            num_messages_total=msg_count[cid],
            avg_response_sec=avg_sec,
        )

    return stats_map


async def _compute_rubric_scores(
    pool: asyncpg.Pool,
    redis: Redis,
    chat_items: list[ChatItem],
    *,
    bypass_cache: bool = False,
) -> RubricScoresResponse:
    """Compute rubric scores using black-box entry tools + Python stitching.

    Flow:
      1. search_attempt_grades(chat_ids) → latest grade per chat (Python dedup)
      2. search_attempt_feedback_entries(grade_ids) → feedback scores
      3. get_standards(standard_ids) → standard_group_id per standard
      4. get_standard_groups(sg_ids) → points per standard_group
      5. get_rubrics(rubric_ids) → which standard_groups belong to each rubric
      6. Python: score_percent = 100 * SUM(feedback.total) / standard_group.points
         per (chat_id, standard_group_id)
    """
    if not chat_items:
        return RubricScoresResponse(items=[], total_count=0)

    chat_ids = [item.chat_id for item in chat_items]

    # Step 1: Fetch all grades for these chats, dedup to latest per chat
    async with pool.acquire() as c:
        all_grades = await search_attempt_grades(c, chat_ids=chat_ids, limit=500000)

    if not all_grades:
        return RubricScoresResponse(items=[], total_count=0)

    # Dedup: latest grade per chat (already ordered by created_at DESC from search)
    latest_grade: dict[
        UUID, tuple[UUID, UUID | None]
    ] = {}  # chat_id → (grade_id, rubric_id)
    for g in all_grades:
        if g.chat_id not in latest_grade:
            latest_grade[g.chat_id] = (g.grade_id, g.rubric_id)

    grade_ids = [gid for gid, _ in latest_grade.values()]
    grade_to_chat: dict[UUID, UUID] = {
        gid: cid for cid, (gid, _) in latest_grade.items()
    }
    chat_to_rubric: dict[UUID, UUID | None] = {
        cid: rid for cid, (_, rid) in latest_grade.items()
    }

    # Step 2: Fetch feedback entries for latest grades
    async with pool.acquire() as c:
        feedbacks = await search_attempt_feedback_entries(
            c, grade_ids=grade_ids, limit=500000
        )

    if not feedbacks:
        return RubricScoresResponse(items=[], total_count=0)

    # Step 3: Collect unique standard_ids from feedback, fetch standards for mapping
    standard_ids_set: set[UUID] = set()
    for fb in feedbacks:
        if fb.standard_id:
            standard_ids_set.add(fb.standard_id)

    async with pool.acquire() as c:
        standards_list = await get_standards(
            c, list(standard_ids_set), redis, bypass_cache=bypass_cache
        )

    # Build standard_id → standard_group_id map
    std_to_sg: dict[UUID, UUID] = {s.id: s.standard_group_id for s in standards_list}

    # Step 4: Fetch standard_groups for points
    sg_ids_set: set[UUID] = set(std_to_sg.values())
    async with pool.acquire() as c:
        sg_list = await get_standard_groups(
            c, list(sg_ids_set), redis, bypass_cache=bypass_cache
        )

    sg_points: dict[UUID, int] = {sg.id: sg.points for sg in sg_list}

    # Step 5: Fetch rubrics to know which standard_groups belong to each rubric
    rubric_ids_set: set[UUID] = {rid for rid in chat_to_rubric.values() if rid}
    async with pool.acquire() as c:
        rubrics_list = await get_rubrics(
            c, list(rubric_ids_set), redis, bypass_cache=bypass_cache
        )

    # rubric_id → set of standard_group_ids (from rubric resource)
    rubric_sg_map: dict[UUID, set[UUID]] = {}
    for rubric in rubrics_list:
        rid = getattr(rubric, "rubric_id", None)
        sg_ids = getattr(rubric, "standard_group_ids", None) or []
        if rid:
            rubric_sg_map[rid] = {sgid for sgid in sg_ids if sgid}

    # Step 6: Aggregate feedback totals per (chat_id, standard_group_id)
    score_agg: dict[tuple[UUID, UUID], float] = defaultdict(float)

    for fb in feedbacks:
        chat_id = grade_to_chat.get(fb.grade_id)
        if not chat_id or not fb.standard_id:
            continue
        sg_id = std_to_sg.get(fb.standard_id)
        if not sg_id:
            continue
        # Only include if this standard_group belongs to the chat's rubric
        rubric_id = chat_to_rubric.get(chat_id)
        if rubric_id:
            valid_sgs = rubric_sg_map.get(rubric_id, set())
            if sg_id not in valid_sgs:
                continue
        score_agg[(chat_id, sg_id)] += fb.total

    # Step 7: Build RubricScoreItems
    chat_meta: dict[UUID, ChatItem] = {item.chat_id: item for item in chat_items}

    items: list[RubricScoreItem] = []
    for (chat_id, sg_id), total in score_agg.items():
        points = sg_points.get(sg_id, 0)
        score_percent = round(100.0 * total / points, 2) if points > 0 else None
        meta = chat_meta.get(chat_id)
        rubric_id = chat_to_rubric.get(chat_id)

        items.append(
            RubricScoreItem(
                chat_id=chat_id,
                standard_group_id=sg_id,
                rubric_id=rubric_id,
                score_percent=score_percent,
                simulation_id=meta.simulation_id if meta else None,
                profile_id=meta.profile_id if meta else None,
                cohort_id=meta.cohort_id if meta else None,
                department_id=meta.department_id if meta else None,
                attempt_date=meta.attempt_date if meta else None,
                attempt_type=meta.attempt_type if meta else None,
                is_archived=meta.is_archived if meta else False,
            )
        )

    # Sort by attempt_date DESC, chat_id DESC (matching original SQL)
    items.sort(
        key=lambda x: (x.attempt_date or date.min, x.chat_id),
        reverse=True,
    )

    return RubricScoresResponse(items=items, total_count=len(items))


async def resolve_dashboard_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    target_profile_id: UUID | None = None,
    actor_profile_id: UUID | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    attempt_type: str | None = None,
    is_archived: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve dashboard context for metrics bundle.

    Entries:
      - chat_items: ChatItem list (enriched with message stats, document_ids from MV)
      - rubric_items: RubricScoreItem list
      - thresholds: [Thresholds] (single-item list)
      - scenario_counts: list of {simulation_id, scenario_count} dicts (from simulations resource)
      - cohort_names: list of {id, name} dicts (from cohorts resource)

    Resources:
      - simulations, scenarios, personas, profiles, rubrics, standard_groups,
        documents, parameter_fields, parameters, fields, cohorts
    """

    # ── Phase 1: Fetch chats + thresholds in parallel ────────────────
    async def _fetch_chats() -> list[ChatItem]:
        async with pool.acquire() as c:
            raw, _total_count = await search_attempt_chats(
                c,
                profile_ids=[target_profile_id] if target_profile_id else None,
                cohort_ids=cohort_ids,
                department_ids=list(department_ids) if department_ids else None,
                simulation_ids=simulation_ids,
                attempt_type=attempt_type,
                is_archived=is_archived,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )
        return [_to_chat_item(r) for r in raw]

    async def _fetch_thresholds() -> dict[str, int | float]:
        profile_for_settings = actor_profile_id or target_profile_id
        return await resolve_thresholds(
            pool, redis, profile_for_settings, bypass_cache=bypass_cache
        )

    chat_items, thresholds = await asyncio.gather(
        _fetch_chats(),
        _fetch_thresholds(),
    )

    # ── Phase 2: Collect IDs from chat_items ─────────────────────────
    simulation_ids_set: set[UUID] = set()
    persona_ids_set: set[UUID] = set()
    cohort_ids_set: set[UUID] = set()
    scenario_ids_set: set[UUID] = set()
    document_ids_set: set[UUID] = set()
    chat_ids: list[UUID] = []

    for item in chat_items:
        chat_ids.append(item.chat_id)
        if item.simulation_id:
            simulation_ids_set.add(item.simulation_id)
        if item.persona_ids:
            persona_ids_set.update(item.persona_ids)
        if item.cohort_id:
            cohort_ids_set.add(item.cohort_id)
        if item.scenario_id:
            scenario_ids_set.add(item.scenario_id)
        for doc_id in item.document_ids or []:
            document_ids_set.add(doc_id)

    # ── Phase 3: Parallel — rubric scores, message stats, resources ──
    async def _fetch_rubric_scores() -> RubricScoresResponse:
        return await _compute_rubric_scores(
            pool, redis, chat_items, bypass_cache=bypass_cache
        )

    async def _get_simulations() -> list:
        async with pool.acquire() as c:
            return await get_simulations(
                c, list(simulation_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_personas() -> list:
        async with pool.acquire() as c:
            return await get_personas(
                c, list(persona_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_scenarios() -> list:
        async with pool.acquire() as c:
            return await get_scenarios(
                c, list(scenario_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_rubric_resources() -> tuple:
        async with pool.acquire() as c:
            rubrics = await get_rubrics(
                c,
                list({item.rubric_id for item in chat_items if item.rubric_id}),
                redis,
                bypass_cache=bypass_cache,
            )
        all_sg_ids: list[UUID] = []
        for rubric in rubrics:
            for sg_id in getattr(rubric, "standard_group_ids", None) or []:
                if sg_id and sg_id not in all_sg_ids:
                    all_sg_ids.append(sg_id)
        standard_groups = []
        if all_sg_ids:
            async with pool.acquire() as c:
                standard_groups = await get_standard_groups(
                    c, all_sg_ids, redis, bypass_cache=bypass_cache
                )
        return rubrics, standard_groups

    async def _get_message_stats() -> dict[UUID, MessageStats]:
        return await _compute_message_stats(pool, chat_ids)

    async def _get_cohorts() -> list:
        if not cohort_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_cohorts(
                c, list(cohort_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_documents() -> list:
        if not document_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_documents(
                c, list(document_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_profiles() -> list:
        if not target_profile_id:
            return []
        async with pool.acquire() as c:
            return await get_profiles(
                c, [target_profile_id], redis, bypass_cache=bypass_cache
            )

    (
        rubric_scores_result,
        simulations,
        personas,
        scenarios_list,
        (rubrics, standard_groups),
        message_stats,
        cohorts,
        documents,
        target_profiles,
    ) = await asyncio.gather(
        _fetch_rubric_scores(),
        _get_simulations(),
        _get_personas(),
        _get_scenarios(),
        _get_rubric_resources(),
        _get_message_stats(),
        _get_cohorts(),
        _get_documents(),
        _get_profiles(),
    )
    rubric_items = rubric_scores_result.items

    # ── Phase 4: Enrich chat items with message stats ────────────────
    for item in chat_items:
        stats = message_stats.get(item.chat_id)
        if stats:
            item.num_messages_total = stats.num_messages_total
            item.avg_response_sec = stats.avg_response_sec

    # ── Phase 5: Build scenario_counts + cohort_names from resources ──
    # scenario_counts: derived from simulations resource (len(scenario_ids))
    scenario_count_rows = [
        {"simulation_id": s.id, "scenario_count": len(s.scenario_ids or [])}
        for s in simulations
        if s.id
    ]

    # cohort_names: derived from cohorts resource
    cohort_name_rows = [
        {"id": c.id, "name": c.name} for c in cohorts if c.id and c.name
    ]

    # ── Phase 6: Sequential resource hydration (depends on Phase 3) ──
    # Parameter fields from scenarios + personas + documents
    all_pf_ids: set[UUID] = set()
    for s in scenarios_list:
        for pfid in getattr(s, "parameter_field_ids", None) or []:
            all_pf_ids.add(pfid)
    for p in personas:
        for pfid in getattr(p, "parameter_field_ids", None) or []:
            all_pf_ids.add(pfid)
    for d in documents:
        for pfid in getattr(d, "parameter_field_ids", None) or []:
            all_pf_ids.add(pfid)

    async with pool.acquire() as c:
        parameter_fields = await get_parameter_fields(
            c, list(all_pf_ids), redis, bypass_cache=bypass_cache
        )

    # Parameters + fields from parameter_fields
    parameter_ids_set: set[UUID] = set()
    field_ids_set: set[UUID] = set()
    for pf in parameter_fields:
        if pf.parameter_id:
            parameter_ids_set.add(pf.parameter_id)
        if pf.field_id:
            field_ids_set.add(pf.field_id)

    async def _get_parameters() -> list:
        async with pool.acquire() as c:
            return await get_parameters(
                c, list(parameter_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_fields() -> list:
        async with pool.acquire() as c:
            return await get_fields(
                c, list(field_ids_set), redis, bypass_cache=bypass_cache
            )

    parameters, fields_list = await asyncio.gather(
        _get_parameters(),
        _get_fields(),
    )

    # ── Phase 7: Return ArtifactContext ──────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "chat_items": chat_items,
            "rubric_items": rubric_items,
            "thresholds": [thresholds],
            "scenario_counts": scenario_count_rows,
            "cohort_names": cohort_name_rows,
        },
        resources={
            "simulations": ResourcePair(selected=simulations, suggestions=[]),
            "scenarios": ResourcePair(selected=scenarios_list, suggestions=[]),
            "personas": ResourcePair(selected=personas, suggestions=[]),
            "rubrics": ResourcePair(selected=rubrics, suggestions=[]),
            "standard_groups": ResourcePair(selected=standard_groups, suggestions=[]),
            "documents": ResourcePair(selected=documents, suggestions=[]),
            "parameter_fields": ResourcePair(selected=parameter_fields, suggestions=[]),
            "parameters": ResourcePair(selected=parameters, suggestions=[]),
            "fields": ResourcePair(selected=fields_list, suggestions=[]),
            "profiles": ResourcePair(selected=target_profiles, suggestions=[]),
        },
    )


async def resolve_dashboard_search_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_resource_id: UUID | None = None,
    target_profile_id: UUID | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    practice: bool = False,
    scenario_ids: list[UUID] | None = None,
    infinite_mode: bool | None = None,
    show_archived: bool = False,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 20,
    date_from: date | None = None,
    date_to: date | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve dashboard search context for history table.

    Entries:
      - attempts: paginated GetAttemptResponse list (via search_attempts)
      - attempt_chats: GetAttemptChatResponse list for paginated attempts
      - total_count: total number of matching attempts

    Resources:
      - simulations, scenarios, personas, profiles
    """
    if not profile_resource_id:
        return ArtifactContext(
            artifact_id=None,
            active=True,
            group_id=None,  # type: ignore[arg-type]
            draft_version=None,
            entries={"attempts": [], "attempt_chats": [], "total_count": 0},
            resources={},
        )

    query_profile_id = target_profile_id or profile_resource_id
    page_offset = page * page_size

    # Step 1: Paginated attempts via search_attempts
    # TODO: search_attempts does not support date_from/date_to filters yet
    async with pool.acquire() as c:
        items, total_count = await search_attempts(
            conn=c,
            profile_ids=[query_profile_id],
            practice=practice,
            is_archived=(show_archived if practice else False),
            cohort_ids=cohort_ids,
            department_ids=department_ids,
            scenario_ids=scenario_ids,
            infinite_mode=infinite_mode,
            sort_order=sort_order,
            limit=page_size,
            offset=page_offset,
        )

    # Step 2: Batch-fetch chats for paginated attempt_ids
    paginated_ids = [item.attempt_id for item in items]

    chats: list[GetAttemptChatResponse] = []
    if paginated_ids:
        async with pool.acquire() as c:
            chats, _chat_count = await search_attempt_chats(
                c, attempt_ids=paginated_ids, limit=10000
            )

    # Step 3: Collect resource IDs
    h_sim_ids: set[UUID] = set()
    h_profile_ids: set[UUID] = set()
    h_persona_ids: set[UUID] = set()
    h_scenario_ids: set[UUID] = set()

    chats_by_attempt: dict[UUID, list[GetAttemptChatResponse]] = {}
    for chat in chats:
        if chat.attempt_id:
            chats_by_attempt.setdefault(chat.attempt_id, []).append(chat)

    for item in items:
        if item.simulation_id:
            h_sim_ids.add(item.simulation_id)
        if item.profile_id:
            h_profile_ids.add(item.profile_id)
        attempt_chats = chats_by_attempt.get(item.attempt_id, [])
        for chat in attempt_chats:
            if chat.persona_ids:
                h_persona_ids.update(chat.persona_ids)
            if chat.scenario_id:
                h_scenario_ids.add(chat.scenario_id)
        if item.scenario_ids:
            h_scenario_ids.update(item.scenario_ids)

    # Step 4: Parallel resource hydration
    async def _h_sims() -> list:
        if not h_sim_ids:
            return []
        async with pool.acquire() as c:
            return await get_simulations(
                c, list(h_sim_ids), redis, bypass_cache=bypass_cache
            )

    async def _h_profiles() -> list:
        if not h_profile_ids:
            return []
        async with pool.acquire() as c:
            return await get_profiles(
                c, list(h_profile_ids), redis, bypass_cache=bypass_cache
            )

    async def _h_personas() -> list:
        if not h_persona_ids:
            return []
        async with pool.acquire() as c:
            return await get_personas(
                c, list(h_persona_ids), redis, bypass_cache=bypass_cache
            )

    async def _h_scenarios() -> list:
        if not h_scenario_ids:
            return []
        async with pool.acquire() as c:
            return await get_scenarios(
                c, list(h_scenario_ids), redis, bypass_cache=bypass_cache
            )

    h_sims, h_profs, h_pers, h_scens = await asyncio.gather(
        _h_sims(), _h_profiles(), _h_personas(), _h_scenarios()
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "attempts": items,
            "attempt_chats": chats,
            "total_count": total_count,
        },
        resources={
            "simulations": ResourcePair(selected=h_sims, suggestions=[]),
            "scenarios": ResourcePair(selected=h_scens, suggestions=[]),
            "personas": ResourcePair(selected=h_pers, suggestions=[]),
            "profiles": ResourcePair(selected=h_profs, suggestions=[]),
        },
    )
