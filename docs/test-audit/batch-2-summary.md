# Batch 2 Summary

Status: STOPPED before quarantine/delete sweep.

## Survey

- Confirmed collection: `6976 tests collected`.
- First maxfail sample: 200 failures from 200 reported failed tests.
- Full failure survey after six obvious local fixes: 1,528 failed tests across 570 unique files.
- This exceeds the Batch 2 quarantine/delete cap of 100, so the sweep stopped before deleting or xfail'ing tests.

## Failure Pattern Breakdown

Counts below are from `/tmp/batch2-all-failures.txt`, grouped by failing test path and representative traceback samples.

| Pattern | Count | Notes |
| --- | ---: | --- |
| Tool/entry/resource helper drift | 735 | `core/tests/tools/entries/**` and `core/tests/tools/resources/**`; broad helper contract drift beyond Batch 2 cap. |
| Route contract drift | 246 | `core/tests/infra/routes/**`; old route expectations and request/response shapes. |
| Artifact impl direct-call drift | 238 | `core/tests/infra/{agent,auth,cohort,...}/**`; old kwargs such as `items=`, removed monkeypatch targets such as `invalidate_tags`, and stale direct-call collaborators. |
| Removed attempt modules | 15 | Tests import removed modules such as `app.infra.attempt.end`. |
| Other infra drift | 294 | Identity, health, pricing, session, stream event, and dashboard-adjacent failures. |

## Deletions

None. The full failure set exceeded the quarantine cap before a delete list could be applied safely.

## Files Updated

These are FIX-category updates made before the stop condition became clear:

- `core/tests/infra/agent/test_delete.py`
- `core/tests/infra/agent/test_duplicate.py`
- `core/tests/infra/agents/test_generic_agent.py`
- `core/tests/infra/agents/utils/test_build_hint_agent.py`
- `core/tests/infra/agents/utils/test_build_voice_agent.py`
- `core/tests/infra/dashboard/test_builders.py`

Targeted verification for these files:

```text
.venv/bin/python -m pytest core/tests/infra/agent/test_delete.py core/tests/infra/agent/test_duplicate.py core/tests/infra/agents/test_generic_agent.py core/tests/infra/agents/utils/test_build_hint_agent.py core/tests/infra/agents/utils/test_build_voice_agent.py core/tests/infra/dashboard/test_builders.py --tb=short -q
28 passed, 1 warning
```

## XFAILs

None.

## Coverage

Not measured. Per Batch 2 acceptance rules, `make test-cov` was not run after the full survey showed 570 failing files, which would require quarantine or rewrites beyond the cap.

## Commands Run

- `git switch -c test-audit/batch-2`
- `.venv/bin/python -m pytest core/tests/ --co -q 2>&1 | tail -3`
- `.venv/bin/python -m pytest core/tests/ --tb=line -q --maxfail=200 2>&1 | grep -E "^(FAILED|ERROR)" > /tmp/batch2-failures.txt`
- `.venv/bin/python -m pytest core/tests/ --tb=line -q 2>&1 | grep -E "^(FAILED|ERROR)" > /tmp/batch2-all-failures.txt`
- targeted pytest runs for representative files and fixed files

## Remaining Risks

- The suite rot is wider than Batch 2's intended stale-test sweep. A mass delete/XFAIL would exceed the explicit cap and risks deleting behavior tests mixed into stale implementation-shape tests.
- Many failures are not simple import errors or one-line signature renames; they include route response-shape drift, removed collaborators, and helper-layer contract changes.
- Recommended next strategy: create a broader production/test contract investigation batch, or split by subsystem with separate caps for `tools/entries`, `infra/routes`, and artifact direct-call tests.
