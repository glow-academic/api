"""attempt/search — filtered/paginated query against attempt_mv."""

from datetime import datetime, timezone
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt.types import GetAttemptResponse
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "attempt_mv"


async def search_attempts(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    practice: bool | None = None,
    is_archived: bool | None = None,
    is_completed: bool | None = None,
    infinite_mode: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> tuple[list[GetAttemptResponse], int]:
    """Search attempt entries from attempt_mv with declarative filters.

    Hedged: merges the MV result with the per-row write-back cache so
    freshly-created attempts appear before the MV refresh has caught up.
    Cache rows from ``create_attempt`` only carry creator-known fields
    (attempt_id, profile_id, user_persona_id, infinite_mode, num_chats,
    attempt_created_at); junction-derived fields (simulation_id, role_id,
    personas_id, cohort_id, department_id, scenario_ids, chat_entry_id,
    attempt_chat_id, is_archived, is_completed, practice) are None / [] /
    False at create-time. A search filter targeting one of those fields
    will naturally exclude an under-hydrated cache row — that's correct:
    once the child junction writes invalidate the cache (TODO: wire those
    invalidations — see create.py), the next read falls through to the MV.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order == "asc" else "DESC"
    rows = await conn.fetch(
        f"""
        SELECT attempt_id, simulation_id, profile_id, role_id, user_persona_id,
               personas_id, cohort_id, department_id, practice,
               attempt_created_at, infinite_mode, num_chats, is_archived,
               is_completed, scenario_ids, chat_entry_id, attempt_chat_id,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR simulation_id = ANY($2))
          AND ($3::uuid[] IS NULL OR profile_id = ANY($3))
          AND ($4::uuid[] IS NULL OR role_id = ANY($4))
          AND ($5::uuid[] IS NULL OR cohort_id = ANY($5))
          AND ($6::uuid[] IS NULL OR department_id = ANY($6))
          AND ($7::uuid[] IS NULL OR scenario_ids && $7)
          AND ($8::boolean IS NULL OR practice = $8)
          AND ($9::boolean IS NULL OR is_archived = $9)
          AND ($10::boolean IS NULL OR is_completed = $10)
          AND ($11::boolean IS NULL OR infinite_mode = $11)
          AND ($12::timestamptz IS NULL OR attempt_created_at >= $12)
          AND ($13::timestamptz IS NULL OR attempt_created_at <= $13)
        ORDER BY attempt_created_at {order}
        LIMIT $14 OFFSET $15
        """,
        attempt_ids,
        simulation_ids,
        profile_ids,
        role_ids,
        cohort_ids,
        department_ids,
        scenario_ids,
        practice,
        is_archived,
        is_completed,
        infinite_mode,
        date_from,
        date_to,
        # Over-fetch like the messages pattern so the hedged merge has
        # enough MV rows to cover offset+limit after dedupe.
        limit + offset + 1000,
        0,
    )

    mv_total = rows[0]["total_count"] if rows else 0

    # ASC mode bypasses the hedged helper (which only sorts DESC).
    if sort_order.lower() == "asc":
        items_list = [
            GetAttemptResponse(
                **{k: v for k, v in dict(r).items() if k != "total_count"}
            )
            for r in rows
        ]
        return items_list[offset : offset + limit], mv_total

    # Reshape MV rows to the cache-row keyspace (str UUIDs, isoformat
    # timestamps) so cached and MV dicts dedupe + sort consistently.
    def _iso(ts: datetime | None) -> str | None:
        if ts is None:
            return None
        if isinstance(ts, str):
            return ts
        return ts.isoformat()

    mv_dicts = [
        {
            "attempt_id": str(r["attempt_id"]),
            "simulation_id": str(r["simulation_id"]) if r["simulation_id"] else None,
            "profile_id": str(r["profile_id"]) if r["profile_id"] else None,
            "role_id": str(r["role_id"]) if r["role_id"] else None,
            "user_persona_id": (
                str(r["user_persona_id"]) if r["user_persona_id"] else None
            ),
            "personas_id": str(r["personas_id"]) if r["personas_id"] else None,
            "cohort_id": str(r["cohort_id"]) if r["cohort_id"] else None,
            "department_id": str(r["department_id"]) if r["department_id"] else None,
            "practice": r["practice"],
            "attempt_created_at": _iso(r["attempt_created_at"]),
            "infinite_mode": r["infinite_mode"],
            "num_chats": r["num_chats"],
            "is_archived": r["is_archived"],
            "is_completed": r["is_completed"],
            "scenario_ids": [str(s) for s in (r["scenario_ids"] or [])],
            "chat_entry_id": str(r["chat_entry_id"]) if r["chat_entry_id"] else None,
            "attempt_chat_id": (
                str(r["attempt_chat_id"]) if r["attempt_chat_id"] else None
            ),
            # id mirror so hedged_search id_key="attempt_id" dedupes cleanly.
            "id": str(r["attempt_id"]),
        }
        for r in rows
    ]

    # Filter closure mirrors the SQL WHERE 1:1.
    attempt_ids_str = {str(x) for x in attempt_ids} if attempt_ids else None
    simulation_ids_str = (
        {str(x) for x in simulation_ids} if simulation_ids else None
    )
    profile_ids_str = {str(x) for x in profile_ids} if profile_ids else None
    role_ids_str = {str(x) for x in role_ids} if role_ids else None
    cohort_ids_str = {str(x) for x in cohort_ids} if cohort_ids else None
    department_ids_str = (
        {str(x) for x in department_ids} if department_ids else None
    )
    scenario_ids_str = (
        {str(x) for x in scenario_ids} if scenario_ids else None
    )

    def matches(row: dict) -> bool:
        if attempt_ids_str is not None and str(row.get("attempt_id")) not in attempt_ids_str:
            return False
        if simulation_ids_str is not None:
            sim = row.get("simulation_id")
            if sim is None or str(sim) not in simulation_ids_str:
                return False
        if profile_ids_str is not None:
            pid = row.get("profile_id")
            if pid is None or str(pid) not in profile_ids_str:
                return False
        if role_ids_str is not None:
            rid = row.get("role_id")
            if rid is None or str(rid) not in role_ids_str:
                return False
        if cohort_ids_str is not None:
            cid = row.get("cohort_id")
            if cid is None or str(cid) not in cohort_ids_str:
                return False
        if department_ids_str is not None:
            did = row.get("department_id")
            if did is None or str(did) not in department_ids_str:
                return False
        if scenario_ids_str is not None:
            row_scenarios = {str(s) for s in (row.get("scenario_ids") or [])}
            if not (row_scenarios & scenario_ids_str):
                return False
        if practice is not None and row.get("practice") != practice:
            return False
        if is_archived is not None and row.get("is_archived") != is_archived:
            return False
        if is_completed is not None and row.get("is_completed") != is_completed:
            return False
        if infinite_mode is not None and row.get("infinite_mode") != infinite_mode:
            return False
        ts_raw = row.get("attempt_created_at")
        ts: datetime | None
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except Exception:
                ts = None
        else:
            ts = ts_raw
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        return True

    def _sort_key(row: dict) -> datetime:
        ts = row.get("attempt_created_at")
        if ts is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    items, total = await hedged_search_with_total(
        redis,
        "attempt",
        mv_rows=mv_dicts,
        mv_total=mv_total,
        matches_filter=matches,
        sort_key=_sort_key,
        limit=limit,
        offset=offset,
        id_key="attempt_id",
        bypass_cache=bypass_cache,
    )

    return [GetAttemptResponse.model_validate(r) for r in items], total
