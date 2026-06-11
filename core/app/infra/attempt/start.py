"""Attempt start — unified entry point for creating attempts.

Accepts either home_id or practice_id. Resolves the parent entry,
creates the attempt, and returns { attempt_id, chat_id }.

Does NOT create attempt_chat or trigger generation — the client
reads attempt/get and calls attempt/chat/create via generate.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.resolve import resolve_soft_call
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class AttemptStartRequest(BaseModel):
    home_id: UUID | None = None
    practice_id: UUID | None = None
    infinite_mode: bool = False
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior call; on the ack, the server-minted soft key to activate/reject a staged attempt")
    soft: bool = Field(False, description="Stage the attempt dormant (persona+attempt+junction active=False) — agent proposes; accept activates. The sim-env 'dormant attempt' primitive.")
    accept: bool | None = Field(None, description="Ack: True activates the staged attempt, False rejects. Only meaningful with idempotency_key")


class AttemptStartResponse(BaseModel):
    attempt_id: UUID
    chat_id: UUID
    department_id: UUID | None = None
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with accept to activate/reject the staged attempt.")


async def attempt_start_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: AttemptStartRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> AttemptStartResponse:
    """Create an attempt from a home or practice entry (with soft/accept staging)."""
    from app.tools.entries.attempt.create import create_attempt
    from app.infra.attempt.refresh import refresh_attempt_impl
    from app.tools.entries.persona.create import create_persona
    from app.tools.resources.profile_personas.search import search_profile_personas
    from app.tools.resources.simulations.get import get_simulations

    is_ack = accept is not None and idempotency_key is not None
    is_practice = request.practice_id is not None
    parent_id = request.practice_id or request.home_id
    if not parent_id and not is_ack:
        # The ack call carries no home_id/practice_id — it only promotes/rejects a
        # staged attempt (handled by the short-circuit after the profile check).
        raise HTTPException(status_code=400, detail="Either home_id or practice_id is required.")

    # ── Step 1: Profile context + permissions ────────────────────────────────

    with timed("profile"):
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

    # ── Short-circuit: ack — activate / reject a staged attempt ──────────────
    # (no re-resolution needed; just flip the staged persona+attempt+junction active)
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact="attempt")
        if entry is None or entry.status != "pending" or entry.operation != "start":
            raise HTTPException(status_code=404, detail="No pending attempt start for this call.")
        ids = entry.patch or {}
        # ── Atomic ack (A3/A4) ────────────────────────────────────────────
        # One transaction: the conditional terminal-state transition
        # (resolve_soft_call) + the persona/attempt/junction activations commit
        # together. A concurrent double-ack loses the race → resolve returns
        # None → we SKIP the activations. A crash before commit rolls back BOTH
        # the activations and the ledger row. The MV refresh runs only AFTER
        # the commit.
        async with pool.acquire() as conn:
            async with conn.transaction():
                resolved = await resolve_soft_call(
                    conn, redis, call_id=idempotency_key, artifact="attempt",
                    operation="start", artifact_id=entry.artifact_id,
                    accept=accept,
                )
                if resolved is None:
                    # Already resolved by a concurrent ack — no double activation.
                    return AttemptStartResponse(
                        attempt_id=UUID(ids["attempt_id"]),
                        chat_id=UUID(ids["chat_id"]),
                        idempotency_key=idempotency_key,
                    )
                if accept:
                    await activate_rows(conn, table="personas_entry", ids=[UUID(ids["persona_id"])])
                    await activate_rows(conn, table="attempt_entry", ids=[UUID(ids["attempt_id"])])
                    # junction has no id column → activate by attempt_id
                    jt = "attempt_practice_entry" if ids.get("is_practice") else "attempt_home_entry"
                    await conn.execute(
                        f"UPDATE {jt} SET active = true WHERE attempt_id = $1",
                        UUID(ids["attempt_id"]),
                    )
        if accept:
            await refresh_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["attempt_mv", "attempt_chat_mv"],
            )
        return AttemptStartResponse(
            attempt_id=UUID(ids["attempt_id"]),
            chat_id=UUID(ids["chat_id"]),
            idempotency_key=idempotency_key,
        )

    from app.infra.attempt.group import group_attempt_impl
    with timed("group"):
        group_result = await group_attempt_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
    group_id = group_result.group_id

    # ── Step 2: Resolve parent entry ─────────────────────────────────────────

    with timed("parent_entry"):
     if is_practice:
        from app.tools.entries.practice.get import get_practices
        async with pool.acquire() as conn:
            entries = await get_practices(conn, [parent_id], redis)
        if not entries:
            raise HTTPException(status_code=404, detail="Practice entry not found.")
     else:
        from app.tools.entries.home.get import get_homes
        async with pool.acquire() as conn:
            entries = await get_homes(conn, [parent_id], redis)
        if not entries:
            raise HTTPException(status_code=404, detail="Home entry not found.")

    parent_entry = entries[0]
    simulation_ids = parent_entry.simulation_ids or []

    # ── Step 3: Resolve persona + chats ──────────────────────────────────────

    profile_ids = parent_entry.profile_ids or []
    if not profile_ids:
        raise HTTPException(status_code=400, detail="No profile personas found.")

    with timed("profile_personas"):
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
                conn, redis, practice_ids=[parent_id], limit=1000,
            )
    else:
        from app.tools.entries.home_chat.search import search_home_chats
        async with pool.acquire() as conn:
            chat_entries = await search_home_chats(
                conn, redis, home_ids=[parent_id], limit=1000,
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
            chat_templates = await get_chat_entries_fn(conn, [first_chat_id], redis)
        if chat_templates:
            resolved_department_id = resolve_attempt_department(
                user_department_ids=identity.department_ids,
                user_primary_department_id=identity.primary_department_id,
                chat_department_ids=chat_templates[0].department_ids,
            )

    sim_name = None
    sim_desc = None
    if simulation_ids:
        simulations = await get_simulations(pool, simulation_ids[:1], redis, bypass_cache=True)
        if simulations:
            sim_name = simulations[0].name
            sim_desc = simulations[0].description

    # ── Step 4: Create attempt ───────────────────────────────────────────────

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with conn.transaction():
            persona_result = await create_persona(conn, redis, personas_id=persona_id, soft=soft)
            attempt_result = await create_attempt(
                conn, redis,
                session_id=session_id,
                user_persona_id=persona_result.id,
                profiles_id=profiles_resource_id,
                name=sim_name or "",
                description=sim_desc or "",
                infinite_mode=request.infinite_mode if is_practice else False,
                num_chats=num_chats,
                practice=is_practice,
                soft=soft,
            )

            if is_practice:
                from app.tools.entries.attempt_practice.create import (
                    create_attempt_practice,
                )
                await create_attempt_practice(
                    conn, redis,
                    attempt_id=attempt_result.id,
                    practice_id=parent_id,
                    session_id=session_id,
                    soft=soft,
                )
            else:
                from app.tools.entries.attempt_home.create import create_attempt_home
                await create_attempt_home(
                    conn, redis,
                    attempt_id=attempt_result.id,
                    home_id=parent_id,
                    session_id=session_id,
                    soft=soft,
                )

            # Soft: stash the staged chain as a pending soft_call (keyed by the
            # server call_id) so the ack can activate persona+attempt+junction.
            if soft and call_id is not None:
                await create_soft_call(
                    conn, redis, call_id=call_id, artifact="attempt",
                    operation="start", artifact_id=attempt_result.id, status="pending",
                    patch={
                        "persona_id": str(persona_result.id),
                        "attempt_id": str(attempt_result.id),
                        "chat_id": str(first_chat_id),
                        "is_practice": is_practice,
                    },
                )

    # ── Step 5: Refresh MVs ─────────────────────────────────────────────────

    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["attempt_mv", "attempt_chat_mv"],
        )

    return AttemptStartResponse(
        attempt_id=attempt_result.id,
        chat_id=first_chat_id,
        department_id=resolved_department_id,
        idempotency_key=call_id,
    )
