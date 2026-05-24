"""Tests for `_find_next_run_id` in `core/app/infra/test/workflows.py`.

The helper was called at workflows.py:276 but never defined — a NameError
waiting to happen on the `test.group` event path. Defined in PR
`prod-bug/find-next-run-id` per the contract these tests document.

These tests were originally in `core/tests/infra/test_attempt_events.py`
(pre-Batch-0). That file was deleted in test-audit Batch 0 because it
referenced multiple missing prod symbols. Extracted here as a focused
unit test for the now-fixed helper.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.infra.test.workflows import _find_next_run_id


def test_empty_runs() -> None:
    assert _find_next_run_id([], None) is None


def test_first_run_no_prev() -> None:
    runs = [SimpleNamespace(run_id="r1"), SimpleNamespace(run_id="r2")]
    assert _find_next_run_id(runs, None) == "r1"


def test_next_after_prev() -> None:
    runs = [
        SimpleNamespace(run_id="r1"),
        SimpleNamespace(run_id="r2"),
        SimpleNamespace(run_id="r3"),
    ]
    assert _find_next_run_id(runs, "r1") == "r2"
    assert _find_next_run_id(runs, "r2") == "r3"


def test_last_run_returns_none() -> None:
    runs = [SimpleNamespace(run_id="r1"), SimpleNamespace(run_id="r2")]
    assert _find_next_run_id(runs, "r2") is None


def test_unknown_prev_returns_none() -> None:
    runs = [SimpleNamespace(run_id="r1")]
    assert _find_next_run_id(runs, "unknown") is None
