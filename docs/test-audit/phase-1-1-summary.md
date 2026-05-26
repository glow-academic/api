# Phase 1.1 Summary — Restore Over-Deleted Tests + File Prod Bugs

## Context

In test-audit Batch 0 (commit 6c0f668419), I deleted three test files whole that had import errors:
- `core/tests/infra/dashboard/test_history_response.py`
- `core/tests/infra/test_workflow_internal_entries.py`
- `core/tests/infra/test_attempt_events.py`

A subsequent Codex pass (Phase 1.1) caught that two of those files were **mixed** — they had dead tests alongside live tests, and the right cleanup was surgical (remove the dead tests, keep the live ones), not whole-file deletion.

This PR corrects the over-deletion by restoring the recoverable live tests.

## Files restored

### `core/tests/infra/dashboard/test_history_response.py` (128 lines, 3 live tests recovered)

Restored from `git show 5fba90f8c7~1` (pre-Batch-0 state), with the 1 dead test removed:
- **Removed:** `test_build_history_response_populates_filter_options_from_resources` — imported `_build_history_response` from `app.routes.attempt.dashboard.search`, which no longer exists.
- **Kept (live tests):**
  - `test_dashboard_search_context_does_not_default_to_general_only`
  - `test_dashboard_search_context_archived_filter_is_independent_of_practice`
  - `test_dashboard_search_context_returns_general_and_practice_by_default`

### `core/tests/infra/test_workflow_internal_entries.py` (89 lines, 1 live test recovered)

Restored with 2 of 3 tests removed (they imported renamed-away `*_internal_impl` symbols):
- **Removed:** `test_attempt_start_internal_impl_returns_terminal_result`, `test_attempt_grade_internal_impl_emits_grade_complete`
- **Kept (live test):** `test_test_start_internal_impl_returns_terminal_result` — `test_start_internal_impl` still exists in `core/app/infra/test/start.py:54`.

### `core/tests/infra/test_attempt_events.py` — NOT restored

This file was investigated but **left deleted** because it has too many missing prod symbols to rescue cleanly:
- `_find_next_run_id` (used by `TestFindNextRunId` class)
- `test_proceed_impl` (used by multiple test classes)
- `test_run_impl` (used by multiple test classes)

Each is filed in `docs/test-audit/prod-bug-candidates.md`. When the prod side is fixed, restore the file from `git show 5fba90f8c7~1:core/tests/infra/test_attempt_events.py`.

## Production-bug candidates filed

See `docs/test-audit/prod-bug-candidates.md`. Three items:

1. **`_find_next_run_id`** — called at `core/app/infra/test/workflows.py:276` but never defined. Real `NameError` waiting to happen if that code path runs. **Highest priority** of the three.
2. **`test_proceed_impl`** — expected in `core/app/infra/test/workflows.py`, not present. Likely a refactor straggler or stale test import.
3. **`test_run_impl`** — same situation as #2.

## Verification

```
$ pytest --co -q core/tests/
6980 tests collected
```

(Up from 6,976 before this PR. Net: +4 tests recovered.)

`make lint` and `make typecheck` were not run as part of this PR because the broader suite still has the 1,528 signature-drift failures from test-audit Batch 2's survey (see PR #2). That's a separate cleanup track and not blocked by this PR.

## What's next

After this PR is in, the test-audit work continues with the pattern-based sweeps (Phases 1.2 onward) targeting the failure buckets identified in Batch 2:
- Tool/entry/resource helper drift: 735
- Route contract drift: 246
- Artifact impl direct-call drift: 238
- Other infra drift: 294
