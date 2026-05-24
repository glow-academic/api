# Phase 1.5 Summary

Status: `[phase-1.5] DONE pr=#8 failures_remaining=56 prod_bugs=+1`

Target bucket:

- `core/tests/infra/identity/`
- `core/tests/infra/health/`
- `core/tests/infra/pricing/`
- `core/tests/infra/session/`
- `core/tests/infra/stream/`
- `core/tests/infra/dashboard/`

## Survey

Initial command:

```bash
.venv/bin/python -m pytest core/tests/infra/identity core/tests/infra/health core/tests/infra/pricing core/tests/infra/session core/tests/infra/stream core/tests/infra/dashboard --tb=line -q
```

Initial failures surveyed: 78.

This is far below the Batch 2 estimate of about 294 because Phase 1.5 was scoped
to the named "other infra drift" directories only.

After applying the loop-scope pattern and quarantining one prod-bug candidate,
the target bucket has 56 remaining failures:

```text
56 failed, 160 passed, 1 skipped, 1 warning in 9.16s
```

## Pattern Breakdown

| Pattern | Count | Notes |
| --- | ---: | --- |
| `RuntimeError: Redis client not initialized` | 18 | Direct calls still reach global Redis instead of injected fixtures/lifespan state. |
| `AttributeError` | 16 | Mostly stale fake objects or monkeypatch targets after implementation refactors. |
| `TypeError unexpected/missing arguments` | 12 | Factory and route helper signatures drifted. |
| `AssertionError` / HTTP mismatch | 7 | Needs careful follow-up; one was quarantined as a prod-bug candidate. |
| `KeyError` | 3 | Identity simulatable role map expectations drifted. |

## Fixes Applied

| Fix | Files |
| --- | ---: |
| Added `loop_scope="session"` to async test marks in the Phase 1.5 bucket. | 37 |
| Quarantined confirmed prod-bug candidate with TODO skip marker. | 1 |

No production code was changed.

## Files Deleted

None.

## Files Quarantined

| Test | Reason |
| --- | --- |
| `core/tests/infra/stream/test_registry.py::test_domain_events_do_not_collide_with_lifecycle_events` | Production registers `system.group_generate.started` and `system.group_generate.completed` as both domain events and generated lifecycle events. TODO points to `docs/test-audit/prod-bug-candidates.md`. |

## New Prod-Bug Candidates

Count: 1.

Added under `## Phase 1.5` in `docs/test-audit/prod-bug-candidates.md`.

## Verification

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest core/tests/infra/identity core/tests/infra/health core/tests/infra/pricing core/tests/infra/session core/tests/infra/stream core/tests/infra/dashboard --tb=line -q` | Failed: 56 failed, 160 passed, 1 skipped. |
| `.venv/bin/python -m pytest core/tests/ --co -q` | Passed: 6976 tests collected. |
| `make lint` | Failed with existing repo-wide ruff backlog: 29938 errors. |
| `make typecheck` | Failed: `mypy: can't read file 'core/utils': No such file or directory`. |

## Remaining Failures

Remaining failures after fixes: 56.
