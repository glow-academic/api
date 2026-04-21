"""Attempt start — unified entry point for creating attempts.

Accepts either home_id or practice_id. Resolves the parent entry,
creates the attempt, and returns { attempt_id, chat_id }.

Does NOT create attempt_chat or trigger generation — the client
reads attempt/get and calls attempt/chat/create via generate.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class AttemptStartRequest(BaseModel):
    home_id: UUID | None = None
    practice_id: UUID | None = None
    infinite_mode: bool = False


class AttemptStartResponse(BaseModel):
    attempt_id: UUID
    chat_id: UUID
    department_id: UUID | None = None


async def attempt_start_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: AttemptStartRequest,
) -> AttemptStartResponse:
    """Create an attempt from a home or practice entry."""
    from app.infra.ledger.gate import LedgerDenied, ledger_gate, record_start
    from app.infra.ledger.types import AttemptContext
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.persona.create import create_persona
    from app.tools.resources.profile_personas.search import search_profile_personas
    from app.tools.resources.simulations.get import get_simulations

    is_practice = request.practice_id is not None
    parent_id = request.practice_id or request.home_id
    if not parent_id:
        raise HTTPException(status_code=400, detail="Either home_id or practice_id is required.")

    # ── Step 1: Profile context + permissions ────────────────────────────────

    identity = await resolve_profile_identity_context(
        pool, profile_id, redis,
        bypass_cache=True, session_id=session_id,
    )
    if identity is None:
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    if not has_permission(identity.role_permissions, "attempt", "start"):
        raise HTTPException(status_code=403, detail="You don't have permission to start attempts.")

    profiles_resource_id = identity.profiles_id
    if not profiles_resource_id:
        raise HTTPException(status_code=400, detail="Profile resource not found.")

    from app.infra.attempt.group import group_attempt_impl
    group_result = await group_attempt_impl(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )
    group_id = group_result.group_id

    # ── Step 2: Resolve parent entry ─────────────────────────────────────────

    if is_practice:
        from app.tools.entries.practice.get import get_practices
        async with pool.acquire() as conn:
            entries = await get_practices(conn, [parent_id])
        if not entries:
            raise HTTPException(status_code=404, detail="Practice entry not found.")
    else:
        from app.tools.entries.home.get import get_homes
        async with pool.acquire() as conn:
            entries = await get_homes(conn, [parent_id])
        if not entries:
            raise HTTPException(status_code=404, detail="Home entry not found.")

    parent_entry = entries[0]
    simulation_ids = parent_entry.simulation_ids or []

    # ── Step 3: Ledger gate ──────────────────────────────────────────────────

    _sim_id: str | None = None
    _sim_name: str | None = None
    _pass_pct: float | None = None

    if simulation_ids:
        try:
            from app.infra.chat.permissions import compute_pass_pct
            from app.tools.artifacts.rubric.get import get_rubrics
            from app.tools.artifacts.rubric.search import search_rubrics
            from app.tools.resources.points.get import get_points

            async with pool.acquire() as conn:
                sims = await get_simulations(conn, simulation_ids[:1], redis, bypass_cache=True)
                if sims:
                    _sim_id = str(simulation_ids[0])
                    _sim_name = sims[0].name

                rubric_ids, _ = await search_rubrics(conn, simulation_ids=simulation_ids[:1], limit_count=1)
                if rubric_ids:
                    rubrics = await get_rubrics(conn, rubric_ids, points=True)
                    if rubrics and rubrics[0].point_ids:
                        points = await get_points(conn, rubrics[0].point_ids, redis, bypass_cache=True)
                        total_pts = sum(p.value for p in points if p.type == "total")
                        pass_pts = sum(p.value for p in points if p.type == "pass")
                        pct = compute_pass_pct(total_pts, pass_pts)
                        if pct is not None:
                            _pass_pct = round(pct / 100.0, 2)
        except Exception:
            pass  # Non-fatal

    try:
        await ledger_gate(
            attempt_id=str(uuid.uuid4()),
            profile_id=str(profile_id),
            email=identity.primary_email,
            name=identity.name,
            attempt_context=AttemptContext(
                simulation_id=_sim_id,
                simulation_name=_sim_name,
                passing_threshold=_pass_pct,
            ) if _sim_id else None,
        )
        record_start(
            profile_id=str(profile_id),
            email=identity.primary_email,
            name=identity.name,
            role=identity.role_name,
            simulation_id=_sim_id,
            simulation_name=_sim_name,
        )
    except LedgerDenied as e:
        raise HTTPException(status_code=429, detail=f"Usage limit reached: {e.reason}") from e

    # ── Step 4: Resolve persona + chats ──────────────────────────────────────

    profile_ids = parent_entry.profile_ids or []
    if not profile_ids:
        raise HTTPException(status_code=400, detail="No profile personas found.")

    async with pool.acquire() as conn:
        profile_personas = await search_profile_personas(
            conn, redis=redis, profile_ids=profile_ids, bypass_cache=True,
        )

    persona_id = None
    for pp in profile_personas:
        if pp.profile_id == profiles_resource_id:
            persona_id = pp.persona_id
            break
    if not persona_id:
        raise HTTPException(status_code=400, detail="No profile persona found matching this profile.")

    if is_practice:
        from app.tools.entries.practice_chat.search import search_practice_chats
        async with pool.acquire() as conn:
            chat_entries = await search_practice_chats(
                conn, practice_ids=[parent_id], limit=1000, bypass_mv=True,
            )
    else:
        from app.tools.entries.home_chat.search import search_home_chats
        async with pool.acquire() as conn:
            chat_entries = await search_home_chats(
                conn, home_ids=[parent_id], limit=1000, bypass_mv=True,
            )

    if not chat_entries:
        raise HTTPException(status_code=400, detail="No chat entries found.")

    num_chats = len(chat_entries)
    first_chat_id = chat_entries[0].chat_id

    # Resolve department (for practice)
    resolved_department_id: UUID | None = None
    if is_practice:
        from app.infra.attempt.department import resolve_attempt_department
        from app.tools.entries.chat.get import get_chats as get_chat_entries_fn

        async with pool.acquire() as conn:
            chat_templates = await get_chat_entries_fn(conn, [first_chat_id])
        if chat_templates:
            resolved_department_id = resolve_attempt_department(
                user_department_ids=identity.department_ids,
                user_primary_department_id=identity.primary_department_id,
                chat_department_ids=chat_templates[0].department_ids,
            )

    sim_name = None
    sim_desc = None
    if simulation_ids:
        async with pool.acquire() as conn:
            simulations = await get_simulations(conn, simulation_ids[:1], redis, bypass_cache=True)
        if simulations:
            sim_name = simulations[0].name
            sim_desc = simulations[0].description

    # ── Step 5: Create attempt ───────────────────────────────────────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            persona_result = await create_persona(conn, personas_id=persona_id)
            attempt_result = await create_attempt(
                conn,
                session_id=session_id,
                user_persona_id=persona_result.id,
                profiles_id=profiles_resource_id,
                name=sim_name or "",
                description=sim_desc or "",
                infinite_mode=request.infinite_mode if is_practice else False,
                num_chats=num_chats,
                practice=is_practice,
            )

            if is_practice:
                from app.tools.entries.attempt_practice.create import create_attempt_practice
                await create_attempt_practice(
                    conn,
                    attempt_id=attempt_result.id,
                    practice_id=parent_id,
                    session_id=session_id,
                )
            else:
                from app.tools.entries.attempt_home.create import create_attempt_home
                await create_attempt_home(
                    conn,
                    attempt_id=attempt_result.id,
                    home_id=parent_id,
                    session_id=session_id,
                )

    # ── Step 6: Refresh MVs ─────────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_attempt(conn)
        await refresh_attempt_chat(conn)

    return AttemptStartResponse(
        attempt_id=attempt_result.id,
        chat_id=first_chat_id,
        department_id=resolved_department_id,
    )
