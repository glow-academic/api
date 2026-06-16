"""report-18 B1/B3: BatchedRedis must hold a strong reference to its in-flight
flush task (so it can't be GC'd → hung awaits + lost writes), and a single
poisoned command in a batch must fail ONLY its own future, not the co-batched
reads/writes for unrelated keys.
"""

from __future__ import annotations

import asyncio

import pytest

from app.infra.batched_redis import BatchedRedis

pytestmark = pytest.mark.asyncio


class _FakePipe:
    def __init__(self, results_factory) -> None:
        self._cmds: list[tuple[str, object]] = []
        self._results_factory = results_factory
        self.raise_on_error_arg: object = "unset"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    def mget(self, keys):
        self._cmds.append(("mget", list(keys)))

    def setex(self, key, ttl, value):
        self._cmds.append(("setex", key))

    def expire(self, key, ttl):
        self._cmds.append(("expire", key))

    async def execute(self, raise_on_error=True):
        self.raise_on_error_arg = raise_on_error
        return self._results_factory(self._cmds)


class _FakeClient:
    def __init__(self, results_factory) -> None:
        self._results_factory = results_factory
        self.last_pipe: _FakePipe | None = None

    def pipeline(self, transaction=False):
        self.last_pipe = _FakePipe(self._results_factory)
        return self.last_pipe


async def test_b1_flush_task_is_strongly_referenced_until_done():
    client = _FakeClient(lambda cmds: [[b"v"]])
    r = BatchedRedis(client)

    fut = asyncio.ensure_future(r.get("k"))
    await asyncio.sleep(0)  # let get() enqueue + schedule the flush task
    # B1: the flush task must be held in a strong-ref set while in flight —
    # otherwise asyncio's weak ref lets it be GC'd and the await hangs forever.
    assert r._flush_tasks, "flush task must be strongly referenced while pending"

    assert await fut == b"v"  # the flush actually ran and resolved the await
    await asyncio.sleep(0)  # let the done-callback fire
    assert r._flush_tasks == set(), "completed flush task ref must be released"


async def test_b3_poisoned_command_does_not_fail_co_batched_ops():
    # Build per-command results: the "poison" SETEX errors; everything else OK.
    def factory(cmds):
        out: list[object] = []
        for op, arg in cmds:
            if op == "mget":
                out.append([b"val"])
            elif arg == "poison":
                out.append(RuntimeError("WRONGTYPE"))
            else:
                out.append(b"OK")
        return out

    client = _FakeClient(factory)
    r = BatchedRedis(client)

    # All three coalesce into one batch (one tick): a GET, a poisoned SETEX,
    # and an unrelated healthy SETEX.
    results = await asyncio.gather(
        r.get("good"),
        r.setex("poison", 10, "x"),
        r.setex("ok", 10, "y"),
        return_exceptions=True,
    )

    # B3: the wrapper must call execute(raise_on_error=False)...
    assert client.last_pipe is not None
    assert client.last_pipe.raise_on_error_arg is False
    # ...so the poisoned SETEX fails ONLY its own future, while the co-batched
    # GET and the unrelated SETEX still succeed.
    assert results[0] == b"val"
    assert isinstance(results[1], RuntimeError)
    assert results[2] == b"OK"
