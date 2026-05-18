"""MV refresh queue primitives — Redis-backed, append-only DB audit.

Three keys per MV target:
  mv:pending:{target}      string ("1") — set by enqueue, deleted by worker
                                          before running. Existence = "queue
                                          non-empty". Survives across replicas.
  mv:lock:{target}          string (worker_id), TTL = max-runtime — held by
                                          whichever replica is currently
                                          executing the refresh. Self-heals
                                          via TTL if the worker crashes.
  mv:next_run_at:{target}   string (epoch ms) — earliest time the next refresh
                                          is allowed to start. Set on every
                                          successful run.

Append-only audit lives in `refreshes_entry` via the existing
`tools.entries.refreshes.create_refresh` primitive — never edited.
This module only mediates Redis. Workers read pending state in O(1) via
EXISTS, claim runs via SET NX EX, and do not touch the DB-level audit log.
"""

from __future__ import annotations

from redis.asyncio import Redis


def _pending_key(target: str) -> str:
    return f"mv:pending:{target}"


def _lock_key(target: str) -> str:
    return f"mv:lock:{target}"


def _next_run_key(target: str) -> str:
    return f"mv:next_run_at:{target}"


async def enqueue_pending(redis: Redis, target: str) -> None:
    """Mark target as having pending work.

    Uses SET NX so concurrent enqueues collapse into a single pending flag —
    one worker drain handles N enqueues. The flag persists until the worker
    consumes it (DEL before running the refresh, so any new enqueue mid-run
    re-sets the flag and is picked up next iteration — no missed writes).
    """
    await redis.set(_pending_key(target), "1", nx=True)


async def has_pending(redis: Redis, target: str) -> bool:
    """O(1) probe — is the queue for this target non-empty?"""
    return bool(await redis.exists(_pending_key(target)))


async def consume_pending(redis: Redis, target: str) -> bool:
    """Atomically clear the pending flag. Returns True if it was set.

    Called by the worker BEFORE it runs the refresh, so any concurrent
    enqueue during the run rewrites the flag and is processed next cycle.
    """
    return bool(await redis.delete(_pending_key(target)))


async def try_acquire_lock(
    redis: Redis, target: str, worker_id: str, ttl_s: int
) -> bool:
    """Atomic SET NX EX. Returns True iff this caller now owns the lock.

    TTL self-heals after worker crash; a new worker can claim once the TTL
    expires. Choose ttl_s to be a small multiple of expected refresh runtime.
    """
    res = await redis.set(_lock_key(target), worker_id, nx=True, ex=ttl_s)
    return bool(res)


async def release_lock(redis: Redis, target: str, worker_id: str) -> None:
    """Release the lock if and only if we still own it.

    Avoids a race where our TTL expired, another worker claimed the lock,
    and we then DELETE theirs. Compare-and-delete via Lua, atomic.
    """
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] "
        "then return redis.call('del', KEYS[1]) "
        "else return 0 end"
    )
    await redis.eval(script, 1, _lock_key(target), worker_id)


async def get_next_run_at_ms(redis: Redis, target: str) -> int:
    """Earliest epoch ms when the next refresh is allowed. 0 = run now."""
    raw = await redis.get(_next_run_key(target))
    if raw is None:
        return 0
    return int(raw.decode() if isinstance(raw, bytes) else raw)


async def set_next_run_at_ms(redis: Redis, target: str, at_ms: int) -> None:
    """Stamp the earliest allowed start time for the next refresh."""
    # No TTL — this stays until next overwrite. Long-lived per MV.
    await redis.set(_next_run_key(target), str(at_ms))
