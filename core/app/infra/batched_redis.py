"""BatchedRedis — automatic per-tick MGET batching for Redis GET calls.

Wraps an ``redis.asyncio.Redis`` client so that every ``await client.get(k)``
within a single event-loop turn is collected into a list of pending keys.
At the next ``await asyncio.sleep(0)`` boundary the wrapper fires ONE
``MGET`` for the whole batch and resolves each caller's awaited future
with its result.

The application code is unchanged — ``await redis.get(key)`` still looks
like a single get. Only the wire pattern changes: where the underlying
client previously issued N sequential round-trips, it now issues O(1)
round-trips per asyncio "tick", proportional to the number of concurrent
gets (e.g. from an ``asyncio.gather``).

Why this exists
---------------
Measured Sep 2026 on ``/persona/get`` (warm cache, university seed):
  - ``inner_get_persona_impl`` ≈ 50 ms (~50% of total wall clock)
  - ``audit_overhead`` ≈ 50 ms
  - cache log: ~76 cache HITS per request, ZERO writes on the warm path
  - 76 redis round-trips * ~1 ms each = the 80–100 ms floor
The 23-way ``asyncio.gather`` parallelises Python coroutines, but each
``redis.get`` still round-trips to redis sequentially on its connection.
This wrapper recovers the parallelism at the wire layer.

Operations that are NOT batched (pass through unchanged via ``__getattr__``)
include set/setex/expire/delete/pipeline/eval — they have side-effects or
are stateful and don't benefit from coalescing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class BatchedRedis:
    """Drop-in wrapper over an ``redis.asyncio.Redis`` client that auto-
    coalesces concurrent ``.get(key)`` awaits into one ``MGET`` per tick.

    Constructor takes the real client; everything else delegates.
    Thread-safety: not thread-safe (only one event loop accesses it at
    a time), which matches the underlying redis client's contract.
    """

    def __init__(self, client: Any) -> None:
        # ``client`` is an ``redis.asyncio.Redis`` instance. We never read
        # private attrs, only call documented public methods.
        self._client = client
        # Pending GET requests waiting for the next tick to flush.
        # Map of key (str) → list of futures awaiting that key. Multiple
        # callers asking for the same key in the same tick share a future
        # so we don't transmit the same key twice in one MGET.
        self._pending: dict[str, list[asyncio.Future[Any]]] = {}
        # Whether a flush task is already scheduled. Guards against
        # double-scheduling when many gets arrive before the tick fires.
        self._flush_scheduled: bool = False

    async def get(self, key: Any) -> Any:
        """Coalesced GET. Identical semantics to ``Redis.get(key)`` —
        returns the value (as bytes or str depending on the underlying
        client's ``decode_responses`` setting) or ``None`` if the key
        does not exist.
        """
        key_str = _normalize_key(key)
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        bucket = self._pending.setdefault(key_str, [])
        bucket.append(fut)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            # ``ensure_future`` not strictly needed — ``create_task`` is
            # the standard primitive. The flush coroutine itself yields
            # via ``asyncio.sleep(0)`` so peer gets enqueued in the same
            # microtask have time to join the batch before MGET fires.
            asyncio.create_task(self._flush())
        return await fut

    async def _flush(self) -> None:
        # Yield once so peer ``.get()`` awaits scheduled in the same tick
        # get a chance to enqueue before MGET fires. Without this we
        # would degenerate back to one-key-per-MGET.
        await asyncio.sleep(0)
        # Snapshot + reset before issuing MGET so any further gets enqueued
        # mid-flush start a fresh batch instead of mutating the in-flight one.
        pending = self._pending
        self._pending = {}
        self._flush_scheduled = False
        if not pending:
            return
        keys = list(pending.keys())
        try:
            values = await self._client.mget(keys)
        except Exception as exc:  # noqa: BLE001 — fan out to all waiters
            logger.warning("BatchedRedis: mget(%d keys) failed: %s", len(keys), exc)
            for bucket in pending.values():
                for f in bucket:
                    if not f.done():
                        f.set_exception(exc)
            return
        # Dispatch results. ``mget`` returns a list aligned with ``keys``.
        for k, v in zip(keys, values):
            for f in pending[k]:
                if not f.done():
                    f.set_result(v)

    def __getattr__(self, name: str) -> Any:
        """Pass through every non-GET operation directly to the underlying
        client. ``__getattr__`` only fires for missing attributes, so this
        doesn't shadow ``get``/``_client``/``_pending``/``_flush_scheduled``.
        """
        return getattr(self._client, name)


def _normalize_key(key: Any) -> str:
    """MGET requires a list of comparable keys. Accept str or bytes and
    return a canonical str so duplicate-key deduplication works.
    """
    if isinstance(key, bytes):
        return key.decode()
    return str(key)
