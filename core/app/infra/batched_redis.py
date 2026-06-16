"""BatchedRedis — automatic per-tick batching for Redis reads + writes.

Wraps an ``redis.asyncio.Redis`` client so that every ``await client.get(k)``,
``await client.setex(k, ttl, v)`` and ``await client.expire(k, ttl)`` within
a single event-loop turn is collected into a pending queue. At the next
``await asyncio.sleep(0)`` boundary the wrapper fires ONE pipeline that
includes MGET (for all the reads) plus SETEX / EXPIRE for all the writes,
in a single round-trip. Each caller's awaited future resolves with its
individual result.

The application code is unchanged — every ``await redis.<op>(...)`` still
looks like a single operation. Only the wire pattern changes: where the
underlying client previously issued N sequential round-trips, it now
issues ONE pipeline per asyncio "tick".

Why this exists
---------------
Measured 2026 on ``/persona/get``:
  - 76 redis cache HITS per warm request, sequential round-trips
  - 14-17 cache WRITES per cold request, also sequential round-trips
  - The 23-way ``asyncio.gather`` parallelises Python but not the wire.
This wrapper recovers wire-layer parallelism for both reads and writes.

Safety / batching scope
-----------------------
Batched:
  - GET           — coalesced into MGET (read)
  - SETEX         — coalesced into a pipeline (write, no-return)
  - EXPIRE        — coalesced into a pipeline (write, returns bool)

NOT batched (pass through via ``__getattr__``):
  - SET with NX (atomic lock-acquire — caller branches on return; mixing
    into a pipeline would break read-after-write causality if a peer GET
    on the same key is in the same batch)
  - HASH / LIST / STREAM / SCRIPT primitives
  - PIPELINE explicitly (caller is managing their own)
  - SUBSCRIBE / PUBSUB / blocking commands

Read-after-write within one tick: writes execute in the same pipeline
as reads, but the pipeline returns all results together — a GET in the
same batch as a SETEX of the same key would see the PRE-write value.
None of the audit-wrapper or cache-layer code paths in this codebase
do a GET-of-key followed by a SETEX-of-same-key in the same tick, so
this is safe in practice. If a future caller adds that pattern, they
must call ``redis._client.setex(...)`` directly to bypass batching, or
the wrapper would need an inline-flush before queueing the dependent op.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _PendingWrite:
    op: str  # "setex" | "expire"
    key: str
    ttl: int
    value: Any  # ignored for expire
    future: asyncio.Future[Any]


class BatchedRedis:
    """Drop-in wrapper over an ``redis.asyncio.Redis`` client that auto-
    coalesces concurrent ``.get()`` / ``.setex()`` / ``.expire()`` awaits
    into one pipeline per asyncio tick.

    Constructor takes the real client; everything else delegates via
    ``__getattr__``.

    Not thread-safe — single event loop only, matching the underlying
    redis client's contract.
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        # Pending reads: map of key (str) → list of futures awaiting that key.
        # Multiple callers asking for the same key in the same tick share
        # a single redis-side fetch but each get their own future.
        self._pending_gets: dict[str, list[asyncio.Future[Any]]] = {}
        # Pending writes: ordered list of (op, key, ttl, value, future).
        # Order is preserved so the pipeline mirrors caller-visible order.
        self._pending_writes: list[_PendingWrite] = []
        # Guards double-scheduling of the flush task when many ops enqueue
        # before the next tick fires.
        self._flush_scheduled: bool = False
        # B1 (report-18): asyncio holds only a WEAK reference to a task, so a
        # flush task whose only ref was the discarded ``create_task`` return
        # could be garbage-collected before it ran — leaving every awaiting
        # ``get``/``setex``/``expire`` future for that tick to hang forever and
        # the buffered writes silently lost. Hold a strong ref in a set until
        # the task completes (mirrors utils/async_tasks.schedule_background).
        self._flush_tasks: set[asyncio.Task[Any]] = set()

    async def get(self, key: Any) -> Any:
        """Coalesced GET. Identical semantics to ``Redis.get(key)`` —
        returns the value (bytes/str depending on ``decode_responses``)
        or ``None`` for a missing key.
        """
        key_str = _normalize_key(key)
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        bucket = self._pending_gets.setdefault(key_str, [])
        bucket.append(fut)
        self._schedule_flush()
        return await fut

    async def setex(self, name: Any, time: int, value: Any) -> Any:
        """Coalesced SETEX. Identical semantics to ``Redis.setex(name, time, value)``
        — sets the key with an expiration, returns the redis "OK" reply.
        """
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending_writes.append(
            _PendingWrite(op="setex", key=_normalize_key(name), ttl=int(time), value=value, future=fut)
        )
        self._schedule_flush()
        return await fut

    async def expire(self, name: Any, time: int) -> bool:
        """Coalesced EXPIRE. Identical semantics to ``Redis.expire(name, time)``
        — sets TTL on existing key, returns True/False.
        """
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending_writes.append(
            _PendingWrite(op="expire", key=_normalize_key(name), ttl=int(time), value=None, future=fut)
        )
        self._schedule_flush()
        return await fut

    def _schedule_flush(self) -> None:
        if not self._flush_scheduled:
            self._flush_scheduled = True
            task = asyncio.create_task(self._flush())
            # B1: keep a strong ref so the task can't be GC'd mid-flight;
            # drop it on completion to avoid unbounded growth.
            self._flush_tasks.add(task)
            task.add_done_callback(self._flush_tasks.discard)

    async def _flush(self) -> None:
        # Yield once so peer awaits scheduled in the same tick get a chance
        # to enqueue before the pipeline fires. Without this we'd degenerate
        # back to one-op-per-pipeline.
        await asyncio.sleep(0)
        # Snapshot + reset before issuing pipeline so any further ops
        # enqueued mid-flush start a fresh batch.
        pending_gets = self._pending_gets
        pending_writes = self._pending_writes
        self._pending_gets = {}
        self._pending_writes = []
        self._flush_scheduled = False
        if not pending_gets and not pending_writes:
            return

        get_keys = list(pending_gets.keys())
        try:
            # ``transaction=False`` — we don't need MULTI/EXEC atomicity,
            # just pipelined dispatch (one network round-trip).
            # B3 (report-18): ``raise_on_error=False`` so ONE poisoned command
            # (e.g. a SETEX/EXPIRE against a wrong-type key) does NOT abort and
            # fail every co-batched op — its error is returned in-band as that
            # command's result and dispatched to ITS future only. Without this,
            # a single bad key silently dropped a co-batched rate-limit EXPIRE
            # or cache SETEX for unrelated keys/requests in the same tick.
            async with self._client.pipeline(transaction=False) as pipe:
                if get_keys:
                    pipe.mget(get_keys)
                for w in pending_writes:
                    if w.op == "setex":
                        pipe.setex(w.key, w.ttl, w.value)
                    elif w.op == "expire":
                        pipe.expire(w.key, w.ttl)
                results = await pipe.execute(raise_on_error=False)
        except Exception as exc:  # noqa: BLE001 — connection-level failure
            logger.warning(
                "BatchedRedis: pipeline failed (%d gets, %d writes): %s",
                len(get_keys), len(pending_writes), exc,
            )
            for bucket in pending_gets.values():
                for f in bucket:
                    if not f.done():
                        f.set_exception(exc)
            for w in pending_writes:
                if not w.future.done():
                    w.future.set_exception(exc)
            return

        # Dispatch results. Pipeline returns one entry per queued command,
        # in queue order: MGET (if any), then each write. With
        # ``raise_on_error=False`` an individual entry may be an Exception
        # (that command failed) — dispatch it to that command's future(s) only.
        idx = 0
        if get_keys:
            values = results[idx]
            idx += 1
            if isinstance(values, Exception):
                for k in get_keys:
                    for f in pending_gets[k]:
                        if not f.done():
                            f.set_exception(values)
            else:
                for k, v in zip(get_keys, values):
                    for f in pending_gets[k]:
                        if not f.done():
                            f.set_result(v)
        for i, w in enumerate(pending_writes):
            if w.future.done():
                continue
            res = results[idx + i]
            if isinstance(res, Exception):
                w.future.set_exception(res)
            else:
                w.future.set_result(res)

    def __getattr__(self, name: str) -> Any:
        """Pass through every non-batched operation directly to the
        underlying client. ``__getattr__`` only fires for missing attributes,
        so this doesn't shadow ``get`` / ``setex`` / ``expire`` /
        ``_client`` / ``_pending_*`` / ``_flush_*``.
        """
        return getattr(self._client, name)


def _normalize_key(key: Any) -> str:
    """MGET / pipeline ops need str keys for the dedup-by-key map. Accept
    str or bytes and return a canonical str.
    """
    if isinstance(key, bytes):
        return key.decode()
    return str(key)
