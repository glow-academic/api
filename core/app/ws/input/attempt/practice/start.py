"""Input: attempt.practice.start"""

from typing import Any

from app.infra.globals import sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.practice.start")  # type: ignore
async def attempt_practice_start(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return {"error": "Not authenticated"}

    try:
        from app.infra.attempt.practice_start import PracticeStartRequest, practice_start_impl
        from app.infra.globals import get_pool, get_redis_client

        pool = get_pool()
        redis = get_redis_client()

        request = PracticeStartRequest(**data)
        result = await practice_start_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=request,
        )

        return {
            "attempt_id": str(result.attempt_id),
            "chat_id": str(result.chat_id),
        }
    except Exception as e:
        return {"error": str(e)}
