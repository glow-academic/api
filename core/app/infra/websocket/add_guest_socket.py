"""Add a guest socket to Redis."""

from app.infra.globals import get_redis_client


async def add_guest_socket(socket_id: str) -> None:
    """Add a guest socket to Redis."""
    redis_client = get_redis_client()
    await redis_client.sadd("guest_sockets", socket_id)
