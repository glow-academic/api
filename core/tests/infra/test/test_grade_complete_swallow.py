"""SW1 — ``test_grade_complete_impl`` must SURFACE a failed token/score write.

Pre-fix, a single ``try/except Exception`` wrapped BOTH the usage/billing token
write and the score-delivery emit, then returned ``None``. A failure silently
swallowed the lost billing row AND the grade event, while the caller treated the
grade flow as done (silent success). The fix moves the load-bearing token write
OUT of the swallowing try (so it re-raises, mirroring E1); only the post-commit
cosmetic emit stays best-effort.

Deps stubbed as black boxes over a fake pool.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

# Aliased import — bare ``test_*`` names get collected by pytest as test cases.
from app.infra.test.workflows import test_grade_complete_impl as grade_complete
from tests.infra._txn_fakes import TxnSpyConn, TxnSpyPool

pytestmark = pytest.mark.asyncio


def _payload():
    return {
        "sid": "sid-1",
        "grade_id": str(uuid4()),
        "invocation_id": str(uuid4()),
        "run_id": str(uuid4()),
        "session_id": str(uuid4()),
        "input_text_tokens": 10,
        "output_text_tokens": 20,
        "tool_results": [],
    }


async def _noop_emit(events):
    return None


async def test_token_write_failure_surfaces(monkeypatch):
    """A failed usage/billing token write must re-raise — not be swallowed into
    a fake 'grade complete'."""
    async def _create_token(conn, redis, **kwargs):
        raise RuntimeError("injected token-write failure")

    monkeypatch.setattr("app.tools.entries.tokens.create.create_token", _create_token)

    with pytest.raises(RuntimeError, match="injected token-write failure"):
        await grade_complete(
            _payload(),
            emit=_noop_emit,
            pool=TxnSpyPool(TxnSpyConn()),
            profile_id=str(uuid4()),
        )


async def test_emit_failure_stays_best_effort(monkeypatch):
    """The post-commit score-delivery emit is cosmetic — a failed emit must NOT
    re-raise once the load-bearing token write has persisted."""
    wrote: list = []

    async def _create_token(conn, redis, **kwargs):
        wrote.append(True)
        return None

    async def _raising_emit(events):
        raise RuntimeError("emit transport down")

    monkeypatch.setattr("app.tools.entries.tokens.create.create_token", _create_token)

    # Must NOT raise — the persisted token stands; only the UX emit is lost.
    await grade_complete(
        _payload(),
        emit=_raising_emit,
        pool=TxnSpyPool(TxnSpyConn()),
        profile_id=str(uuid4()),
    )
    assert wrote == [True]  # the load-bearing write ran before the emit failed
