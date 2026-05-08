"""MV refresh scheduler — debounced, multi-replica-safe via Redis.

One worker task per registered MV. Each task:
  1. Probes Redis for pending state (O(1)).
  2. Enforces per-MV interval via Redis next_run_at marker.
  3. Claims a Redis lock (SET NX EX) so only one replica runs at a time.
  4. Consumes the pending flag BEFORE running, so concurrent enqueues during
     the run re-set it and are picked up next iteration (no missed writes).
  5. Calls the existing per-target `refresh_X` primitive from
     `app.tools.entries.{target}.refresh` to actually run REFRESH MATERIALIZED
     VIEW CONCURRENTLY. No SQL is written here — this module only orchestrates.
  6. Stamps next_run_at and releases the lock.

Append-only audit rows in refreshes_entry are NOT read by the worker — they
are written by the request handlers via `tools.entries.refreshes.create_refresh`
purely for observability. Pending state is Redis-only and O(1) to check.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
import uuid
from typing import Awaitable, Callable

import asyncpg
from redis.asyncio import Redis

from app.utils.cache.mv_refresh_queue import (
    consume_pending,
    get_next_run_at_ms,
    has_pending,
    release_lock,
    set_next_run_at_ms,
    try_acquire_lock,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


# Refresh primitive contract — matches the existing per-target signatures
# in app.tools.entries.{target}.refresh (e.g. refresh_group_names).
RefreshFn = Callable[[asyncpg.Connection, Redis | None], Awaitable[object]]


class MVRefresher:
    """Lifespan-managed background scheduler for MV refreshes.

    Usage (inside FastAPI lifespan):
        refresher = MVRefresher(pool, redis)
        refresher.register("group_names_mv", refresh_group_names, interval_s=2.0)
        refresher.register("groups_mv",      refresh_groups,      interval_s=2.0)
        await stack.enter_async_context(refresher)
    """

    # How long a single refresh is allowed to run before its lock is force-
    # released. Tune above the slowest observed REFRESH duration for the
    # registered MVs. 60s is generous — observed runs are 50-130ms.
    LOCK_TTL_S: int = 60

    # Idle sleep when the queue is empty. Workers wake on this interval to
    # re-probe Redis for new pending work.
    IDLE_SLEEP_S: float = 1.0

    # Backoff when another replica holds the lock — keeps us from busy-looping
    # while the active replica completes.
    LOCK_BACKOFF_S: float = 0.5

    def __init__(self, pool: asyncpg.Pool, redis: Redis):
        self._pool = pool
        self._redis = redis
        self._registry: dict[str, tuple[RefreshFn, float]] = {}
        self._tasks: list[asyncio.Task] = []
        # Stable per-process worker id so lock release knows who owns it.
        # Includes pid for human-readability when debugging Redis state.
        self._worker_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

    # -- registration ------------------------------------------------------

    def register(
        self,
        target: str,
        refresh_fn: RefreshFn,
        *,
        interval_s: float,
    ) -> None:
        """Register an MV target with its refresh primitive and interval.

        Must be called BEFORE __aenter__. The refresh_fn is the existing
        black-box per-target primitive (e.g. refresh_group_names from
        app.tools.entries.group_names.refresh).
        """
        if target in self._registry:
            logger.warning(f"MVRefresher: re-registering {target}; overwriting")
        self._registry[target] = (refresh_fn, interval_s)

    # -- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> "MVRefresher":
        if not self._registry:
            logger.info("MVRefresher: no targets registered; idle")
            return self
        for target in self._registry:
            task = asyncio.create_task(
                self._worker_loop(target),
                name=f"mv-refresher:{target}",
            )
            self._tasks.append(task)
        logger.info(
            f"MVRefresher started: {len(self._tasks)} worker(s) "
            f"({', '.join(self._registry)}) — worker_id={self._worker_id}"
        )
        return self

    async def __aexit__(self, *_exc) -> None:
        if not self._tasks:
            return
        for task in self._tasks:
            task.cancel()
        # Bounded wait — tied into v2.15.12's lifespan shutdown timeout
        # contract. Workers awake from sleep, see CancelledError, return fast.
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info(f"MVRefresher stopped: {len(self._tasks)} worker(s)")
        self._tasks.clear()

    # -- worker ------------------------------------------------------------

    async def _worker_loop(self, target: str) -> None:
        refresh_fn, interval_s = self._registry[target]
        interval_ms = int(interval_s * 1000)
        # DEBUG (not INFO) — one line per registered MV at boot, ~60
        # MVs floods the startup log. Tick errors below stay at ERROR
        # because they're sparse + actionable.
        logger.debug(f"[mv-refresher:{target}] starting (interval={interval_s}s)")

        try:
            while True:
                try:
                    await self._tick(target, refresh_fn, interval_ms)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # One bad iteration shouldn't kill the worker — log and retry.
                    logger.error(
                        f"[mv-refresher:{target}] tick error: {e!r}",
                        exc_info=True,
                    )
                    await asyncio.sleep(self.IDLE_SLEEP_S)
        except asyncio.CancelledError:
            logger.debug(f"[mv-refresher:{target}] cancelled")
            raise

    async def _tick(
        self,
        target: str,
        refresh_fn: RefreshFn,
        interval_ms: int,
    ) -> None:
        # 1. Anything pending? O(1) Redis EXISTS.
        if not await has_pending(self._redis, target):
            await asyncio.sleep(self.IDLE_SLEEP_S)
            return

        # 2. Are we past the per-MV cooldown?
        now_ms = int(time.time() * 1000)
        next_run_at = await get_next_run_at_ms(self._redis, target)
        if now_ms < next_run_at:
            wait_s = (next_run_at - now_ms) / 1000.0
            await asyncio.sleep(wait_s)
            return

        # 3. Try to claim the cross-replica lock. If another replica is
        # mid-refresh, back off briefly and retry.
        got = await try_acquire_lock(
            self._redis, target, self._worker_id, self.LOCK_TTL_S
        )
        if not got:
            await asyncio.sleep(self.LOCK_BACKOFF_S)
            return

        try:
            # 4. Consume pending BEFORE running the refresh. Concurrent
            # enqueues during the refresh re-flip pending and get drained
            # next tick — no information loss.
            await consume_pending(self._redis, target)

            # 5. Run the existing per-target refresh primitive. The primitive
            # owns its own DB connection acquisition + cache invalidation.
            # Some primitives accept (conn, redis), others only (conn) — try
            # the rich signature first, fall back to bare conn on TypeError
            # so we don't have to keep the registry in lock-step with every
            # leaf primitive's signature drift.
            t0 = time.monotonic()
            async with self._pool.acquire() as conn:
                try:
                    await refresh_fn(conn, self._redis)
                except TypeError as e:
                    if "positional argument" in str(e) or "unexpected keyword" in str(e):
                        await refresh_fn(conn)
                    else:
                        raise
            duration_ms = int((time.monotonic() - t0) * 1000)
            # DEBUG (not INFO) — fires per-tick when pending work
            # exists; high-frequency MVs (groups_mv, runs_mv,
            # messages_mv at 2s interval) emit constantly.
            logger.debug(
                f"[mv-refresher:{target}] refreshed in {duration_ms}ms"
            )

            # 6. Stamp the next allowed start.
            await set_next_run_at_ms(self._redis, target, now_ms + interval_ms)
        finally:
            await release_lock(self._redis, target, self._worker_id)
