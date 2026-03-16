"""Internal handler: attempt_proceed — canonical orchestration entry."""

from typing import Any
from uuid import UUID

from app.infra.attempt.workflows import attempt_proceed_impl
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, make_emit
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


async def attempt_proceed_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
) -> None:
    """Run canonical attempt proceed orchestration for any surface."""
    sid = data.get("sid", "")
    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        logger.warning("No profile_id for attempt_proceed")
        return

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        return

    pool = get_pool()
    redis = get_redis_client()
    identity = await resolve_profile_identity_context(
        pool,
        UUID(profile_id),
        redis,
        bypass_cache=True,
        session_id=UUID(session_id),
    )
    profiles_id = identity.profiles_id if identity else None

    await attempt_proceed_impl(
        data,
        emit=emit or make_emit(),
        pool=pool,
        redis=redis,
        profile_id=profile_id,
        session_id=session_id,
        profiles_id=profiles_id,
    )
