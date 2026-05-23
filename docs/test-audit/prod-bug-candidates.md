# Production Bug Candidates Surfaced by the Test-Harness Audit

Findings where a failing test pointed to a real defect in production code (not test rot). File a real bug ticket / fix; do not "fix" by deleting the test.

---

## 1. `_find_next_run_id` — called but not defined

**File:** `core/app/infra/test/workflows.py`
**Line:** 276

```python
next_run_id = _find_next_run_id(runs, prev_run_id)
```

This function is called inside `test_group_impl` (the `test.group` event handler), but it is **never defined or imported** anywhere in `core/app/`. The code would raise `NameError` at runtime if this path executes.

**Evidence:**
```
$ git grep "def _find_next_run_id\|def find_next_run_id" core/app/
(no matches)
```

**Test impact:** The `TestFindNextRunId` class in `core/tests/infra/test_attempt_events.py` was catching this. (Note: that file was ultimately deleted in test-audit Batch 0 due to multiple missing prod symbols — see items 2 and 3.) When the prod bug is fixed, restore those tests from `git show 5fba90f8c7~1:core/tests/infra/test_attempt_events.py` (the pre-Batch-0 state).

**Suggested fix:** Either implement `_find_next_run_id(runs, prev_run_id)` (probably: walk `runs` to find the entry whose `prev_run_id` matches and return the next one), OR if this code path is dead, remove the call and the surrounding block.

---

## 2. `test_proceed_impl` — imported but not defined

**Imported in (at minimum):** `core/tests/infra/test_attempt_events.py` (pre-Batch-0)

**Expected in:** `core/app/infra/test/workflows.py` — currently NOT present.

**Evidence:**
```
$ grep -E "^(def |async def )" core/app/infra/test/workflows.py
async def test_progress_impl(
async def test_run_done_impl(
async def test_error_impl(
async def test_grade_complete_impl(
async def test_group_impl(
async def test_next_impl(
async def test_start_impl(
def _extract_grade_score(...)
def _extract_grade_passed(...)
def _extract_grade_feedback(...)
def build_messages_from_conversation(...)
# test_proceed_impl is missing
```

**Likely status:** Either (a) intentionally removed during the recent test/operations refactor and the import is just stale (no real bug), or (b) a refactor straggler — the event handler for `test.proceed` was supposed to be moved here and wasn't.

**Action needed:** Confirm whether `test.proceed` is still a supported event. If yes, implement the handler. If no, this is just test rot and the test file deletion is fine.

---

## 3. `test_run_impl` — imported but not defined

**Same situation as #2.** Imported in pre-Batch-0 `test_attempt_events.py`, not present in `core/app/infra/test/workflows.py`.

**Action needed:** Same as #2 — confirm intent.

---

## Notes on the test-audit context

These bugs were surfaced during the test-harness audit (PR #1, PR #2, and the Phase 1.1 restore PR). The audit pattern was: when a test fails because it imports a symbol from prod code that no longer exists, classify the failure as either (a) stale test (delete it) or (b) prod bug candidate (file it here, don't delete the test).

Items 1-3 are in the (b) category — they point at functions production code expected to exist (item 1 is unambiguously a bug because the call site is live). Items 2 and 3 may turn out to be (a) once you confirm whether `test.proceed` and `test.run` events are still in the supported event surface.
