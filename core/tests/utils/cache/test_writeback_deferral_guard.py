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


# ── report-21 FIX 3(b): V2-GAP-class guard ───────────────────────────────────
#
# The bare-transaction guard above only forces write-backs DONE THROUGH
# write_back_row to defer. report-21 V2-GAP was a different leak: soft_calls
# wrote its hedged write-back cache row via a DIRECT ``redis.pipeline().setex(
# entry:soft_call:{id}, ...)`` (a comment even said it "reaches past
# BatchedRedis"), bypassing write_back_row entirely — so the SETEX fired
# IMMEDIATELY regardless of any surrounding transaction, and a rollback left a
# phantom cache row served for the TTL.
#
# The structural invariant that closes the class: the hedged per-id write-back
# cache (keys shaped ``entry:<X>:<id>`` / ``entry:<X>:recent``) may only be
# WRITTEN through ``write_back_row`` in ``hedged_row.py`` (which routes through
# the deferral). No other app file may issue a raw ``setex``/``zadd`` against an
# ``entry:``-prefixed key. This static scan flags any such raw write. READS of
# those keys (``get`` / ``mget`` / ``zrevrange`` / ``zscore`` and bare key
# constants used only for reads) are fine — only writes bypass the deferral.

# Raw Redis WRITE ops that, applied to an `entry:`-prefixed key, would bypass
# write_back_row's deferral.
_RAW_WRITE_OP = re.compile(r"\.(setex|zadd|zremrangebyrank)\(")
# A literal `entry:` cache key (the hedged-row namespace prefix).
_ENTRY_KEY_LITERAL = re.compile(r'["\']entry:')

# Files allowed to touch raw `entry:` write ops, each with a reason.
_ENTRY_WRITE_WHITELIST = {
    # The shared helper that OWNS the entry:* write-back keys + the deferral.
    "app/utils/cache/hedged_row.py",
}


def test_no_raw_entry_writeback_bypassing_deferral() -> None:
    """No app file (besides hedged_row.py) may issue a raw setex/zadd against an
    ``entry:``-prefixed key — that bypasses write_back_row's HC2/V2 deferral
    (report-21 V2-GAP). Route hedged write-backs through ``write_back_row``."""
    offenders: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = _rel(path)
        if rel in _ENTRY_WRITE_WHITELIST:
            continue
        lines = path.read_text().splitlines()
        # An `entry:` literal anywhere in a module that ALSO issues a raw write
        # op is the smell. Be conservative: only flag files that have BOTH a raw
        # write op AND an `entry:` key literal (a read-only `entry:` constant
        # like search.py's _RECENT_KEY, with no raw write op, is clean).
        has_entry_literal = any(_ENTRY_KEY_LITERAL.search(ln) for ln in lines)
        if not has_entry_literal:
            continue
        for lineno, line in enumerate(lines, start=1):
            if _RAW_WRITE_OP.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Raw setex/zadd in a module that also references an `entry:` write-back "
        "key — this bypasses write_back_row's HC2/V2 deferral (report-21 "
        "V2-GAP). Route hedged write-backs through `write_back_row` (or add a "
        "documented whitelist entry if this key is genuinely not a hedged "
        "write-back row). Offenders:\n  " + "\n  ".join(offenders)
    )
