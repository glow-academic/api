"""Store an active run for potential cancellation."""

import uuid
from collections.abc import Awaitable, Callable

from app.infra.websocket.set_active_run import set_active_run


def generate_active_run_id() -> str:
    """Generate a run ID used for cooperative cancellation tracking."""
    return str(uuid.uuid4())


async def store_active_run(
    chat_id: str,
    run_result: object,
    *,
    run_id_factory: Callable[[], str] = generate_active_run_id,
    set_active_run_fn: Callable[[str, str], Awaitable[None]] = set_active_run,
) -> None:
    """Store an active run for potential cancellation"""
    # Generate a unique run ID for cooperative cancellation
    run_id = run_id_factory()
    await set_active_run_fn(chat_id, run_id)
