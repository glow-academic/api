# Batch 1 Summary

Status: STOP. Batch 1 did not meet acceptance because `make test-cov` still
shows broad non-loop-scope failures and cannot complete to a measurable coverage
baseline.

## Diagnosis

The asyncpg teardown failure was caused by
`asyncio_default_fixture_loop_scope = "session"` in `pyproject.toml`.
That setting was dormant while `core/pytest.ini` was the active pytest config.
Commit `6c0f668419` promoted `pyproject.toml` to the authoritative config,
activating the session-loop fixture scope. Function-scoped async fixtures such
as `pool`, `conn`, and `redis_client` then created asyncpg/Redis objects on the
session event loop while tests executed on function event loops, corrupting
asyncpg state and surfacing as rollback teardown failures.

## Files Touched

- `pyproject.toml` - changed `asyncio_default_fixture_loop_scope` from
  `session` to `function`.
- `core/tests/conftest.py` - pinned `initialize_test_db` to
  `loop_scope="session"` while leaving per-test fixtures on the function loop.
- `core/tests/infra/artifacts/test_discovery.py` - quarantined one uncovered
  non-loop-scope failure exposed by the narrow diagnostic.

## Commands Run

- `make test ARGS="core/tests/infra/artifacts/test_discovery.py -q"`
  - Before quarantine: no `asyncpg.InterfaceError`; 10 passed, 1 failed.
  - After quarantine: 10 passed, 1 xfailed.
- `make test-cov`
  - Stopped early after broad failures unrelated to the loop-scope regression.
  - Collection count: 6,976 tests.
  - Run was terminated at 36% after many failures/errors across route and infra
    tests.

## Coverage

Coverage was not achieved. `make test-cov` did not complete, so there is no
valid total coverage percentage and no valid top-20 lowest-covered module table.

## Quarantined Tests

| Test | Root cause | TODO |
| --- | --- | --- |
| `core/tests/infra/artifacts/test_discovery.py::test_get_agent_end_event_name_handles_known_and_special_cases` | `get_agent_end_event_name(conn, "persona")` falls back to `text_end` because this fixture path does not expose a matching `permissions_resource` row for `persona`. This is independent of the asyncpg loop-scope fix. | delete after fix |

## Blocking Failures

`make test-cov` produced broad failures before coverage could complete. Early
examples included:

- `core/tests/infra/agent/test_create.py::*`
- `core/tests/infra/agent/test_drafts.py::*`
- `core/tests/infra/artifacts/test_stream_litellm_events.py::*`
- `core/tests/infra/routes/*/test_route.py::*`
- `core/tests/infra/tool/test_refresh.py::*`

These exceed the quarantine cap and include behavior-level route/infra failures,
so Batch 1 is stopped without a commit or PR.

## Remaining Risks

- The loop-scope regression appears fixed for the narrow diagnostic, but the
  suite still lacks a measurable baseline.
- Batch 2 should not start until the Batch 1 acceptance criteria are clarified
  or the broad pre-existing failures are handled.
