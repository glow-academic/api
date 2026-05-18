"""Remove a guest socket from Redis."""

from app.infra.globals import get_redis_client


async def remove_guest_socket(socket_id: str) -> None:
    """Remove a guest socket from Redis."""
    redis_client = get_redis_client()
    await redis_client.srem("guest_sockets", socket_id)
