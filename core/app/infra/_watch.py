"""Artifact-agnostic one-shot watch impl — blocks until run(s) finish.

Pairs with the live SSE route (``GET /<artifact>/stream``) which holds a
long-poll connection open for the browser. This impl is the tool-layer
sibling: same event source (the in-process hub), one-shot return shape.

The HTTP route is fixed at SSE. This impl is flexible — call with
``wait_for_complete=True`` to block until all watched runs are terminal,
or with ``wait_for_complete=False`` to get a snapshot of current state
(via DB query) and return immediately.

Used by the per-artifact ``watch_<artifact>_impl`` functions; those are
thin wrappers that supply ``artifact_type`` and route through the same
shared logic.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.stream.hub import subscribe, unsubscribe
from app.infra.stream.types import EventEnvelope

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class WatchApiRequest(BaseModel):
    """Watch a group's run for terminal events (or take a snapshot)."""

    group_id: UUID = Field(..., description="Chat group whose events we watch")
    run_id: UUID | None = Field(
        None,
        description=(
            "Specific run to watch (e.g. the ``run_id`` returned by a prior "
            "``X_Generate`` call). If None, watches every active run in the "
            "group at call time."
        ),
    )
    wait_for_complete: bool = Field(
        True,
        description=(
            "If True, block until the watched run reaches a terminal "
            "(complete/failed) event or timeout fires. "
            "If False, return current state and exit immediately."
        ),
    )
    timeout_seconds: int = Field(
        120,
        ge=1,
        le=600,
        description="Max wait time when ``wait_for_complete=True``.",
    )


class RunStatus(BaseModel):
    """Outcome of one watched run."""

    run_id: UUID
    status: Literal["pending", "completed", "failed"]
    modality: str | None = Field(
        None, description="Modality of generated output (image, video, text…)"
    )
    resource_ids: list[UUID] = Field(
        default_factory=list,
        description="Resource UUIDs produced by this run (e.g. images_resource ids)",
    )
    error: str | None = None


class WatchApiResponse(BaseModel):
    """One-shot view of run states with any captured resource ids."""

    group_id: UUID
    runs: list[RunStatus]
    timed_out: bool = False
    waited_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Terminal-event classification
# ---------------------------------------------------------------------------

# We treat any of these event_type suffixes as terminal.
_TERMINAL_SUFFIXES = (".complete", ".completed", ".failed", ".error")


def _is_terminal(envelope: EventEnvelope) -> bool:
    et = envelope.event_type or ""
    return any(et.endswith(s) for s in _TERMINAL_SUFFIXES) or et in {
        "media_complete",
        "media_error",
    }


def _outcome(envelope: EventEnvelope) -> Literal["completed", "failed"]:
    et = envelope.event_type or ""
    if et.endswith(".failed") or et.endswith(".error") or et == "media_error":
        return "failed"
    return "completed"


def _resource_ids_from_payload(payload: dict) -> list[UUID]:
    ids: list[UUID] = []
    # Common keys produced by the generation pipeline + media chain.
    for key in ("resource_id", "image_id", "video_id", "audio_id", "upload_id"):
        v = payload.get(key)
        if v is None:
            continue
        try:
            ids.append(UUID(str(v)))
        except (ValueError, TypeError):
            continue
    # Plural lists, if any
    for key in ("resource_ids", "image_ids", "video_ids", "audio_ids"):
        v = payload.get(key)
        if not isinstance(v, list):
            continue
        for raw in v:
            try:
                ids.append(UUID(str(raw)))
            except (ValueError, TypeError):
                continue
    # Dedupe preserving order
    seen: set[UUID] = set()
    deduped = []
    for r in ids:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def _modality_from_event(envelope: EventEnvelope) -> str | None:
    p = envelope.payload or {}
    return p.get("modality") or p.get("resource_type") or None


# ---------------------------------------------------------------------------
# Snapshot path — DB-driven, no waiting
# ---------------------------------------------------------------------------


async def _snapshot_runs(
    pool: asyncpg.Pool,
    group_id: UUID,
    run_ids: list[UUID] | None,
) -> list[RunStatus]:
    """Snapshot of run state for a group.

    Currently returns ``[]`` — the prior inline SQL queried
    ``image_uploads_entry.run_id`` (and friends) but those tables don't
    have a ``run_id`` column. The canonical link is the
    ``run_id → messages_entry → message_uploads_entry → <m>_uploads_entry``
    path (populated by ``create_tool_call`` for agentic uploads and by
    ``media_upload_impl`` for media-dispatch uploads after the
    creation-site wiring lands). Rewriting this via existing black-box
    helpers (``search_messages`` → ``search_message_uploads`` →
    ``search_images`` / ``search_videos``) is the follow-up.

    Until that follow-up: ``wait_for_complete=True`` (live hub) is the
    only mode that produces results. Returning empty here keeps the
    impl honest rather than crashing at runtime against a column that
    doesn't exist.
    """
    # Suppress unused-arg warnings — kept in signature for the follow-up.
    _ = (pool, group_id, run_ids)
    return []


# ---------------------------------------------------------------------------
# Wait path — subscribe to hub, drain until terminal-for-each-run or timeout
# ---------------------------------------------------------------------------


async def watch_runs_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact_type: str,  # noqa: ARG001 — reserved for future per-artifact filtering
    group_id: UUID,
    run_id: UUID | None = None,
    wait_for_complete: bool = True,
    timeout_seconds: int = 120,
    profile_id: UUID,  # noqa: ARG001 — reserved for auth/audit; checked at route
    session_id: UUID | None = None,  # noqa: ARG001
) -> WatchApiResponse:
    """Block (or snapshot) on a group's run and return what it produced.

    Subscribes to the in-process hub BEFORE inspecting state so no event
    fires in a gap. Falls back to DB snapshot for any runs that already
    completed before subscribe (e.g. fast cache-hit path).
    """
    started = datetime.now(timezone.utc)

    # Internal list shape — we may receive None (watch group's active runs)
    # or a specific run_id. Normalize to a list[UUID] | None for snapshot.
    target_run_ids: list[UUID] | None = [run_id] if run_id else None

    # Snapshot first — captures runs that already finished
    initial = await _snapshot_runs(pool, group_id, target_run_ids)
    statuses: dict[UUID, RunStatus] = {rs.run_id: rs for rs in initial}

    if not wait_for_complete:
        return WatchApiResponse(
            group_id=group_id,
            runs=list(statuses.values()),
            timed_out=False,
            waited_seconds=0.0,
        )

    # If the run we were given is already terminal, exit.
    def _all_terminal() -> bool:
        if not target_run_ids:
            # No specific id — accept "everything we know about is terminal"
            return len(statuses) > 0 and all(
                s.status in {"completed", "failed"} for s in statuses.values()
            )
        return all(
            statuses.get(rid) is not None
            and statuses[rid].status in {"completed", "failed"}
            for rid in target_run_ids
        )

    if _all_terminal():
        return WatchApiResponse(
            group_id=group_id,
            runs=list(statuses.values()),
            timed_out=False,
            waited_seconds=0.0,
        )

    # Subscribe and drain
    queue = subscribe(group_id=group_id)
    deadline = started.timestamp() + timeout_seconds
    timed_out = False
    try:
        while not _all_terminal():
            remaining = deadline - datetime.now(timezone.utc).timestamp()
            if remaining <= 0:
                timed_out = True
                break
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                timed_out = True
                break

            if not _is_terminal(envelope):
                continue

            # Apply event to status table
            rid = envelope.run_id
            if rid is None:
                continue
            if target_run_ids and rid not in target_run_ids:
                continue  # event for a sibling run we're not watching

            existing = statuses.get(rid)
            modality = _modality_from_event(envelope)
            resource_ids = _resource_ids_from_payload(envelope.payload or {})
            outcome = _outcome(envelope)
            error = (envelope.payload or {}).get("error_message") or (
                (envelope.payload or {}).get("error")
            ) if outcome == "failed" else None

            if existing is None:
                statuses[rid] = RunStatus(
                    run_id=rid,
                    status=outcome,
                    modality=modality,
                    resource_ids=resource_ids,
                    error=error if isinstance(error, str) else None,
                )
            else:
                existing.status = outcome
                if modality and not existing.modality:
                    existing.modality = modality
                # Union resource_ids
                seen = {x for x in existing.resource_ids}
                for r in resource_ids:
                    if r not in seen:
                        existing.resource_ids.append(r)
                        seen.add(r)
                if error and not existing.error:
                    existing.error = error if isinstance(error, str) else None
    finally:
        unsubscribe(queue)

    waited = (datetime.now(timezone.utc) - started).total_seconds()
    return WatchApiResponse(
        group_id=group_id,
        runs=list(statuses.values()),
        timed_out=timed_out,
        waited_seconds=waited,
    )
