"""report-21 FIX 3(a) — per-class invariant guard for the HC1 / V1 bug class.

The hedged-cache layer must keep the per-id write-back cache consistent with
what an entry's GET/SEARCH returns. The dangerous class (report-19 HC1) is a
materialized view defined ``DISTINCT ON (<key>) ... ORDER BY <key>, created_at
DESC`` over its OWN entry table — i.e. "latest row per <key> wins". A re-write
appends a NEW row for the same <key>; only the latest is visible in the MV, but
the write-back cache keys EVERY row by its own entry id, so without busting the
prior rows' cache keys a hedged SEARCH would return N rows for one <key> for up
to the cache TTL (the attempt_grade HC1 bug). The fix: the create module
invalidates the prior rows for that <key> around ``write_back_row`` (see
``attempt_grade/create.py``).

This static guard:
  1. Scans ``database/schema/views/*.sql`` for every MV with ``DISTINCT ON``.
  2. Asserts each is in our CLASSIFICATION below (a NEW grade-like MV added in
     the future is unclassified → this test FAILS, forcing a human to decide
     whether it needs HC1-style invalidation — catching the bug class proactively).
  3. For MVs classified ``REQUIRES_INVALIDATION``, asserts the entry's
     create module actually calls ``invalidate_row`` (the HC1 supersede).

It is deliberately pragmatic (source scan, curated classification with
documented reasons) to avoid false failures. It logs what it checked.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# tests/utils/cache/test_x.py: parents[3] == core/, parents[4] == repo root.
_VIEWS_DIR = Path(__file__).resolve().parents[4] / "database" / "schema" / "views"
_APP_ENTRIES = Path(__file__).resolve().parents[3] / "app" / "tools" / "entries"

_DISTINCT_ON = re.compile(r"DISTINCT ON \(([^)]*)\)")


# ── Classification of every DISTINCT-ON MV ────────────────────────────────────
#
# Each MV maps to a verdict + reason. Verdicts:
#   "REQUIRES_INVALIDATION": latest-per-FK over the entry's OWN table AND the
#       write-back cache keys rows by the entry's own id → the create MUST bust
#       prior rows for that key (HC1). Value is the create module to check.
#   "EXEMPT_KEYED_BY_DISTINCT_COL": latest-per-FK, but the write-back cache is
#       keyed by the DISTINCT-ON column itself, so a fresh write OVERWRITES the
#       prior cache row in place — no stale sibling can survive.
#   "EXEMPT_DISTINCT_ON_OWN_ID": DISTINCT ON the entry's own primary id — one
#       row per id, no latest-per-FK supersede semantics.
#   "EXEMPT_DISTINCT_ON_SUBRESOURCE": the DISTINCT ON lives in a CTE over a
#       DIFFERENT table (a sub-resource/junction), not the MV's primary entry;
#       the supersede (if any) is the sub-resource's concern, and the parent's
#       cache is busted by that sub-resource's create (e.g. test_grade busts the
#       parent test_invocation row).
#   "EXEMPT_PLAIN_NO_SUPERSEDE": no DISTINCT ON over the primary entry that
#       changes latest-per-key (covered for completeness; such MVs won't match).
#
# NOTE on V1 (report-21 disputed): ``test_grade_mv`` is intentionally ABSENT
# here because it is a PLAIN ``SELECT ... WHERE active=true`` (NOT DISTINCT ON) —
# so it returns ALL active grades and there is no supersede/divergence. See the
# separate ``test_grade`` verdict assertion at the bottom of this file.
CLASSIFICATION: dict[str, tuple[str, str]] = {
    "attempt_grade_mv": (
        "REQUIRES_INVALIDATION",
        "attempt_grade",  # create module under app/tools/entries/
    ),
    "soft_calls_mv": (
        "EXEMPT_KEYED_BY_DISTINCT_COL",
        "DISTINCT ON (call_id); the write-back cache key IS entry:soft_call:"
        "{call_id}, so a new status row overwrites the prior cache row in place.",
    ),
    "group_names_mv": (
        "EXEMPT_KEYED_BY_DISTINCT_COL",
        "DISTINCT ON (group_id); the write-back cache key IS the group_id, so a "
        "rename overwrites the prior cached name in place (and the dormant path "
        "explicitly invalidate_row's group_id anyway).",
    ),
    "attempt_responses_mv": (
        "EXEMPT_DISTINCT_ON_OWN_ID",
        "DISTINCT ON (r.id) — distinct on the response's OWN id (one row per "
        "response), not a latest-per-foreign-key supersede.",
    ),
    "chat_mv": (
        "EXEMPT_DISTINCT_ON_SUBRESOURCE",
        "DISTINCT ON (tbsc.chat_id) is in the scenario_single CTE over the "
        "chat_scenarios_connection JUNCTION, picking one scenario per chat — not "
        "a supersede of chat_entry rows (which are keyed by their own id).",
    ),
    "attempt_chat_mv": (
        "EXEMPT_DISTINCT_ON_SUBRESOURCE",
        "All DISTINCT ON clauses are in CTEs over OTHER tables "
        "(attempt_grade_entry latest-grade, rubric/position/time-limit "
        "connections) — the attempt_chat rows themselves are keyed by their own "
        "id; the latest-grade supersede is attempt_grade's concern (handled by "
        "its REQUIRES_INVALIDATION create).",
    ),
    "test_invocation_mv": (
        "EXEMPT_DISTINCT_ON_SUBRESOURCE",
        "DISTINCT ON (g.invocation_id)/(c.invocation_id) live in CTEs over "
        "test_grade_entry / test_invocation_completion_entry (sub-resources). "
        "The latest-grade derivation is busted by test_grade's create, which "
        "invalidate_row's the parent test_invocation cache row.",
    ),
}


def _discover_distinct_on_mvs() -> dict[str, list[str]]:
    """Return ``{mv_name: [distinct_on_col, ...]}`` for every MV with DISTINCT ON."""
    assert _VIEWS_DIR.is_dir(), f"views dir not found: {_VIEWS_DIR}"
    found: dict[str, list[str]] = {}
    for sql_path in sorted(_VIEWS_DIR.glob("*.sql")):
        text = sql_path.read_text()
        cols = _DISTINCT_ON.findall(text)
        if not cols:
            continue
        mv_name = sql_path.stem  # e.g. attempt_grade_mv
        found[mv_name] = [c.strip() for c in cols]
    return found


def test_every_distinct_on_mv_is_classified() -> None:
    """Every DISTINCT-ON MV must appear in CLASSIFICATION. A new grade-like MV
    is unclassified → fails here, forcing a human to decide on HC1 invalidation."""
    discovered = _discover_distinct_on_mvs()
    logger.info(
        "DISTINCT-ON MVs discovered (%d): %s",
        len(discovered),
        dict(discovered),
    )
    unclassified = sorted(set(discovered) - set(CLASSIFICATION))
    assert not unclassified, (
        "New DISTINCT-ON materialized view(s) found with no classification: "
        f"{unclassified}. If an MV is `DISTINCT ON (<fk>)` over its OWN entry "
        "table and its write-back cache keys rows by the entry's own id, its "
        "create MUST bust prior rows for that <fk> (the HC1 pattern — see "
        "attempt_grade/create.py). Add it to CLASSIFICATION with the right "
        "verdict + reason."
    )

    # Also flag stale classifications (an MV removed/renamed in the schema).
    stale = sorted(set(CLASSIFICATION) - set(discovered))
    assert not stale, (
        f"CLASSIFICATION references MV(s) no longer in the schema: {stale}. "
        "Remove or update them."
    )


def test_requires_invalidation_mvs_actually_invalidate() -> None:
    """Every MV classified REQUIRES_INVALIDATION must have a create module that
    calls ``invalidate_row`` (busting prior rows for the DISTINCT-ON key)."""
    checked: list[str] = []
    for mv_name, (verdict, payload) in CLASSIFICATION.items():
        if verdict != "REQUIRES_INVALIDATION":
            continue
        entry = payload
        create_path = _APP_ENTRIES / entry / "create.py"
        assert create_path.is_file(), (
            f"{mv_name} requires invalidation but its create module is missing: "
            f"{create_path}"
        )
        src = create_path.read_text()
        assert "invalidate_row" in src, (
            f"{mv_name} is DISTINCT-ON-(fk) over its own table with id-keyed "
            f"write-backs, but {entry}/create.py never calls invalidate_row — a "
            "re-write would leave a superseded sibling in the hedged cache for "
            "the TTL (HC1). Bust prior rows for the key before/around "
            "write_back_row (see attempt_grade/create.py)."
        )
        checked.append(f"{mv_name} -> {entry}/create.py")
    logger.info("REQUIRES_INVALIDATION creates verified: %s", checked)
    assert checked, "expected at least one REQUIRES_INVALIDATION MV (attempt_grade)"


def test_v1_test_grade_is_exempt_plain_mv() -> None:
    """report-21 V1 verdict (DISPUTED → NOT A BUG): ``test_grade_mv`` is a PLAIN
    ``SELECT ... WHERE active=true`` (NOT DISTINCT ON), so it returns ALL active
    grades — a re-grade legitimately yields N active grades in BOTH the MV and
    the cache (consistent, no divergence). The "single latest grade per
    invocation" lives in the PARENT ``test_invocation_mv`` (DISTINCT ON
    invocation_id), which ``test_grade/create.py`` already invalidates.

    Therefore test_grade must NOT do prior-grade invalidation (it would make
    search_test_grades UNDER-report). This test pins that verdict: test_grade_mv
    is not a DISTINCT-ON MV, and test_grade/create.py does not bust prior grades.
    """
    discovered = _discover_distinct_on_mvs()
    assert "test_grade_mv" not in discovered, (
        "test_grade_mv unexpectedly became a DISTINCT-ON MV — re-evaluate V1: if "
        "it is now DISTINCT ON (invocation_id) there IS a supersede and "
        "test_grade/create.py must invalidate prior grades like HC1."
    )

    tg_mv = (_VIEWS_DIR / "test_grade_mv.sql").read_text()
    assert "DISTINCT ON" not in tg_mv, "test_grade_mv must remain a plain MV"

    tg_create = (_APP_ENTRIES / "test_grade" / "create.py").read_text()
    # It DOES invalidate the parent test_invocation row (correct), but must NOT
    # invalidate prior test_grade rows for the invocation (would under-report).
    assert 'invalidate_row(redis, "test_invocation"' in tg_create, (
        "test_grade/create.py should still bust the parent test_invocation cache "
        "row (the DISTINCT-ON-invocation_id derivation lives there)."
    )
    assert 'invalidate_row(redis, "test_grade"' not in tg_create, (
        "test_grade/create.py must NOT invalidate prior test_grade rows — "
        "test_grade_mv returns ALL active grades, so busting siblings would make "
        "search_test_grades under-report (V1 is NOT a cache-divergence bug)."
    )
