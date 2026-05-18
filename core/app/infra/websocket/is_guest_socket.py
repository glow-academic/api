"""Check if a socket is a guest socket."""

from app.infra.globals import get_redis_client


async def is_guest_socket(socket_id: str) -> bool:
    """Check if a socket is a guest socket."""
    redis_client = get_redis_client()
    return bool(await redis_client.sismember("guest_sockets", socket_id))
