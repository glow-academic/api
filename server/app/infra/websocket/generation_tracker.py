"""Track multi-agent generation progress in Redis.

Follows the set_active_run.py pattern: get_redis_client(), null guard, TTL.
Falls back to an in-memory dict when Redis is unavailable.
"""

import json
from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# In-memory fallback when Redis is unavailable
_fallback_store: dict[str, dict[str, Any]] = {}

# TTL for generation tracking keys (1 hour)
GENERATION_TTL = 3600


async def init_generation(run_id: str, expected_agent_count: int) -> None:
    """Initialize generation tracking for a run.

    Sets up a Redis hash with expected agent count and empty results.
    """
    redis_client = get_redis_client()
    key = f"generation:{run_id}"

    if not redis_client:
        _fallback_store[key] = {
            "expected": expected_agent_count,
            "completed": 0,
            "tool_results": [],
        }
        return

    try:
        pipe = redis_client.pipeline()
        pipe.hset(
            key,
            mapping={
                "expected": str(expected_agent_count),
                "completed": "0",
                "tool_results": "[]",
            },
        )
        pipe.expire(key, GENERATION_TTL)
        await pipe.execute()
    except Exception as e:
        logger.error(f"Redis error initializing generation for run {run_id}: {e}")
        _fallback_store[key] = {
            "expected": expected_agent_count,
            "completed": 0,
            "tool_results": [],
        }


async def record_agent_complete(
    run_id: str, tool_results: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]]]:
    """Record an agent completion and return whether all agents are done.

    Returns (is_complete, all_tool_results).
    """
    redis_client = get_redis_client()
    key = f"generation:{run_id}"

    if not redis_client:
        entry = _fallback_store.get(key)
        if not entry:
            return (True, tool_results)
        entry["completed"] += 1
        entry["tool_results"].extend(tool_results)
        is_complete = entry["completed"] >= entry["expected"]
        return (is_complete, entry["tool_results"])

    try:
        pipe = redis_client.pipeline()
        pipe.hincrby(key, "completed", 1)
        pipe.hget(key, "expected")
        pipe.hget(key, "tool_results")
        results = await pipe.execute()

        completed = results[0]  # HINCRBY returns new value
        expected = int(results[1] or "1")
        existing_results: list[dict[str, Any]] = json.loads(results[2] or "[]")
        existing_results.extend(tool_results)

        # Update stored tool_results
        await redis_client.hset(key, "tool_results", json.dumps(existing_results))

        is_complete = completed >= expected
        return (is_complete, existing_results)
    except Exception as e:
        logger.error(f"Redis error recording agent complete for run {run_id}: {e}")
        return (True, tool_results)


async def init_resource_progress(run_id: str, total_resources: int) -> None:
    """Initialize resource-level progress tracking for a run.

    Tracks how many individual resources have completed out of total.
    """
    redis_client = get_redis_client()
    key = f"resource_progress:{run_id}"

    if not redis_client:
        _fallback_store[key] = {"total": total_resources, "completed": 0}
        return

    try:
        pipe = redis_client.pipeline()
        pipe.hset(
            key,
            mapping={
                "total": str(total_resources),
                "completed": "0",
            },
        )
        pipe.expire(key, GENERATION_TTL)
        await pipe.execute()
    except Exception as e:
        logger.error(
            f"Redis error initializing resource progress for run {run_id}: {e}"
        )
        _fallback_store[key] = {"total": total_resources, "completed": 0}


async def record_resource_complete(run_id: str, resource_type: str) -> tuple[int, int]:
    """Record a resource completion. Returns (completed, total)."""
    redis_client = get_redis_client()
    key = f"resource_progress:{run_id}"

    if not redis_client:
        entry = _fallback_store.get(key)
        if not entry:
            return (1, 1)
        entry["completed"] += 1
        return (entry["completed"], entry["total"])

    try:
        pipe = redis_client.pipeline()
        pipe.hincrby(key, "completed", 1)
        pipe.hget(key, "total")
        results = await pipe.execute()

        completed = results[0]  # HINCRBY returns new value
        total = int(results[1] or "1")
        return (completed, total)
    except Exception as e:
        logger.error(f"Redis error recording resource complete for run {run_id}: {e}")
        return (1, 1)


async def cleanup_generation(run_id: str) -> None:
    """Clean up generation tracking data."""
    redis_client = get_redis_client()
    key = f"generation:{run_id}"
    resource_key = f"resource_progress:{run_id}"

    _fallback_store.pop(key, None)
    _fallback_store.pop(resource_key, None)

    if not redis_client:
        return

    try:
        await redis_client.delete(key, resource_key)
    except Exception as e:
        logger.error(f"Redis error cleaning up generation for run {run_id}: {e}")
