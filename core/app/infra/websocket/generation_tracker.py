"""Track multi-agent generation progress in Redis.

Redis-only — no in-memory fallback. Cross-replica counters must be
authoritative or the "all agents complete" signal is wrong.
"""

import json
from typing import Any

from app.infra.globals import get_redis_client

# TTL for generation tracking keys (1 hour).
GENERATION_TTL = 3600


async def init_generation(run_id: str, expected_agent_count: int) -> None:
    """Initialize generation tracking for a run."""
    redis_client = get_redis_client()
    key = f"generation:{run_id}"
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


async def record_agent_complete(
    run_id: str, tool_results: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]]]:
    """Record an agent completion. Returns (is_complete, all_tool_results)."""
    redis_client = get_redis_client()
    key = f"generation:{run_id}"

    pipe = redis_client.pipeline()
    pipe.hincrby(key, "completed", 1)
    pipe.hget(key, "expected")
    pipe.hget(key, "tool_results")
    results = await pipe.execute()

    completed = results[0]
    expected = int(results[1] or "1")
    existing_results: list[dict[str, Any]] = json.loads(results[2] or "[]")
    existing_results.extend(tool_results)

    await redis_client.hset(key, "tool_results", json.dumps(existing_results))
    return (completed >= expected, existing_results)


async def init_resource_progress(run_id: str, total_resources: int) -> None:
    """Initialize resource-level progress tracking for a run."""
    redis_client = get_redis_client()
    key = f"resource_progress:{run_id}"
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


async def record_resource_complete(run_id: str, resource_type: str) -> tuple[int, int]:
    """Record a resource completion. Returns (completed, total)."""
    redis_client = get_redis_client()
    key = f"resource_progress:{run_id}"

    pipe = redis_client.pipeline()
    pipe.hincrby(key, "completed", 1)
    pipe.hget(key, "total")
    results = await pipe.execute()

    completed = results[0]
    total = int(results[1] or "1")
    return (completed, total)


async def cleanup_generation(run_id: str) -> None:
    """Clean up generation tracking data."""
    redis_client = get_redis_client()
    await redis_client.delete(f"generation:{run_id}", f"resource_progress:{run_id}")
