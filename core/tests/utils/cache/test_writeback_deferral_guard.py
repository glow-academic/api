"""report-20 V2 guard: every Postgres transaction in app code must use
``transaction_with_writeback`` (not a bare ``conn.transaction()``), so any
``write_back_row`` issued inside it is deferred until COMMIT — closing the HC2
phantom-cache-row-on-rollback class for the WHOLE codebase, not just the two
sites HC2 originally wired.

This is a fast static scan (no DB/Redis). If you add a new ``async with
<conn>.transaction():`` to app code, this test fails and points you at the
deferred helper. The few legitimate exceptions are whitelisted below with a
reason.
"""

from __future__ import annotations

import re
from pathlib import Path

# core/app, resolved relative to this test file (tests/utils/cache/).
_APP_ROOT = Path(__file__).resolve().parents[3] / "app"

# `async with <var>.transaction():` — the bare asyncpg context manager.
_BARE_TXN = re.compile(r"async with \w+\.transaction\(\):")

# Files allowed to use a bare transaction, each with a reason.
_WHITELIST = {
    # Defines transaction_with_writeback itself (wraps conn.transaction()).
    "app/utils/cache/hedged_row.py",
}


def _rel(path: Path) -> str:
    # Normalize to "app/..." regardless of where pytest is invoked from.
    parts = path.resolve().parts
    idx = len(parts) - 1 - parts[::-1].index("app")
    return "/".join(parts[idx:])


def test_no_bare_conn_transaction_in_app() -> None:
    offenders: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = _rel(path)
        if rel in _WHITELIST:
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _BARE_TXN.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Bare `conn.transaction()` found in app code — use "
        "`transaction_with_writeback(conn)` so write-backs defer to COMMIT "
        "(report-20 V2 / HC2). Offenders:\n  " + "\n  ".join(offenders)
    )
