"""Initialize Redis generation trackers for a run.

Wraps the new run_tracker.init_run (work-unit state machine) and
the legacy generation_tracker init functions into one call with
redis as an explicit parameter for testability.

During migration, both old and new trackers are initialized so that
existing callers (generate_run_complete, generation_progress) continue
to work while new callers can use the work-unit model.
"""

from __future__ import annotations

from typing import Any

from app.infra.websocket.run_tracker import WorkUnit, init_run
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# TTL for generation tracking keys (1 hour)
GENERATION_TTL = 3600


async def init_run_trackers(
    redis: Any,
    *,
    run_id: str,
    num_agents: int,
    num_resources: int,
    units: list[WorkUnit] | None = None,
) -> None:
    """Initialize both legacy and new trackers for a run.

    When *units* is provided, the new work-unit tracker is also initialized.
    When *units* is None, only the legacy keys are set (backward compat).
    When redis is None, silently skips.
    """
    if not redis:
        return

    # --- Legacy keys (old generation_tracker consumers) ---
    gen_key = f"generation:{run_id}"
    res_key = f"resource_progress:{run_id}"

    try:
        pipe = redis.pipeline()
        pipe.hset(
            gen_key,
            mapping={
                "expected": str(num_agents),
                "completed": "0",
                "tool_results": "[]",
            },
        )
        pipe.expire(gen_key, GENERATION_TTL)
        pipe.hset(
            res_key,
            mapping={
                "total": str(num_resources),
                "completed": "0",
            },
        )
        pipe.expire(res_key, GENERATION_TTL)
        await pipe.execute()
    except Exception as e:
        logger.error(f"Redis error initializing legacy trackers for run {run_id}: {e}")

    # --- New work-unit tracker ---
    if units is not None:
        await init_run(
            redis,
            run_id=run_id,
            units=units,
            num_agents=num_agents,
        )
