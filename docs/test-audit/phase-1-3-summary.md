# Phase 1.3 Summary

Target: `core/tests/infra/routes/**`

Final status: `[phase-1.3] DONE pr=TBD failures_remaining=174 prod_bugs=+5`

## Survey

| Run | Failures/errors |
| --- | ---: |
| Initial requested survey | 257 |
| After route loop-scope fix | 246 |
| After Phase 1.3 mechanical fixes | 174 |

The initial count was slightly above the expected ~246. After applying the
session loop scope, the count matched the expected route-drift baseline exactly.

## Pattern Breakdown

| Pattern | Final count | Action |
| --- | ---: | --- |
| Missing route modules / stale route-client imports | 74 | Documented as prod-bug candidate group; left failing |
| Assertion/status/response-shape drift | 66 | Documented as prod-bug candidate groups; left failing |
| TypeError signature drift | 19 | Fixed broad duplicate-argument pattern; remaining draft primitive drift documented |
| KeyError response-shape drift | 12 | Documented as shared docs/export response drift |
| AttributeError signature/model drift | 1 | Fixed `parameter_id` in field route setup; one route response drift remains |

## Fixes Applied

| Pattern | Files |
| --- | ---: |
| Added `loop_scope="session"` to class-level route async marks | 28 route test files |
| Removed duplicated `redis_client` argument in helper route create calls | 17 route test files |
| Route actor now creates real permission resources for requested artifacts | 1 shared route helper |
| Updated route draft group setup to pass Redis into `create_group` | 4 route test files |
| Updated field route setup to use `parameter_id` from `GetParameterResponse` | 1 route test file |
| Corrected agent get-route editability expectation for an actor with update permission | 1 route test file |

## Files Deleted

None.

## Files Quarantined

None. Remaining route-contract failures were left visible rather than
skip-marked because the bucket still has broad shared drift and quarantining all
affected tests would exceed the Phase 1.3 quarantine cap.

## New Prod-Bug Candidates

Count: 5 grouped candidate entries added in
`docs/test-audit/prod-bug-candidates.md` under `## Phase 1.3`.

## Verification

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest core/tests/infra/routes/ --tb=line -q` | 100 failed, 84 passed, 74 errors; 174 remaining |
| `.venv/bin/python -m pytest core/tests/ --co -q` | Passed; 6976 tests collected |
| `make lint` | Failed on existing repo-wide lint backlog; 29942 errors reported |
| `make typecheck` | Failed: `mypy: can't read file 'core/utils': No such file or directory` |

## Remaining Risk

The route bucket still has large public-contract drift. I did not change
production code or silently update assertions for the unresolved route behavior
differences.
