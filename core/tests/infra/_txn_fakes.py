"""Shared transaction-spy fakes for the atomicity (A1-A4) regression tests.

The test/invocation/grade impls acquire a connection from the pool and (post
class-fix) wrap their multi-write chain in a single ``conn.transaction()``.
These fakes let a test prove that property deterministically without a DB:

  - ``TxnSpyConn`` records whether it is *inside* a transaction at the moment
    each fake write runs (``conn.in_txn``), and remembers the exception type
    the transaction context manager exited with.
  - A test injects a failure on a *later* write in the chain, then asserts that
    (a) the *earlier* (orphan-prone) write ran INSIDE the transaction, and
    (b) the transaction exited with that exception → a real DB would roll the
    earlier write back, leaving no orphan call/test/invocation/junction.
"""

from __future__ import annotations


class _TxnSpy:
    def __init__(self, conn: "TxnSpyConn") -> None:
        self._conn = conn

    async def __aenter__(self) -> "_TxnSpy":
        self._conn.in_txn = True
        self._conn.txn_entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._conn.in_txn = False
        self._conn.txn_exit_exc = exc_type
        return False  # never suppress — a real txn re-raises (rolls back)


class TxnSpyConn:
    """Stand-in for an asyncpg connection that tracks transaction state."""

    def __init__(self) -> None:
        self.in_txn = False
        self.txn_entered = False
        self.txn_exit_exc: type | None = None

    def transaction(self) -> _TxnSpy:
        return _TxnSpy(self)


class _Acquire:
    def __init__(self, conn: TxnSpyConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> TxnSpyConn:
        return self._conn

    async def __aexit__(self, *exc) -> bool:
        return False


class TxnSpyPool:
    """Fake pool whose ``acquire()`` always yields the same ``TxnSpyConn``."""

    def __init__(self, conn: TxnSpyConn) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)
