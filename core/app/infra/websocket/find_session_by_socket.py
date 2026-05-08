"""Find the session ID for a socket ID."""

from app.infra.globals import get_redis_client


async def find_session_by_socket(socket_id: str) -> str | None:
    """Find the session ID for a socket ID via Redis.

    The session_id is stored at connect time in socket_session:{sid}.
    """
    redis_client = get_redis_client()
    session_id_bytes = await redis_client.get(f"socket_session:{socket_id}")
    if not session_id_bytes:
        return None
    return (
        session_id_bytes.decode("utf-8")
        if isinstance(session_id_bytes, bytes)
        else session_id_bytes
    )
