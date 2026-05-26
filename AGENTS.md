# AGENTS.md

Instructions for AI coding agents (Codex, Claude Code, etc.) working in this
repo. Keep this file short. Add rules only after seeing the same mistake twice.

## Repo layout

- Source:  `core/app/` (Python 3.11, FastAPI + asyncpg + Redis)
- Utils:   `core/utils/`
- Tests:   `core/tests/{unit,infra,tools,utils}/`
- Shared fixtures: `core/tests/conftest.py` — provides `pool`, `redis_client`,
  and `*_factory` fixtures backed by a real Postgres (testcontainers) + Redis.
  Reuse them; do not introduce a parallel mocking style.
- Config:  `pyproject.toml` is authoritative for pytest, ruff, mypy, coverage.

## Commands

| Task         | Command           |
| ------------ | ----------------- |
| Run tests    | `make test`       |
| Coverage     | `make test-cov`   |
| Lint         | `make lint`       |
| Type-check   | `make typecheck`  |
| Format       | `make format`     |
| OpenAPI gen  | `make openapi-gen`|

Pass extra args via `ARGS="-k pattern"` (e.g. `make test ARGS="-k persona"`).

## Async testing

`asyncio_mode = strict`. Every async test needs `pytestmark = pytest.mark.asyncio`
at module level (preferred) or `@pytest.mark.asyncio` per test. Forgetting this
silently skips the test.

**Loop-scope alignment** — when your test depends on a *session*-scoped fixture
(like the `pool`/`conn`/`redis_client` family from `core/tests/conftest.py`,
which spin up testcontainers once per session), the test's event loop must
match. Use:

```python
pytestmark = pytest.mark.asyncio(loop_scope="session")
```

Plain `pytest.mark.asyncio` defaults to function-scope and produces
`asyncpg.InterfaceError: cannot perform operation: another operation is in
progress` or `got Future attached to a different loop` on teardown. This
class of bug was found twice during the test-harness audit — once at the
config level (`pyproject.toml`'s `asyncio_default_fixture_loop_scope`) and
once at 746 individual test files. Don't introduce it a third time.

## Per-test timeout

`--timeout=300` (5 min) is set in `pyproject.toml` via `pytest-timeout`.
Individual tests will be killed if they hang; this prevents a single
deadlocked test from holding the entire `make test-cov` run hostage.
If you genuinely need a longer test, override per-test with
`@pytest.mark.timeout(600)`.

## Testing philosophy

- Tests lock down **intended behavior**, not accidental implementation.
- House style is integration-first against real Postgres + Redis. **Do not** add
  DB or Redis mocks — use the existing `pool` / `redis_client` fixtures.
- Mock only true external boundaries the conftest doesn't already cover:
  outbound HTTP (use `respx`), LiteLLM/OpenAI calls, filesystem, current time,
  randomness, subprocesses.
- If production logic is broken or its contract is unclear, fix or refactor the
  code, then test the intended behavior. Do not pin broken behavior in a test.
- Treat already-tested primitives as black boxes.
- Do not assert internal call sequences unless that sequence IS the behavior
  being guaranteed (e.g. a transactional invariant).
- **Deleting brittle/dead tests is as valuable as writing new ones.** Empty
  files, zero-import test files, tests that only count mock calls, and tests
  that mirror implementation details should be removed.

## Test conventions

- Name by behavior: `test_returns_none_when_profile_missing`, not `test_get_profile_2`.
- One module-level `pytestmark = pytest.mark.asyncio` instead of per-test marks.
- Use existing factory fixtures (`profile_identity_factory`, etc.) before
  hand-building objects.
- Parametrize repeated input/output cases.
- No `sleep()`. Use a fake clock if needed.
- No tests that depend on execution order.
- Use the existing markers: `fast`, `slow`, `unit`, `integration`.

## Refactoring rules for testability

- Introduce a boundary only when code touches: DB, HTTP, filesystem, clock, RNG,
  env, subprocess, queue, or LLM/API client.
- Do **not** thread pure helper functions through call signatures — that's fake
  dependency injection and makes the code worse.
- Preserve public response shapes unless the task explicitly asks to change
  them. If a shape must change, call it out in the PR summary.

**Lifespan-coupling anti-pattern (learned twice from the audit).** Production
helpers should not reach for FastAPI-lifespan globals (`get_redis_client()`,
`get_pool()`, etc.) deep in their call chain — only the *boundary* layer
(server lifespan, collector modules) should touch those globals, and inject
the resolved client downward as an explicit parameter. Why: helpers that
call `get_redis_client()` silently work in production but raise
`RuntimeError: Redis client not initialized` from any test or non-lifespan
caller, making the helper untestable without standing up the whole app.

If you're writing a function that needs Redis/pool/the system session id,
take it as a parameter. The caller in the lifespan boundary passes
`get_redis_client()` once. Tests pass the `redis_client` fixture from
conftest.

## Surfacing prod bugs vs. updating tests

When a test fails because production returns something different from what
the test asserts — **stop and classify**:

- **Test asserts call shape that no longer exists** (`TypeError`,
  `AttributeError` from a renamed kwarg, `ImportError` from a renamed module):
  prod refactor was clean, test is stale. Update or delete the test.
- **Test asserts behavior X, prod returns X'** (logically different output
  for the same input): **do not silently update the test.** This is the
  signature of a real production regression. File an entry in
  `docs/test-audit/prod-bug-candidates.md` with file:test_name + what was
  asserted + what prod returns + a suggested fix direction. Skip-mark the
  test with a TODO pointing to the doc, or leave it red.

The test-harness audit found 15 distinct prod-bug candidates this way. Don't
let the count grow silently by rubber-stamping prod into tests.

## Coverage

- Branch coverage is on: `--cov-branch`.
- Do **not** raise `--cov-fail-under` without first measuring the baseline.
  Each batch should either raise coverage by ≥2% OR delete brittle tests
  without losing coverage. Both count as wins.
- HTML report lands at `core/htmlcov/index.html`.

## Done means

- `make test` passes.
- `make test-cov` runs cleanly; coverage delta reported in PR body.
- `make lint` and `make typecheck` pass.
- PR summary lists: files changed, tests added, tests deleted/rewritten,
  coverage before→after, commands run, remaining risks.
- No new mocks for things the conftest already provides.
- No new test files with zero imports from `core/app/`.

## Stop and ask

- A change would alter a public API response shape.
- A test is failing for a reason that suggests a real production bug.
- A refactor would change behavior of code that is not part of the current task.
- The contract of a function is ambiguous and tests would be guessing.
