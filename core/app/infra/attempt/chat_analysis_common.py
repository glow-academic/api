"""Canonical bulk-write plumbing shared by the chat AI-analysis routes.

The five ``/attempt/chat_*`` routes (analyses, feedback, hints, improvements,
strengths) are structurally identical bulk *stage-inactive* writes: resolve a
parent (grade / message), create N rows (+ optional child rows), and persist
them. They previously declared ``idempotency_key``/``accept`` but never routed
through the audit wrapper — so no ``calls_entry`` was minted, no ``soft_call``
was ever written, and a dormant (``accept=False``) row was orphaned (no ledger,
no key to ack with).

This helper gives them the real canonical contract, mirroring the verified
attempt/test lifecycle writes:
  * goes through ``run_artifact_operation_with_audit`` (idempotency replay gate
    via ``operation_key`` + audit attribution);
  * resolves the time-windowed group so ``can_audit`` is satisfied and the
    wrapper threads its server ``call_id`` (the soft-ledger key);
  * ``soft=True`` creates every row (parent + children) dormant + a pending
    ``soft_calls_entry`` whose ``patch`` records ``{table: [ids]}`` for ALL
    affected tables; the ack ({idempotency_key, accept}) activates them all
    (``activate_rows`` per table) or rejects.

Each route passes a ``create_fn`` closure that resolves its own parent and
creates its rows, returning ``{table_name: [ids]}`` (primary table first); the
helper owns everything else.
"""

from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.permissions import enforce_attempt_access_by_chat
from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_upload_folder
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "attempt"

# Resolve the parent + create rows on the given conn; return {table: [ids]} for
# every row written (parent + children). ``soft`` → rows created active=False.
CreateFn = Callable[[asyncpg.Connection, Redis, bool], Awaitable[dict[str, list[UUID]]]]


class ChatAnalysisWriteResult(BaseModel):
    success: bool = True
    primary_ids: list[UUID] = []
    idempotency_key: UUID | None = None


async def run_chat_analysis_write(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    operation: str,
    primary_table: str,
    mv_target: str,
    profile_id: UUID,
    session_id: UUID,
    chat_id: UUID,
    idempotency_key: UUID | None,
    soft: bool,
    accept: bool | None,
    arguments: dict,
    create_fn: CreateFn,
) -> ChatAnalysisWriteResult:
    """Canonical bulk stage-inactive write for a chat AI-analysis op."""
    # Authorization (was MISSING on every chat-analysis route — analyses,
    # feedback, hints, improvements, strengths — each keyed solely by the
    # caller-supplied chat_id, so any authenticated profile could annotate ANY
    # student's graded chat). This is the single shared gate for the whole HTTP
    # path: resolve chat → owner and enforce the same self/super-admin/
    # strictly-higher-role-in-department rule chat_grade + archive use (issue
    # #148). Enforced here (before group resolution and any write, incl. the
    # soft/accept ack) so the class can't regress per-route.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    await enforce_attempt_access_by_chat(pool, redis, chat_id=chat_id, requester=requester)

    group_result = await group_attempt_impl(
        pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
    )
    is_ack = accept is not None and idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> ChatAnalysisWriteResult:
        # ── Short-circuit: ack — activate / reject the staged rows ──
        if accept is not None and idempotency_key is not None:
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != operation:
                raise HTTPException(status_code=404, detail=f"No pending {operation} for this call.")
            patch = entry.patch or {}
            rows: dict[str, list[str]] = patch.get("rows", {})
            primary = patch.get("primary_table", primary_table)
            if accept and rows:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        for table, ids in rows.items():
                            if ids:
                                await activate_rows(conn, table=table, ids=[UUID(x) for x in ids])
                await refresh_attempt_impl(
                    pool, redis, profile_id=profile_id, session_id=session_id, targets=[mv_target],
                )
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                    operation=operation, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return ChatAnalysisWriteResult(
                primary_ids=[UUID(x) for x in rows.get(primary, [])],
                idempotency_key=idempotency_key,
            )

        # ── Create (immediate or staged dormant) ──
        async with pool.acquire() as conn:
            async with conn.transaction():
                rows_created = await create_fn(conn, redis, soft)
                primary_ids = rows_created.get(primary_table, [])
                if soft and call_id is not None and primary_ids:
                    await create_soft_call(
                        conn, redis, call_id=call_id, artifact=ARTIFACT,
                        operation=operation, artifact_id=primary_ids[0], status="pending",
                        patch={
                            "rows": {t: [str(x) for x in ids] for t, ids in rows_created.items()},
                            "primary_table": primary_table,
                        },
                    )
        if not soft:
            await refresh_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id, targets=[mv_target],
            )
        return ChatAnalysisWriteResult(primary_ids=primary_ids, idempotency_key=call_id)

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact=ARTIFACT,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_result.group_id,
        operation=operation,
        arguments={"accept": accept} if is_ack else arguments,
        operation_key=idempotency_key,  # idempotency replay gate
        response_model=ChatAnalysisWriteResult,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
