# Phase 1.2 Summary

Status: stopped, not green.

## Survey

- Initial scoped survey command produced 3,951 `FAILED`/`ERROR` lines, far above the prior ~735 target.
- Root cause of the inflated count: event-loop mismatch against session-scoped asyncpg/Redis fixtures.
- After adding `loop_scope="session"` to scoped module-level async markers, the scoped survey was 754 failures, close to the expected bucket.
- After bulk signature/import drift fixes, the scoped run ended at 511 failed test lines plus 31 erroring tests: `511 failed, 2776 passed, 1 warning, 31 errors`.
- Full collection succeeds: `6976 tests collected`.

## Pattern Breakdown

| Error class | Count observed | Representative example |
| --- | ---: | --- |
| RuntimeError loop mismatch | 3,951 survey lines before fix | `got Future ... attached to a different loop` in `activity/test_create.py` |
| TypeError unexpected kwarg | 197 remaining | `create_attempt_chat() got an unexpected keyword argument 'call_id'` |
| TypeError positional drift | 29 remaining | `create_session() missing 1 required positional argument: 'redis'` |
| NameError | 32 remaining | `name 'created' is not defined` |
| AttributeError | 26 remaining | `GetParameterResponse object has no attribute 'id'` |
| AssertionError docs/signature drift | 37 remaining | docs tests expecting `group_id` / `group_ids` params no longer in signatures |
| asyncpg schema/data errors | 40+ remaining | missing `pricing_type`, `attempt_mutes_mv`, `m.updated_at`, missing draft connection IDs |
| Redis app-global errors | 6 remaining | `Redis client not initialized` in health/metrics refresh tests |

## Fixes Applied

| Pattern | Fix | Files affected |
| --- | --- | ---: |
| Async tests used function loop with session fixtures | Changed scoped `pytestmark = pytest.mark.asyncio` to `pytest.mark.asyncio(loop_scope="session")` | 746 |
| `get_*` calls passed `redis_client` before keyword IDs | Reordered calls to pass `ids=`/`*_ids=` before `redis=redis_client` | many generated get tests |
| `create_attempt` helpers still passed removed `call_id` | Replaced `call_id=call.id` for `create_attempt` setup helpers with `session_id=session.id` | attempt-family setup tests |
| Helper calls omitted `redis_client` | Added `redis_client` to helper calls and test fixtures where the helper signature required it | create/setup tests |
| flags resource create tests passed old icon string positional arg | Updated calls to use `redis=redis_client`; bare `get_flags` expectations now assert `icon is None` | flags tests |

## Deletions

None.

## Quarantines

None.

## Production Bug Candidates

Filed 6 candidates in `docs/test-audit/prod-bug-candidates.md`.

This exceeds the hard-rule threshold of more than 5 distinct prod-bug candidates, so Phase 1.2 stops here for human review instead of silently updating assertions or changing production code.

## Remaining Failures

- Total remaining scoped failure lines: 511.
- High-volume remaining signature drift: `create_attempt_chat(call_id=...)`, `create_attempt_message(message_id=...)`, `create_attempt_completion(call_id=...)`, `create_test_feedback(...)`, `create_run(profiles_id=...)`.
- Remaining non-obvious/prod candidates: schema/MV/type errors, app-global Redis usage, missing seed assumptions, draft connection not-null violations.

## Net Test Count Delta

- Baseline from task: 6,980.
- After Phase 1.2 edits: 6,976 collected.
- Net delta: -4 collected tests. No files were deleted in this batch; the delta appears to come from the current `beta` branch state rather than Phase 1.2 deletions.

## Commands Run

- `git switch beta && git pull --ff-only origin beta && git switch -c test-audit/phase-1-2`
- `.venv/bin/python -m pytest core/tests/tools/entries/ core/tests/tools/resources/ --tb=line -q 2>&1 | grep -E "^(FAILED|ERROR)" > /tmp/phase-1-2-failures.txt`
- `.venv/bin/python -m pytest core/tests/tools/entries/activity/test_create.py --tb=short -q`
- `.venv/bin/python -m pytest core/tests/tools/entries/ core/tests/tools/resources/ --tb=short -q > /tmp/phase-1-2-full-after-loop.txt 2>&1`
- `.venv/bin/python -m pytest core/tests/tools/entries/attempt/test_create.py core/tests/tools/entries/agent_drafts/test_get.py core/tests/tools/resources/flags/test_search.py --tb=short -q`
- `.venv/bin/python -m pytest core/tests/tools/entries/ core/tests/tools/resources/ --co -q`
- `.venv/bin/python -m pytest core/tests/tools/entries/ core/tests/tools/resources/ --tb=short -q > /tmp/phase-1-2-full-after-bulk2.txt 2>&1`
- `.venv/bin/python -m pytest core/tests/ --co -q > /tmp/phase-1-2-all-collect.txt 2>&1`

## Not Run

- `make lint`
- `make typecheck`
- PR creation

These were intentionally not run after the hard-rule stop condition was reached.
