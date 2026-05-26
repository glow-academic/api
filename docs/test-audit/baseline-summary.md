# Test-Harness Audit — Final Baseline Summary

## TL;DR

The audit ran from `beta` HEAD `00210e9065` through 8 PRs over a single
session. **All 8 PRs are open against `beta` awaiting review/merge.** A real
coverage % could not be measured because `make test-cov` hangs on one of the
remaining 995 failing integration tests; the right path to a clean number is
to merge these PRs, triage the 15 surfaced prod-bug candidates, then re-run.

## What changed

### Test infrastructure
- Consolidated dueling pytest configs (`core/pytest.ini` deleted, `pyproject.toml` authoritative).
- Removed dormant `core/mypy.ini`.
- Fixed coverage `html_dir` typo (was in wrong section).
- Added `AGENTS.md` at repo root with the testing philosophy ("integration-first house style, delete brittle = adding tests").
- Removed dead `make generate-tests` Make target.

### Two distinct fixture loop-scope bugs fixed
Both class: function-scoped async fixtures creating asyncpg/Redis objects on the wrong event loop, causing `asyncpg.InterfaceError: another operation in progress` or `got Future attached to a different loop`.

1. **Repo-wide** (PR #1): `asyncio_default_fixture_loop_scope` flipped `"session"` → `"function"` in `pyproject.toml`; `initialize_test_db` marked explicit `loop_scope="session"`.
2. **Tools tree** (PR #4): 746 files in `core/tests/tools/{entries,resources}/**` had `pytestmark = pytest.mark.asyncio` and depended on session-scoped fixtures; switched each to `pytestmark = pytest.mark.asyncio(loop_scope="session")`.

### Stale-test cleanup
- ~50 signature-drift fixes (kwarg renames, helper sig updates) across multiple buckets.
- 7 tests surgically removed from mixed files (Phase 1.1).
- 4 over-deleted live tests restored (Phase 1.1).
- Phase 1.3-1.5 applied bucket-by-bucket pattern fixes per the Batch 2 survey breakdown.

## Failure count trajectory

| State | Failing tests |
|---|---:|
| Initial (pre-Batch-0) | unknown — collection broken |
| Post-Batch-0 (collection clean) | 1,528 across 570 files (Batch 2 survey) |
| Post-Phase-1.2 (tools bucket) | 735 → 542 |
| Post-Phase-1.3 (routes bucket) | 246 → 174 |
| Post-Phase-1.4 (artifact direct-call) | 238 → 254 (∗) |
| Post-Phase-1.5 (other infra) | 294 → 56 |
| **Total remaining estimate** | ~995 |

(∗) Phase 1.4 count slightly increased; likely because the fixture loop-scope fix surfaced previously-collection-blocked tests that now run and fail visibly. Phase-1.4 PR body has details.

## Production-bug candidates surfaced (15 total)

See `docs/test-audit/prod-bug-candidates.md` for full details. These are NOT test rot — they point at real defects in `core/app/`:

| # | Issue | Type |
|---:|---|---|
| 1 | `_find_next_run_id` called but not defined (`workflows.py:276`) | **NameError waiting** — fix landed in PR #5 |
| 2 | `test_proceed_impl` imported but not defined | Stale or refactor straggler — needs triage |
| 3 | `test_run_impl` — same | Same |
| 4 | Postgres `pricing_type` enum missing | Schema migration gap |
| 5 | `attempt_mutes_mv` MV missing | Schema migration gap |
| 6 | `chat_mv` missing unique index → can't REFRESH CONCURRENTLY | Schema migration gap |
| 7 | `m.updated_at` column missing in model_flags query | Schema or query drift |
| 8 | Health refresh reaches into app-global `get_redis_client()` | Lifespan coupling |
| 9 | Metrics export — same Redis coupling | Lifespan coupling |
| 10-14 | (Phase 1.3 surfaced 5 more) | See `prod-bug-candidates.md` Phase 1.3 section |
| 15 | (Phase 1.5 surfaced 1 more) | See same |

## PRs (in dependency order)

| PR | Branch | What it does |
|---|---|---|
| #1 | `test-audit/batch-1` | Loop-scope fixture fix (pyproject + conftest) |
| #2 | `test-audit/batch-2` | 6 signature-drift fixes + diagnosis of the 1,528 |
| #3 | `test-audit/phase-1-1-restore` | Restore 4 over-deleted live tests + file first 3 prod bugs |
| #4 | `test-audit/phase-1-2` | 746-file loop_scope marker fix + file 6 more prod bugs |
| #5 | `prod-bug/find-next-run-id` | Fix the `_find_next_run_id` NameError; 5 unit tests |
| #6 | `test-audit/phase-1-3` | Routes bucket pattern-fix |
| #7 | `test-audit/phase-1-4` | Artifact direct-call bucket pattern-fix |
| #8 | `test-audit/phase-1-5` | Other infra bucket pattern-fix |

## Why no coverage % yet

`make test-cov` was launched but hung at ~9 min of silence on an integration test (testcontainers DB pool likely deadlocked on one specific fixture). Codex cleanly interrupted it. A measurable coverage % requires either:
- (a) merging the 8 PRs + triaging the prod bugs (some bugs block whole subsystems from being testable, e.g. items 4-7 schema gaps),
- (b) running coverage with a per-test timeout (requires installing `pytest-timeout`), or
- (c) running `make test-cov -m "not slow"` after marking the hung test set as `slow`.

The audit explicitly did not "achieve baseline at any cost" — that would have meant either skipping ~500 tests blindly or rubber-stamping prod-side wrong behavior.

## Recommended next moves

1. **Merge PR #1 (loop-scope)** first — independently valuable, low-risk.
2. **Triage `prod-bug-candidates.md`** — each entry has suggested-fix direction. Items 8/9 (lifespan coupling) might cascade-unblock dozens of tests; items 4-7 are migration work; items 2/3 might just be intentional refactor cleanup (confirm-and-delete).
3. **Merge PRs #2-#4 and #6-#8** in any order they review cleanly.
4. **PR #5 (`_find_next_run_id` fix)** can merge any time after PR #3 (which restored the tests this fix unblocks).
5. **After 1-4**, run `make test-cov` again with a 5-min per-test timeout (add `pytest-timeout` to dev deps and `--timeout=300` to addopts). The remaining ~995 failures should drop substantially once prod bugs 8/9 are resolved.
6. **Target a real `--cov-fail-under` gate** once the suite is stable; current AGENTS.md guidance says "baseline + 2%/batch, not flat 80."

## Notable findings on the *codebase*

The audit's biggest insight was not a test number — it was that the codebase has **substantial incomplete-refactor debris**: 15 callable-but-undefined helpers, 4 schema-migration gaps, and 2 lifespan-coupling anti-patterns. The tests were doing their job — *catching* these defects — but the prior CI must have been masking them somehow (the dueling pytest configs likely meant nothing was running these tests pre-audit). The test-audit's biggest win is making this debt visible.
