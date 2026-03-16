"""Find the profile ID owned by a socket ID."""

import contextvars

from app.infra.globals import get_redis_client, get_socket_owner_dict
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Recursion guard to prevent infinite recursion if Redis operations trigger callbacks
_recursion_guard: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_recursion_guard", default=False
)


async def find_profile_by_socket(socket_id: str) -> str | None:
    """Find the profile ID owned by a socket ID.

    Uses O(1) direct lookup via socket_to_profile:{socket_id} key.
    Falls back to in-memory dict, then scan_iter for backward compatibility.
    """
    # Recursion protection: if we're already in this function, use in-memory fallback
    if _recursion_guard.get():
        socket_owner = get_socket_owner_dict()
        for profile_id, sid in socket_owner.items():
            if sid == socket_id:
                return profile_id
        return None

    # Set recursion guard
    _recursion_guard.set(True)

    try:
        redis_client = get_redis_client()
        socket_owner = get_socket_owner_dict()

        if not redis_client:
            # Fallback to in-memory storage
            for profile_id, sid in socket_owner.items():
                if sid == socket_id:
                    return profile_id
            return None

        try:
            # First try: Direct O(1) lookup via reverse index
            profile_id_bytes = await redis_client.get(f"socket_to_profile:{socket_id}")
            if profile_id_bytes:
                return profile_id_bytes.decode("utf-8")

            # Second try: Fallback to in-memory dict (reverse lookup)
            for profile_id, sid in socket_owner.items():
                if sid == socket_id:
                    return profile_id

            # Third try: Fallback to scan_iter (for backward compatibility during migration)
            # This should rarely be needed if reverse index is properly maintained
            count = 0
            max_keys = 1000  # Safety limit
            async for key in redis_client.scan_iter(match="socket_owner:*"):
                count += 1
                if count > max_keys:
                    break
                owner_sid = await redis_client.get(key)
                if owner_sid and owner_sid.decode("utf-8") == socket_id:
                    profile_id = key.decode("utf-8").replace("socket_owner:", "")
                    return profile_id  # type: ignore
            return None

        except RecursionError:
            # Don't log with logger.error() as it might use Redis and cause more recursion
            # Fallback to in-memory storage
            for profile_id, sid in socket_owner.items():
                if sid == socket_id:
                    return profile_id
            return None
        except Exception as e:
            # Use print instead of logger.error() to avoid potential Redis recursion
            print(f"Redis error finding profile by socket {socket_id}: {e}", flush=True)
            # Fallback to in-memory storage
            for profile_id, sid in socket_owner.items():
                if sid == socket_id:
                    return profile_id
            return None
    finally:
        # Always clear recursion guard
        _recursion_guard.set(False)
