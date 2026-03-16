"""Internal handler: test_proceed — canonical orchestration entry."""

from typing import Any

from app.infra.globals import get_pool, get_redis_client
from app.infra.test.workflows import test_proceed_impl
from app.infra.websocket.socket_event import EmitFn, make_emit


async def test_proceed_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
) -> None:
    """Run canonical test proceed orchestration for any surface."""
    await test_proceed_impl(
        data, emit=emit or make_emit(), pool=get_pool(), redis=get_redis_client()
    )
