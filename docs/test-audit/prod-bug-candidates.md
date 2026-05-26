# Production Bug Candidates Surfaced by the Test-Harness Audit

Findings where a failing test pointed to a real defect in production code (not test rot). File a real bug ticket / fix; do not "fix" by deleting the test.

(Note: PR #3 and PR #4 both add to this file. If PR #3 merges first, PR #4's
content needs to be appended to this; the conflict is mechanical and the
sections are independent.)

---

## Phase 1.1 — items 1-3

### 1. `_find_next_run_id` — called but not defined

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

**Test impact:** The `TestFindNextRunId` class in `core/tests/infra/test_attempt_events.py` was catching this. (That file was ultimately deleted in test-audit Batch 0 due to multiple missing prod symbols — see items 2 and 3.) When the prod bug is fixed, restore those tests from `git show 5fba90f8c7~1:core/tests/infra/test_attempt_events.py` (the pre-Batch-0 state).

**Suggested fix:** Either implement `_find_next_run_id(runs, prev_run_id)` (probably: walk `runs` to find the entry whose `prev_run_id` matches and return the next one), OR if this code path is dead, remove the call and the surrounding block.

### 2. `test_proceed_impl` — imported but not defined

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

### 3. `test_run_impl` — imported but not defined

**Same situation as #2.** Imported in pre-Batch-0 `test_attempt_events.py`, not present in `core/app/infra/test/workflows.py`.

**Action needed:** Same as #2 — confirm intent.

---

## Phase 1.2 — items 4-9

### 4. Postgres enum `pricing_type` does not exist

**Test:** `core/tests/tools/resources/pricing/test_create.py::test_creates_new_pricing`

- Asserts: pricing resources can be inserted and read through the tools resource layer.
- Prod returns: `asyncpg.exceptions.UndefinedObjectError: type "pricing_type" does not exist`.
- Why this could be real: the test exercises the current DB-backed create path; a missing Postgres enum/type points to schema drift, not a test expectation mismatch.

### 5. `attempt_mutes_mv` materialized view does not exist

**Test:** `core/tests/tools/entries/attempt_mutes/test_get.py::test_gets_created_attempt_mutes`

- Asserts: attempt mute entries are visible through the materialized-view-backed get path after refresh.
- Prod returns: `asyncpg.exceptions.UndefinedTableError: relation "attempt_mutes_mv" does not exist`.
- Why this could be real: the production getter/refresh path expects an MV that the cloned test schema does not provide.

### 6. `chat_mv` cannot REFRESH CONCURRENTLY — missing unique index

**Test:** `core/tests/tools/entries/chat/test_refresh.py::test_refresh_is_idempotent`

- Asserts: chat MV refresh can run concurrently/idempotently.
- Prod returns: `cannot refresh materialized view "public.chat_mv" concurrently` with a hint to add a unique index.
- Why this could be real: the refresh implementation uses concurrent refresh semantics, but the MV schema appears to lack the required unique index.

### 7. `m.updated_at` column missing in model_flags search query

**Test:** `core/tests/tools/resources/model_flags/test_search.py::test_finds_created_model_flag`

- Asserts: model flag search can load rows through the model flags resource search path.
- Prod returns: `asyncpg.exceptions.UndefinedColumnError: column m.updated_at does not exist`.
- Why this could be real: the query references a column absent from the schema; changing the test would hide a broken SQL contract.

### 8. Health refresh tool path reaches into app-global Redis

**Test:** `core/tests/tools/entries/health/test_refresh.py::TestRefreshHealthClient::test_refreshes_views_and_invalidates_tags`

- Asserts: health refresh invalidates cache tags using the test Redis fixture path.
- Prod returns: `RuntimeError: Redis client not initialized -- get_redis_client() called before lifespan startup or after shutdown`.
- Why this could be real: the tool path appears coupled to app lifespan globals instead of accepting the existing test Redis boundary.

### 9. Metrics export has the same Redis-global coupling as item 8

**Test:** `core/tests/tools/entries/metrics/test_refresh.py::TestExportHealthClient::test_exports_health_and_metrics_zip`

- Asserts: metrics/health export can run against the test-backed app dependencies.
- Prod returns: `RuntimeError: Redis client not initialized -- get_redis_client() called before lifespan startup or after shutdown`.
- Why this could be real: the failing path bypasses the fixture-provided Redis client and reaches an uninitialized global client.

---

## Notes on the test-audit context

These bugs were surfaced during the test-harness audit (PRs #1-#4). The audit pattern was: when a test fails because it imports a symbol from prod code that no longer exists OR asserts behavior X but prod returns X', classify the failure as either (a) stale test (delete it) or (b) prod bug candidate (file it here, don't delete the test).

Items in this file are in the (b) category. Item 1 is unambiguously a bug (the call site is live, the function isn't defined). Items 2-3 may be (a) if `test.proceed` and `test.run` events are no longer supported. Items 4-7 are schema/migration gaps. Items 8-9 are lifespan-coupling bugs (production code reaches into globals instead of accepting injected dependencies, making tests harder to isolate).

---
## Phase 1.3

1. Route test clients still reference route modules that no longer exist.
   Affected route buckets include activity, attempt workflow, benchmark,
   dashboard, group, health, leaderboard, pricing, profile context/emulation,
   reports, session, and test workflow. The tests assert mounted HTTP route
   stacks, while production currently exposes several of these as single-module
   routers or renamed workflow endpoints. Suggested direction: decide whether
   the public route contract should preserve the older endpoints or migrate the
   route tests to the current route package layout with explicit compatibility
   coverage.

2. Generic artifact update endpoints reject route-test payloads that use
   `<artifact>_id`; production validators now require `id` inside each update
   item. Affected tests include update-route coverage for agent, auth, cohort,
   department, document, eval, field, model, parameter, provider, rubric,
   scenario, setting, simulation, and tool. Suggested direction: confirm the
   public API field name and either accept the documented legacy id alias or
   update route contract docs/tests together.

3. Generic artifact draft endpoints return `405 Method Not Allowed` for several
   route tests that expect draft creation through `/<artifact>/draft`. Affected
   buckets include auth, department, document, eval, field, model, parameter,
   provider, rubric, scenario, setting, simulation, and tool. Suggested
   direction: confirm whether draft routes are still public POST endpoints and
   restore router wiring or retire the route contract explicitly.

4. Generic artifact docs/export/refresh routes disagree with route-test
   contracts. Remaining failures include `404 Not Found`, missing request body
   validation errors, and response-key mismatches such as missing `content`,
   `mime_type`, or expected refresh view lists. Suggested direction: audit the
   generated route helper contract for these shared endpoints before changing
   individual assertions.

5. Draft entry primitives no longer accept the `group_id` keyword used by route
   tests for owned-draft setup. Affected tests include agent, cohort, persona,
   and scenario draft-list coverage. Suggested direction: either restore the
   setup API alias or migrate tests to the new draft primitive contract after
   confirming the intended ownership model.

---
## Phase 1.5

1. `core/tests/infra/stream/test_registry.py::test_domain_events_do_not_collide_with_lifecycle_events`
   asserts that public domain event names must be distinct from lifecycle event
   names. Production currently registers `system.group_generate.started` and
   `system.group_generate.completed` as both domain events and generated
   lifecycle events. Suggested direction: rename the domain events or disable
   default lifecycle generation for that operation so clients do not receive
   ambiguous event types.
