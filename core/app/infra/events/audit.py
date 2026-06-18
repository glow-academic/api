"""Generic tool-backed audit wrappers for artifact operations."""

from __future__ import annotations

import hashlib
import inspect
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID


def _mint_group_id() -> UUID:
    """Mint a v7 UUID for a brand-new group when the route opted in.
    Falls back to v4 on Python builds that don't expose ``uuid.uuid7``.
    """
    return uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4()


def _mint_call_id() -> UUID:
    """Mint a v7 UUID for the audit-event ``call_id``. Same fallback as
    ``_mint_group_id``. The id is the wire-level identity for the
    started/completed/failed events; the audit-row branch reuses it via
    ``pre_minted_call_id`` so the DB row and the events agree.
    """
    return uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4()

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.tools.entries.calls.search import search_calls
from app.tools.entries.groups.create import create_group
from app.tools.resources.tools.get import get_tools

# SSE mirroring is handled centrally by ``ws/output.py`` — every
# ``internal_sio.emit(...)`` automatically reaches the SSE hub for the
# event's ``group_id``. No need to call ``emit_artifact_operation_*``
# helpers here; the catch-all forwarder is the single primitive.
from app.infra.tool_graph import SettingsToolGraph
from app.infra.tools.entries.create_tool_call import create_tool_call
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)
T = TypeVar("T")

internal_sio = get_internal_sio()

# Idempotency replay gate. The lock only guards the window where N concurrent
# first-runs of the same operation_key race before any receipt exists; once a
# receipt is written the (fresh, bypass_mv) lookup short-circuits first, so the
# lock is never consulted on later retries. TTL should comfortably exceed the
# longest expected execution (incl. AI generations).
_IDEM_LOCK_TTL_SECONDS = 300
_IDEM_LOCK_PREFIX = "idem:op:"

# Lightweight replay receipt for the NON-audit branch (can_audit=False — no
# registered tool, or missing session/group/profiles_id). The audited branch
# persists a full ``calls_entry`` + JSON receipt that ``search_calls`` replays;
# the non-audit branch has no such row, so without this a successful op left no
# trace. Combined with always releasing the lock in a ``finally``, this makes
# replay correctness independent of ``can_audit``: a retry within the TTL finds
# the stored result and replays it instead of re-executing (duplicate write) or
# 409-ing on a stuck lock. Holds the arg-fingerprint (same-key/different-body
# → 409) and the JSON-able result. TTL matches the lock window.
_IDEM_RECEIPT_PREFIX = "idem:receipt:"
_IDEM_RECEIPT_TTL_SECONDS = 300


def _fingerprint_arguments(arguments: dict[str, Any]) -> str:
    """Stable hash of an operation's arguments — backs same-key/different-body
    detection so a reused ``operation_key`` carrying a different payload is
    rejected (409) rather than silently replaying the first response."""
    canonical = json.dumps(arguments or {}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_ACK_CONTROL_KEYS = frozenset({
    "idempotency_key", "operation_key", "accept", "soft", "sid", "session_id", "profile_id",
})


def _is_bare_ack(arguments: dict[str, Any]) -> bool:
    """True when this is a soft/accept *ack* call, not a fresh operation.

    An ack explicitly sets ``accept`` (True/False) and carries no substantive
    payload — it only promotes/rejects a dormant entry the soft-call ledger
    already tracks, intentionally reusing the key with a different body. The
    replay gate skips these (the ledger owns their idempotency).

    Crucially this must NOT skip a normal request that merely *defaults*
    ``accept`` — e.g. ``generate``'s ``accept=True`` — because those carry real
    payload. So we require ``accept`` set AND no non-None field outside the
    control set; a generate request always has live content (instructions etc.).
    """
    if arguments.get("accept") is None:
        return False
    payload = {
        k: v for k, v in arguments.items()
        if v is not None and k not in _ACK_CONTROL_KEYS
    }
    return not payload


def resolve_artifact_operation_tool(
    tool_graph: SettingsToolGraph,
    *,
    artifact: str,
    operation: str,
) -> UUID | None:
    """Pick the canonical tool for an artifact operation from the tool graph."""
    matches = [
        tool
        for tool in tool_graph.tools
        if tool.target_type == "artifact"
        and tool.target == artifact
        and tool.operation == operation
    ]
    if not matches:
        return None

    best = min(matches, key=lambda tool: (tool.system_id, tool.agent_id, tool.tool_id))
    return best.tool_id


async def run_artifact_operation_with_audit(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact: str,
    profile_id: UUID,
    operation: str,
    runner: Callable[..., Awaitable[T]],
    arguments: dict[str, Any],
    sid: str = "",
    rooms: list[str] | None = None,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    run_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    response_model: type[T] | None = None,
    role: str = "user",
    mcp: bool = False,
    upload_folder: Path | None = None,
    instruction_template: str | None = None,
    operation_key: UUID | None = None,
    call_id: UUID | None = None,
    suppress_started: bool = False,
    mint_group_id_if_missing: bool = False,
) -> T:
    """Execute an artifact operation with lifecycle emission and optional audit.

    Emits to internal_sio:
      - {artifact}.{operation}.started
      - {artifact}.{operation}.completed (on success)
      - {artifact}.{operation}.failed (on error)

    Output handlers in ws/output/ pick these up and forward to clients.
    When the tool graph has a matching tool, a tool-call audit record is persisted.

    Room resolution: events broadcast to ``room=profile_id`` so every
    socket the profile has open (multi-tab, multi-device, debug panel)
    receives them. The originating ``sid`` is still threaded through the
    payload for provenance, but room delivery is profile-scoped.
    """
    effective_rooms = rooms or [str(profile_id)]
    event_prefix = f"{artifact}.{operation}"

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise PermissionError("Profile not found. Please sign in again.")

    # ── Authorization for export operations (systemic gate) ──────────────────
    # Export operations dump bulk artifact data (CSV/ZIP). Several export impls
    # had NO permission check and were reachable by ANY authenticated caller —
    # verified live that a guest could export the profile directory, auth/SSO
    # config, etc. Every export route funnels through here with
    # ``operation="export"``, so enforce the ``(artifact, "export")`` capability
    # at this single choke point. Scoped to ``operation == "export"`` so no other
    # audited op is affected. This does NOT over-restrict: "export" is part of
    # ``_READ_OPS`` in the role seed, so any role granted read on an artifact
    # also holds export (e.g. guests have ``attempt:export``, and
    # ``attempt/export``'s own ``check_attempt_access`` still scopes them to
    # their own attempts); a caller with no access to the artifact is denied.
    if operation == "export":
        from app.infra.permissions_helpers import has_permission

        if not has_permission(
            common.profile.role_permissions, artifact, "export"
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to export this resource.",
            )

    # Permission-driven tool resolution — agent-independent. See
    # ``infra/tools/resolve_for_operation.py``: walks the global tool
    # registry by permission overlap, picks the most-specific tool,
    # attaches its instruction_template if any. Replaces the prior
    # ``resolve_artifact_operation_tool`` (which is agent-scoped via
    # tool_graph and stays around for generation-side callers that
    # need that view).
    from app.infra.server_timing import timed
    from app.infra.tools.resolve_for_operation import resolve_tool_for_operation
    with timed("tool_resolve"):
        async with pool.acquire() as _conn:
            resolved_op_tool = await resolve_tool_for_operation(
                _conn, redis, artifact=artifact, operation=operation,
            )
    tool_id = resolved_op_tool.tool_id if resolved_op_tool else None
    resolved_template = (
        resolved_op_tool.instruction_template if resolved_op_tool else None
    )
    # Caller-provided template wins; otherwise use the resolved one.
    # This keeps the LLM dispatch path's per-tool enrichment in charge
    # when it explicitly passes a template, and lets every other audit
    # caller get a template for free via permission-based resolution.
    if instruction_template is None:
        instruction_template = resolved_template
    effective_session_id = session_id or common.profile.session_id
    effective_group_id = group_id
    effective_profiles_id = common.profile.profiles_id
    effective_upload_folder = upload_folder or UPLOAD_FOLDER

    # ── Idempotency replay gate (opt-in; inert unless ``operation_key`` set) ──
    # ``operation_key`` IS the client's idempotency key — one key. Routes thread
    # ``request.idempotency_key`` straight through as ``operation_key`` (the
    # codebase already merges them: ``operation_key or idempotency_key``). Runs
    # before any side effect (group mint, ``.started`` emit, execution).
    #   • A prior completed call with this key → replay its persisted receipt.
    #   • Otherwise take a short-lived lock so only one concurrent first-run runs.
    # The soft/accept ack phase (a *bare* ack — ``accept`` set + no payload) is
    # SKIPPED: it deliberately reuses the key with a different body, and the
    # soft-call ledger already makes that phase idempotent; the gate only guards
    # the first (propose) call. A normal request that merely defaults ``accept``
    # (e.g. ``generate``'s ``accept=True``) is NOT a bare ack — see ``_is_bare_ack``.
    # FAIL-OPEN: any unexpected error logs and falls through to normal execution
    # — the gate must never break a request that would otherwise succeed. A 409
    # is intentional (reused key with a different body, or in-flight duplicate)
    # and is re-raised.
    # ``_idem_lock_key`` is set when (and only when) we won the lock below, so
    # the post-execution ``finally`` can release it. Releasing unconditionally
    # is the core A2 fix: the non-audit branch writes no ``calls_entry`` receipt,
    # so a held lock that's never released turned a SUCCEEDED op into a 300s 409
    # lockout (retry <TTL) then a duplicate execution (retry >TTL).
    _idem_lock_key: str | None = None
    _idem_gate_active = (
        operation_key is not None and not bypass_cache and not _is_bare_ack(arguments)
    )
    if _idem_gate_active:
        try:
            with timed("idempotency"):
                async with pool.acquire() as _idem_conn:
                    # search_calls now has a hedged-read cache (v1.0.31 +
                    # v1.0.30 helpers): the cache catches recently-written
                    # calls within its 1h window, and the MV covers older
                    # ones. bypass_mv removed — the cache layer makes it
                    # unnecessary.
                    _prior = await search_calls(
                        _idem_conn,
                        redis,
                        operation_keys=[operation_key],
                        limit=1,
                    )
            _prior = [c for c in _prior if c.file_path]
            if _prior:
                _receipt_path = effective_upload_folder / _prior[0].file_path
                _receipt = json.loads(_receipt_path.read_text(encoding="utf-8"))
                if _fingerprint_arguments(_receipt.get("arguments")) != \
                        _fingerprint_arguments(arguments):
                    raise HTTPException(
                        status_code=409,
                        detail="Idempotency key reused with a different request payload.",
                    )
                _cached = _receipt.get("raw_output")
                # Never replay a cached server error — let the retry truly retry.
                _is_error = isinstance(_cached, dict) and _cached.get("success") is False
                # A3: a soft/propose persists a calls_entry receipt, but its
                # "success" reflects only a DORMANT staged binding — replaying it
                # would re-assert a creation that may since have been rejected.
                # Fall through to the soft-call ledger (the propose's real
                # idempotency layer) instead of replaying a stale success.
                _is_soft = bool(arguments.get("soft"))
                if _cached is not None and not _is_error and not _is_soft:
                    logger.info(
                        "IDEM_REPLAY %s.%s operation_key=%s call_id=%s",
                        artifact, operation, operation_key, _prior[0].id,
                    )
                    if response_model is not None:
                        return response_model.model_validate(_cached)
                    return _cached  # type: ignore[return-value]
            else:
                # No persisted ``calls_entry`` receipt. Before serializing,
                # consult the lightweight Redis receipt the NON-audit branch
                # leaves behind — that branch never writes a ``calls_entry``,
                # so this is the only replay signal for can_audit=False ops.
                _redis_receipt_raw = await redis.get(
                    f"{_IDEM_RECEIPT_PREFIX}{operation_key}"
                )
                if _redis_receipt_raw is not None:
                    _rr = json.loads(
                        _redis_receipt_raw.decode()
                        if isinstance(_redis_receipt_raw, bytes)
                        else _redis_receipt_raw
                    )
                    if _rr.get("fingerprint") != _fingerprint_arguments(arguments):
                        raise HTTPException(
                            status_code=409,
                            detail="Idempotency key reused with a different request payload.",
                        )
                    _cached = _rr.get("raw_output")
                    _is_error = (
                        isinstance(_cached, dict) and _cached.get("success") is False
                    )
                    if _cached is not None and not _is_error:
                        logger.info(
                            "IDEM_REPLAY(redis) %s.%s operation_key=%s",
                            artifact, operation, operation_key,
                        )
                        if response_model is not None:
                            return response_model.model_validate(_cached)
                        return _cached  # type: ignore[return-value]

                # No receipt anywhere yet → serialize concurrent first-runs.
                _lock_key = f"{_IDEM_LOCK_PREFIX}{operation_key}"
                _got_lock = await redis.set(
                    _lock_key, "1", nx=True, ex=_IDEM_LOCK_TTL_SECONDS,
                )
                if not _got_lock:
                    raise HTTPException(
                        status_code=409,
                        detail="An operation with this idempotency key is already in progress.",
                    )
                _idem_lock_key = _lock_key
        except HTTPException:
            raise
        except Exception:
            logger.warning(
                "IDEM_GATE_SKIP %s.%s operation_key=%s — gate error, falling through",
                artifact, operation, operation_key, exc_info=True,
            )

    async def _release_idem_lock() -> None:
        """Drop the in-flight lock once execution is done (success OR failure).

        The lock only serialized concurrent first-runs; with the receipt now
        written (calls_entry for can_audit, Redis receipt otherwise) it has done
        its job. Leaving it held is the A2 bug. Best-effort — a Redis hiccup
        here must never mask the real result; the TTL is the backstop.
        """
        if _idem_lock_key is None:
            return
        try:
            await redis.delete(_idem_lock_key)
        except Exception:
            logger.debug("IDEM_LOCK_RELEASE_FAIL key=%s (TTL backstop)", _idem_lock_key)

    async def _write_redis_receipt(raw_output: Any) -> None:
        """Persist the lightweight replay receipt for the NON-audit branch.

        can_audit=False ops have no ``calls_entry``; this is their only replay
        signal. Skip caching server errors so a retry truly retries (mirrors the
        ``calls_entry`` replay path). Best-effort."""
        if not _idem_gate_active or operation_key is None:
            return
        # A3: never persist a replayable success receipt for a soft/propose op.
        # A propose only stages a DORMANT binding whose fate (accept/reject) is
        # decided by a later ack — replaying its cached "success" would re-assert
        # a creation that may since have been rejected. The soft-call ledger is
        # the authoritative idempotency layer for the propose phase.
        if arguments.get("soft"):
            return
        _is_err = isinstance(raw_output, dict) and raw_output.get("success") is False
        if _is_err:
            return
        try:
            _serialisable = (
                raw_output.model_dump(mode="json")
                if hasattr(raw_output, "model_dump")
                else raw_output
            )
            await redis.set(
                f"{_IDEM_RECEIPT_PREFIX}{operation_key}",
                json.dumps(
                    {
                        "fingerprint": _fingerprint_arguments(arguments),
                        "raw_output": _serialisable,
                    },
                    default=str,
                ),
                ex=_IDEM_RECEIPT_TTL_SECONDS,
            )
        except Exception:
            logger.debug(
                "IDEM_RECEIPT_WRITE_FAIL operation_key=%s", operation_key
            )

    # Opt-in mint: routes for create-the-group operations (e.g. /X/group)
    # set ``mint_group_id_if_missing=True`` so the framework assigns an id
    # before any event fires. Without this, ``effective_group_id`` is None
    # at ``.started`` time and SSE drops the event (only ``.completed``
    # carries the impl-resolved id), producing the asymmetric "completed
    # without started" trace that breaks the activity-rail bubble.
    #
    # Mint is paired with an idempotent ``create_group`` upsert — the
    # downstream ``create_tool_call`` insert FK-references ``groups_entry``,
    # so the row must exist before any audit write. The runner's own
    # ``create_group`` call later in the impl is then a no-op (ON CONFLICT
    # DO UPDATE).
    if mint_group_id_if_missing and effective_group_id is None:
        # Consult the active-group cache FIRST. Without this, a
        # concurrent page-load (e.g. /context + /group + /search
        # firing in parallel) where /group uses mint_if_missing
        # blindly mints a fresh id, while /context and /search go
        # through resolve_group_impl which uses Redis SETNX. Result:
        # /group lands in its own freshly-minted group, the others
        # converge on the SETNX winner, and audits get fragmented
        # across two groups — chat-history threading then sees only
        # one bucket.
        #
        # Reading the same Redis key resolve_group_impl uses keeps
        # all three on the same group. If nothing is there, we mint
        # a fresh id, claim the slot atomically (SET NX EX), and
        # whoever wins materializes the group. If we lost the SETNX,
        # we re-read the winner's id.
        from app.infra.group.resolve import (
            DEFAULT_WINDOW_SECONDS,
            _redis_key,
        )
        _key = _redis_key(artifact, profile_id)
        _existing = await redis.get(_key)
        if _existing:
            effective_group_id = UUID(
                _existing.decode() if isinstance(_existing, bytes) else _existing
            )
            await redis.expire(_key, DEFAULT_WINDOW_SECONDS)
        else:
            _candidate = _mint_group_id()
            _claimed = await redis.set(
                _key, str(_candidate), nx=True, ex=DEFAULT_WINDOW_SECONDS,
            )
            if _claimed:
                effective_group_id = _candidate
            else:
                _winner = await redis.get(_key)
                effective_group_id = UUID(
                    _winner.decode() if isinstance(_winner, bytes) else _winner
                ) if _winner else _candidate
                # Refresh window even when re-using winner's id.
                await redis.expire(_key, DEFAULT_WINDOW_SECONDS)
        async with pool.acquire() as conn:
            await create_group(
                conn,
                redis, session_id=effective_session_id,
                artifact_type=artifact,
                id=effective_group_id,
            )

    can_audit = all([
        tool_id,
        effective_session_id,
        effective_group_id,
        effective_profiles_id,
    ])
    if run_id is not None:
        logger.info("AUDIT_GEN: %s.%s run_id=%s", artifact, operation, run_id)

    # --- Identity for the wire ---
    # ``emit_call_id`` is the single id every event (.started/.completed
    # /.failed) carries. The audit-row branch reuses it via
    # ``pre_minted_call_id`` so the DB row id matches the wire id; the
    # non-audit branch (no registered tool, no ``can_audit``) still emits
    # coherent started+completed pairs identified by this same id.
    # Pre-minted ``call_id`` from the caller (e.g. streaming generate)
    # wins so its earlier ``.started`` correlates with our ``.completed``.
    emit_call_id: UUID = call_id or _mint_call_id()

    # Dispatch timestamp — captured BEFORE we await the runner so it
    # reflects when the tool was invoked, not when audit finished
    # writing the result row. Passed through to ``create_tool_call`` so
    # the audit-side ``messages_entry`` row uses this for ``created_at``,
    # which makes the FE chat panel render the tool-call indicator at
    # its true position in time — BEFORE the nested run's outputs
    # (prompt + produced media) that happened between dispatch and the
    # audit write. See the matching ``created_at`` override on
    # ``create_run_message`` / ``create_message``.
    started_at = datetime.now(timezone.utc)

    # --- Tool resource for the wire ---
    # Resolve via the canonical ``get_tools`` black box (cached). Sent
    # alongside every event so the client knows whether to render a
    # tool-call bubble (rich metadata, expandable receipt) or a
    # lightweight event pill (audit fired but no tool registered).
    # ``None`` is the discriminator: present ⇒ tool, absent ⇒ event.
    tool_payload: dict[str, Any] | None = None
    if tool_id is not None:
        _tools = await get_tools(pool, [tool_id], redis)
        if _tools:
            tool_payload = _tools[0].model_dump(mode="json")

    # --- .started (always, regardless of can_audit) ---
    # Hoisted out of ``_on_call_created`` so it fires for every operation
    # the framework wraps, not only audited ones. Without this, ops with
    # no tool registered (e.g. ``/X/text_download``, ``/X/call_download``)
    # were silently emitting only ``.completed`` and the client could
    # never render their started bubble.
    if not suppress_started:
        with timed("started_emit"):
            await internal_sio.emit(f"{event_prefix}.started", {
                "sid": sid,
                "rooms": effective_rooms,
                "role": role,
                **arguments,
                # Framework-owned identity trails the spread so request bodies
                # that happen to carry ``call_id``/``group_id`` keys (download
                # routes, etc.) don't overwrite the audit's own ids.
                "call_id": str(emit_call_id),
                "group_id": str(effective_group_id) if effective_group_id else None,
                "operation_key": str(operation_key) if operation_key else None,
                "tool": tool_payload,
            })

    # --- Execute ---
    call_upload_id: UUID | None = None
    tool_error: Exception | None = None

    # Check whether the runner accepts orchestration kwargs. Orchestration
    # runners (closures over ``request``) opt into receiving ``call_id``
    # and/or ``group_id`` from the framework; plain CRUD lambdas accept
    # neither. Same signature-inspection pattern, two independent flags.
    _runner_params = inspect.signature(runner).parameters
    _runner_accepts_call_id = "call_id" in _runner_params
    _runner_accepts_group_id = "group_id" in _runner_params

    async def _invoke_runner(call_id: UUID | None = None) -> Any:
        from app.infra.server_timing import timed
        kwargs: dict[str, Any] = {}
        if _runner_accepts_call_id:
            kwargs["call_id"] = call_id
        if _runner_accepts_group_id:
            kwargs["group_id"] = effective_group_id
        with timed("runner"):
            return await runner(**kwargs)

    if can_audit:
        async def _tool_fn(
            _conn: "asyncpg.Connection | None" = None,
            *, call_id: UUID | None = None, **_arguments: Any
        ) -> Any:
            # ``_conn`` is intentionally ignored — the runner manages its own
            # connections. PERF1: create_tool_call now passes None here (no
            # pooled connection is held across the runner/LLM call).
            result = await _invoke_runner(call_id=call_id)
            if hasattr(result, "model_dump"):
                return result.model_dump(mode="json")
            return result

        # ``.started`` already fired at the top of this function with
        # ``emit_call_id``. We pass ``emit_call_id`` as ``pre_minted_call_id``
        # so ``create_tool_call`` adopts the same id for the DB row and the
        # receipt file. The ``on_call_created`` callback is a no-op now —
        # nothing to fire.
        async def _on_call_created(_cid: UUID | None) -> None:
            return

        with timed("audit_write"):
            # PERF1: pass the POOL, not a held connection. ``create_tool_call``
            # borrows a connection only for the short pre-runner run/call
            # inserts and releases it before the runner (LLM) executes — no
            # pooled connection is pinned across the provider network call.
            audit_result = await create_tool_call(
                pool,
                redis,
                group_id=effective_group_id,  # type: ignore[arg-type]
                session_id=effective_session_id,  # type: ignore[arg-type]
                profile_id=effective_profiles_id,  # type: ignore[arg-type]
                upload_folder=effective_upload_folder,
                tool_fn=_tool_fn,
                arguments=arguments,
                tool_id=tool_id,
                run_id=run_id,
                operation_key=operation_key,
                role=role,
                mcp=mcp,
                instruction_template=instruction_template,
                raise_on_error=False,
                on_call_created=_on_call_created,
                pre_minted_call_id=emit_call_id,
                started_at=started_at,
            )
        result_data = audit_result.result
        call_upload_id = audit_result.call_upload_id

        # Check if the runner failed (captured by create_tool_call). Re-raise the
        # ORIGINAL exception type (HTTPException, CsvParseError, …) so routes' typed
        # handlers and 4xx status codes survive the audit wrapper; fall back to a
        # generic Exception only if the original wasn't captured.
        if isinstance(result_data, dict) and result_data.get("success") is False:
            tool_error = audit_result.error or Exception(
                result_data.get("message", "Unknown error")
            )
    else:
        try:
            result_data = await _invoke_runner()
        except Exception as exc:
            failed_payload = {
                "sid": sid,
                "rooms": effective_rooms,
                "call_id": str(emit_call_id),
                "group_id": str(effective_group_id) if effective_group_id else None,
                "run_id": str(run_id) if run_id else None,
                "operation_key": str(operation_key) if operation_key else None,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "role": role,
                "tool": tool_payload,
            }
            await internal_sio.emit(f"{event_prefix}.failed", failed_payload)

            # Stamp the failure into the call receipt when a pre-minted
            # call_id exists (the streaming generate path mints one and
            # the receipt file already exists from its earlier write).
            # Otherwise no receipt to append to.
            if call_id is not None:
                from app.infra.tools.entries.append_call_event import append_call_event
                append_call_event(
                    call_id,
                    f"{event_prefix}.failed",
                    failed_payload,
                    effective_upload_folder,
                )
            # Release the in-flight lock so the retry can re-run (a failed op
            # writes no receipt; leaving the lock held would 409 the retry).
            await _release_idem_lock()
            raise

    # --- Failed ---
    if tool_error is not None:
        failed_payload = {
            "sid": sid,
            "rooms": effective_rooms,
            "call_id": str(emit_call_id),
            "group_id": str(effective_group_id) if effective_group_id else None,
            "run_id": str(run_id) if run_id else None,
            "operation_key": str(operation_key) if operation_key else None,
            "message": str(tool_error),
            "error_type": type(tool_error).__name__,
            "role": role,
            "tool": tool_payload,
        }
        await internal_sio.emit(f"{event_prefix}.failed", failed_payload)

        # Stamp the failure into the call receipt unconditionally,
        # independent of whether any output handler also calls
        # ``append_call_event`` for this event. The receipt is the
        # source-of-truth audit trail; failed events must always land
        # here so post-mortem ``jq`` queries find them.
        if call_upload_id is not None:
            from app.infra.tools.entries.append_call_event import append_call_event
            append_call_event(
                call_upload_id,
                f"{event_prefix}.failed",
                failed_payload,
                effective_upload_folder,
            )

        # Release the in-flight lock — the can_audit branch's failed result is
        # not cached for replay (we skip success=False receipts), so a retry
        # must be free to re-run rather than hit a stuck-lock 409.
        await _release_idem_lock()
        raise tool_error

    # --- Completed ---
    output = (
        result_data.model_dump(mode="json")
        if hasattr(result_data, "model_dump")
        else result_data
        if isinstance(result_data, dict)
        else {}
    )

    # Latest soft_calls_mv row for this call — the runner just inserted
    # one (or didn't, for non-soft writes). The black-box lookup is the
    # canonical place to surface ledger state to live consumers; the
    # persisted call JSON receipt picks the same fields up via the
    # standard ``append_call_event`` pipe. Read errors don't block the
    # event — ``ledger_status: None`` simply means "no entry found".
    ledger_status: str | None = None
    ledger_operation: str | None = None
    ledger_artifact: str | None = None
    ledger_artifact_id: str | None = None
    try:
        with timed("ledger"):
            from app.tools.entries.soft_calls.get import get_soft_call
            async with pool.acquire() as ledger_conn:
                entry = await get_soft_call(ledger_conn, emit_call_id, redis, artifact=artifact)
        if entry is not None:
            ledger_status = entry.status
            ledger_operation = entry.operation
            ledger_artifact = entry.artifact
            ledger_artifact_id = str(entry.artifact_id)
    except Exception:
        # Best-effort lookup — never block the .completed emit on a
        # ledger fetch failure.
        pass

    # See ``.started`` emit above for the ordering rationale — framework
    # identity fields trail the response spread so a runner that returns
    # ``call_id`` / ``group_id`` in its payload (e.g. group resolve) can't
    # accidentally clobber the audit's own row id. Uses ``emit_call_id``
    # (always set), not ``call_upload_id`` (None in the non-audit branch),
    # so the wire-level identity is consistent regardless of audit branch.
    with timed("completed_emit"):
        await internal_sio.emit(f"{event_prefix}.completed", {
            "sid": sid,
            "rooms": effective_rooms,
            "role": role,
            **output,
            "call_id": str(emit_call_id),
            "group_id": str(effective_group_id) if effective_group_id else None,
            "operation_key": str(operation_key) if operation_key else None,
            "tool": tool_payload,
            "ledger_status": ledger_status,
            "ledger_operation": ledger_operation,
            "ledger_artifact": ledger_artifact,
            "ledger_artifact_id": ledger_artifact_id,
        })

    # Idempotency bookkeeping on success — write the lightweight Redis receipt
    # on EVERY success, then drop the in-flight lock.
    #   • can_audit=False: it is the ONLY replay signal (no calls_entry at all).
    #   • can_audit=True (AU2): the calls_entry receipt that ``search_calls``
    #     replays is keyed on ``file_path``, but that path is written by the
    #     FIRE-AND-FORGET ``_persist_audit_writes`` task (create_tool_call) and
    #     is NOT durable when we release the lock here. A retry landing in that
    #     window finds the call with ``file_path=None`` (filtered out above),
    #     falls to the Redis-receipt branch, and — without this — finds nothing
    #     and RE-EXECUTES. Writing the Redis receipt unconditionally closes the
    #     window (and the failure-to-persist case); it is best-effort and
    #     no-ops on soft/error, so it is safe for the audited path too.
    await _write_redis_receipt(result_data)
    await _release_idem_lock()

    # Final receipt update — merge full per-phase timings + completed_at
    # into the .json receipt for forensic post-mortem by call_id.
    # Best-effort: file I/O errors don't block the response. Two-phase
    # write pattern: the initial receipt (in create_tool_call) captures
    # arguments + result; this final pass captures the full request
    # timing once the audit lifecycle has completed. If a crash happens
    # between the two phases, the absence of `timings_ms` in the file
    # signals "audit lifecycle didn't finish for this call_id".
    if call_upload_id is not None:
        try:
            from app.infra.server_timing import get_timings
            receipt_path = effective_upload_folder / "call" / f"{call_upload_id}.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["timings_ms"] = get_timings()
            receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
            # AU3: atomic write so a concurrent idempotency-replay reader never
            # observes a torn receipt mid-update (which would fail json.loads and
            # make the gate fall through to a duplicate execution).
            from app.utils.atomic_write import atomic_write_text
            atomic_write_text(
                receipt_path, json.dumps(receipt, indent=2, default=str),
            )
        except Exception as e:
            # O3: this write IS the signal meant to flag "audit lifecycle
            # didn't finish" — so a systematic failure here (disk full, perms,
            # corrupt receipt) silently degrades the forensic tool. Warn with
            # the call_upload_id so the gap is visible and attributable.
            logger.warning(
                "Best-effort receipt timing update failed for "
                "call_upload_id=%s (%s): %s",
                call_upload_id,
                type(e).__name__,
                e,
            )

    if response_model is not None:
        with timed("serialize"):
            return response_model.model_validate(result_data)
    return result_data


def build_audit_arguments(data: dict[str, Any]) -> dict[str, Any]:
    """Strip transport-only keys from an audited operation payload."""
    return {
        key: value
        for key, value in data.items()
        if key not in {"sid", "profile_id", "session_id"}
    }
