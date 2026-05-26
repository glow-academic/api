# Phase 1.4 Summary

Target:
`core/tests/infra/{agent,auth,cohort,department,document,eval,field,model,parameter,persona,provider,rubric,scenario,setting,simulation,tool}/**`

Final status: `[phase-1.4] DONE pr=TBD failures_remaining=254 prod_bugs=+0`

## Survey

| Run | Result |
| --- | --- |
| Initial survey | Interrupted at 57%; the run appeared stuck in `core/tests/infra/persona/test_context.py` before pytest emitted failure summary lines |
| After loop-scope fix | 254 failures, 720 passed |

The completed post-loop survey is close to the expected ~238 artifact
direct-call drift failures.

## Pattern Breakdown

| Pattern | Observed count in traceback lines | Notes |
| --- | ---: | --- |
| `TypeError` direct-call signature drift | 116 | Tests pass old kwargs such as `items`, `<artifact>_ids`, or `<artifact>_id` into refactored impl functions |
| `AttributeError` monkeypatch/import drift | 73 | Tests patch removed internals such as `resolve_profile_identity_context`, `invalidate_tags`, or old draft impl names |
| `AssertionError` response/status drift | 5 | Small set of section/export/auth expectations no longer matches current helper output |
| `ModuleNotFoundError` / `ImportError` | 0 | No collection/import failures after loop-scope fix |

## Fixes Applied

| Pattern | Files |
| --- | ---: |
| Added `loop_scope="session"` to artifact direct-call async marks | 211 test files |

No deletes or quarantines were applied in this phase. The remaining failures are
mostly stale direct calls and monkeypatches in tests that were already below the
HTTP route layer; changing production code or silently rewriting expectations
would be outside this phase.

## Files Deleted

None.

## Files Quarantined

None.

## New Prod-Bug Candidates

Count: 0.

## Verification

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest <phase-1.4 bucket> --tb=line -q` | 254 failed, 720 passed |
| `.venv/bin/python -m pytest core/tests/ --co -q` | Passed; 6976 tests collected |
| `make lint` | Failed on existing repo-wide lint backlog; 29938 errors reported |
| `make typecheck` | Failed: `mypy: can't read file 'core/utils': No such file or directory` |

## Remaining Risk

This PR intentionally leaves the direct-call contract drift visible. The next
productive step is deciding whether to delete the mock-heavy direct-call tests
or rewrite a small subset as integration tests against real Postgres/Redis.
