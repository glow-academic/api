"""Check if a run has been cancelled."""

from app.infra.globals import get_redis_client


async def is_run_cancelled(run_id: str) -> bool:
    """Check if a run has been cancelled."""
    redis_client = get_redis_client()
    return bool(await redis_client.exists(f"cancel_run:{run_id}"))
