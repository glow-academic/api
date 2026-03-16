"""Track multi-agent generation progress with per-unit state machine.

Each run has N work units (resource, entry, or artifact operations) assigned
to agents.  Units follow a state machine:

    generating → soft → active   (happy path: create → tentative → promoted)
    generating → soft → failed   (resolution rejects)
    generating → failed          (tool execution error)

Redis layout (two hashes per run, shared TTL):

    run:{run_id}:meta  → { num_agents, completed_agents, tool_results }
    run:{run_id}:units → { "{agent_id}:{target_type}:{target_name}" → JSON }

The old generation_tracker.py is left in place — callers migrate incrementally.

TODOs (input modality & resolution):
    - TODO: Resolve agent input modalities from model → modalities_resource (is_input)
            and pass to post_process_media_sentinels in generate_prepare.
    - TODO: Persist multipart messages (text + image blocks) instead of text-only
            in persist_run_message when input modality includes non-text media.
    - Resolution phase implemented: find_contested_targets / find_uncontested_targets
            + promote_unit / fail_unit wired in generate_run_complete_new + generation_ended.
    - TODO: Build entry_actions alongside resource_actions in generate_run_complete
            (currently only resource_type/resource_id are extracted from tool_results).
    - TODO: Emit per-unit modality metadata in generation_channel progress events
            so the client can show "Generating images…" vs "Generating text…".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# TTL for all run tracking keys (1 hour).
RUN_TTL = 3600

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

VALID_STATES = frozenset({"generating", "soft", "active", "failed"})
VALID_TARGET_TYPES = frozenset({"resource", "entry", "artifact"})


@dataclass(frozen=True)
class WorkUnit:
    """A single piece of work dispatched to an agent."""

    agent_id: str
    target_type: str  # "resource" | "entry" | "artifact"
    target_name: str  # e.g. "images", "contents", "persona"
    modality: str | None = None  # output modality hint


@dataclass(frozen=True)
class UnitState:
    """Snapshot of a single work unit's progress."""

    state: str  # generating | soft | active | failed
    result_id: str | None = None
    modality: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunStatus:
    """Aggregate status for an entire run."""

    total_units: int
    generating: int
    soft: int
    active: int
    failed: int
    num_agents: int
    completed_agents: int
    all_agents_done: bool
    tool_results: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------


def _meta_key(run_id: str) -> str:
    return f"run:{run_id}:meta"


def _units_key(run_id: str) -> str:
    return f"run:{run_id}:units"


def _unit_field(unit: WorkUnit) -> str:
    return f"{unit.agent_id}:{unit.target_type}:{unit.target_name}"


def _unit_field_raw(agent_id: str, target_type: str, target_name: str) -> str:
    return f"{agent_id}:{target_type}:{target_name}"


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------

_fallback: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def init_run(
    redis: Any,
    *,
    run_id: str,
    units: list[WorkUnit],
    num_agents: int | None = None,
) -> None:
    """Register all work units for a run.

    ``num_agents`` defaults to the number of distinct agent_ids in *units*.
    """
    agent_ids = {u.agent_id for u in units}
    effective_agents = num_agents if num_agents is not None else len(agent_ids)

    unit_map: dict[str, str] = {}
    for u in units:
        state = UnitState(state="generating", modality=u.modality)
        unit_map[_unit_field(u)] = json.dumps(
            {
                "state": state.state,
                "result_id": state.result_id,
                "modality": state.modality,
                "metadata": state.metadata,
            }
        )

    meta = {
        "num_agents": str(effective_agents),
        "completed_agents": "0",
        "tool_results": "[]",
    }

    if not redis:
        _fallback[_meta_key(run_id)] = {
            "num_agents": effective_agents,
            "completed_agents": 0,
            "tool_results": [],
        }
        _fallback[_units_key(run_id)] = {k: json.loads(v) for k, v in unit_map.items()}
        return

    try:
        pipe = redis.pipeline()
        mk = _meta_key(run_id)
        uk = _units_key(run_id)
        # Clear previous state if re-initializing
        pipe.delete(mk, uk)
        if meta:
            pipe.hset(mk, mapping=meta)
        pipe.expire(mk, RUN_TTL)
        if unit_map:
            pipe.hset(uk, mapping=unit_map)
        pipe.expire(uk, RUN_TTL)
        await pipe.execute()
    except Exception as e:
        logger.error(f"Redis error in init_run for {run_id}: {e}")
        _fallback[_meta_key(run_id)] = {
            "num_agents": effective_agents,
            "completed_agents": 0,
            "tool_results": [],
        }
        _fallback[_units_key(run_id)] = {k: json.loads(v) for k, v in unit_map.items()}


async def record_unit_soft(
    redis: Any,
    *,
    run_id: str,
    agent_id: str,
    target_type: str,
    target_name: str,
    result_id: str | None = None,
    modality: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Transition a unit from generating → soft.

    Returns ``(completed_units, total_units)`` where completed means
    any state other than *generating*.
    """
    fld = _unit_field_raw(agent_id, target_type, target_name)
    new_state = json.dumps(
        {
            "state": "soft",
            "result_id": result_id,
            "modality": modality,
            "metadata": metadata or {},
        }
    )

    if not redis:
        units = _fallback.get(_units_key(run_id), {})
        units[fld] = json.loads(new_state)
        total = len(units)
        completed = sum(1 for v in units.values() if v["state"] != "generating")
        return (completed, total)

    try:
        pipe = redis.pipeline()
        pipe.hset(_units_key(run_id), fld, new_state)
        pipe.hgetall(_units_key(run_id))
        results = await pipe.execute()
        all_units: dict[bytes, bytes] = results[1]
        total = len(all_units)
        completed = 0
        for v in all_units.values():
            parsed = json.loads(v)
            if parsed["state"] != "generating":
                completed += 1
        return (completed, total)
    except Exception as e:
        logger.error(f"Redis error in record_unit_soft for {run_id}: {e}")
        return (1, 1)


async def promote_unit(
    redis: Any,
    *,
    run_id: str,
    agent_id: str,
    target_type: str,
    target_name: str,
) -> None:
    """Transition a unit from soft → active (resolution winner)."""
    fld = _unit_field_raw(agent_id, target_type, target_name)

    if not redis:
        units = _fallback.get(_units_key(run_id), {})
        if fld in units:
            units[fld]["state"] = "active"
        return

    try:
        raw = await redis.hget(_units_key(run_id), fld)
        if not raw:
            return
        data = json.loads(raw)
        data["state"] = "active"
        await redis.hset(_units_key(run_id), fld, json.dumps(data))
    except Exception as e:
        logger.error(f"Redis error in promote_unit for {run_id}: {e}")


async def fail_unit(
    redis: Any,
    *,
    run_id: str,
    agent_id: str,
    target_type: str,
    target_name: str,
) -> None:
    """Transition a unit to failed (resolution loser or execution error)."""
    fld = _unit_field_raw(agent_id, target_type, target_name)

    if not redis:
        units = _fallback.get(_units_key(run_id), {})
        if fld in units:
            units[fld]["state"] = "failed"
        return

    try:
        raw = await redis.hget(_units_key(run_id), fld)
        if not raw:
            return
        data = json.loads(raw)
        data["state"] = "failed"
        await redis.hset(_units_key(run_id), fld, json.dumps(data))
    except Exception as e:
        logger.error(f"Redis error in fail_unit for {run_id}: {e}")


async def record_agent_done(
    redis: Any,
    *,
    run_id: str,
    tool_results: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    """Record that one agent has finished.  Returns (all_done, all_tool_results).

    Drop-in replacement for the old ``record_agent_complete``.
    """
    if not redis:
        meta = _fallback.get(_meta_key(run_id))
        if not meta:
            return (True, tool_results)
        meta["completed_agents"] += 1
        meta["tool_results"].extend(tool_results)
        return (
            meta["completed_agents"] >= meta["num_agents"],
            meta["tool_results"],
        )

    try:
        mk = _meta_key(run_id)
        pipe = redis.pipeline()
        pipe.hincrby(mk, "completed_agents", 1)
        pipe.hget(mk, "num_agents")
        pipe.hget(mk, "tool_results")
        results = await pipe.execute()

        completed = results[0]
        expected = int(results[1] or "1")
        existing: list[dict[str, Any]] = json.loads(results[2] or "[]")
        existing.extend(tool_results)

        await redis.hset(mk, "tool_results", json.dumps(existing))
        return (completed >= expected, existing)
    except Exception as e:
        logger.error(f"Redis error in record_agent_done for {run_id}: {e}")
        return (True, tool_results)


async def get_run_status(
    redis: Any,
    *,
    run_id: str,
) -> RunStatus:
    """Return aggregate status snapshot for a run."""
    if not redis:
        meta = _fallback.get(_meta_key(run_id), {})
        units = _fallback.get(_units_key(run_id), {})
        counts = _count_states(units.values())
        na = meta.get("num_agents", 0)
        ca = meta.get("completed_agents", 0)
        return RunStatus(
            total_units=len(units),
            **counts,
            num_agents=na,
            completed_agents=ca,
            all_agents_done=ca >= na if na else True,
            tool_results=meta.get("tool_results", []),
        )

    try:
        pipe = redis.pipeline()
        pipe.hgetall(_meta_key(run_id))
        pipe.hgetall(_units_key(run_id))
        results = await pipe.execute()

        raw_meta: dict[bytes, bytes] = results[0]
        raw_units: dict[bytes, bytes] = results[1]

        na = int(raw_meta.get(b"num_agents", b"0"))
        ca = int(raw_meta.get(b"completed_agents", b"0"))
        tool_results = json.loads(raw_meta.get(b"tool_results", b"[]"))

        parsed_units = [json.loads(v) for v in raw_units.values()]
        counts = _count_states(parsed_units)

        return RunStatus(
            total_units=len(raw_units),
            **counts,
            num_agents=na,
            completed_agents=ca,
            all_agents_done=ca >= na if na else True,
            tool_results=tool_results,
        )
    except Exception as e:
        logger.error(f"Redis error in get_run_status for {run_id}: {e}")
        return RunStatus(
            total_units=0,
            generating=0,
            soft=0,
            active=0,
            failed=0,
            num_agents=0,
            completed_agents=0,
            all_agents_done=True,
            tool_results=[],
        )


async def get_all_units(
    redis: Any,
    *,
    run_id: str,
) -> dict[str, UnitState]:
    """Return all units for a run: {field_key: UnitState}.

    Field key format: ``{agent_id}:{target_type}:{target_name}``.
    """
    if not redis:
        raw = _fallback.get(_units_key(run_id), {})
        return {
            k: UnitState(
                state=v["state"],
                result_id=v.get("result_id"),
                modality=v.get("modality"),
                metadata=v.get("metadata", {}),
            )
            for k, v in raw.items()
        }

    try:
        raw_units: dict[bytes, bytes] = await redis.hgetall(_units_key(run_id))
        result: dict[str, UnitState] = {}
        for k, v in raw_units.items():
            key = k.decode() if isinstance(k, bytes) else k
            parsed = json.loads(v)
            result[key] = UnitState(
                state=parsed["state"],
                result_id=parsed.get("result_id"),
                modality=parsed.get("modality"),
                metadata=parsed.get("metadata", {}),
            )
        return result
    except Exception as e:
        logger.error(f"Redis error in get_all_units for {run_id}: {e}")
        return {}


def find_contested_targets(
    units: dict[str, UnitState],
) -> dict[tuple[str, str], list[tuple[str, UnitState]]]:
    """Group soft units by (target_type, target_name) → [(agent_id, UnitState)].

    Returns only targets with >1 competing agent (contested).
    """
    by_target: dict[tuple[str, str], list[tuple[str, UnitState]]] = {}
    for field_key, state in units.items():
        if state.state != "soft":
            continue
        parts = field_key.split(":", 2)
        if len(parts) != 3:
            continue
        agent_id, target_type, target_name = parts
        key = (target_type, target_name)
        by_target.setdefault(key, []).append((agent_id, state))

    return {k: v for k, v in by_target.items() if len(v) > 1}


def find_uncontested_targets(
    units: dict[str, UnitState],
) -> dict[tuple[str, str], tuple[str, UnitState]]:
    """Return soft units with exactly 1 competing agent (uncontested).

    Returns {(target_type, target_name): (agent_id, UnitState)}.
    """
    by_target: dict[tuple[str, str], list[tuple[str, UnitState]]] = {}
    for field_key, state in units.items():
        if state.state != "soft":
            continue
        parts = field_key.split(":", 2)
        if len(parts) != 3:
            continue
        agent_id, target_type, target_name = parts
        key = (target_type, target_name)
        by_target.setdefault(key, []).append((agent_id, state))

    return {k: v[0] for k, v in by_target.items() if len(v) == 1}


async def cleanup_run(
    redis: Any,
    *,
    run_id: str,
) -> None:
    """Delete all tracking state for a run."""
    _fallback.pop(_meta_key(run_id), None)
    _fallback.pop(_units_key(run_id), None)

    if not redis:
        return

    try:
        await redis.delete(_meta_key(run_id), _units_key(run_id))
    except Exception as e:
        logger.error(f"Redis error in cleanup_run for {run_id}: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_states(
    units: Any,
) -> dict[str, int]:
    """Count units per state.  *units* is an iterable of dicts with a 'state' key."""
    counts = {"generating": 0, "soft": 0, "active": 0, "failed": 0}
    for u in units:
        s = u["state"] if isinstance(u, dict) else u.get("state", "generating")
        if s in counts:
            counts[s] += 1
    return counts
