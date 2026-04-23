# MCP exploration — search_content axis 1

Walked 12 probes against `search_content`, varying only inputs. Two real bugs surfaced in the shared dispatch layer, plus minor UX issues.

## Probe log

| # | Args | Result | Notes |
|---|---|---|---|
| 1 | `artifact=persona` | ✓ 9 personas rendered | Baseline |
| 2 | `artifact=persona, operation=search` | ✓ 9 personas | Explicit `operation` matches the collapsed default |
| 3 | `artifact=persona, operation=get` | ✓ `spec_invalid: (persona, get) not permitted` | Correct reject |
| 4 | `artifact=cohort` | ✓ `spec_invalid: (cohort, search) not permitted` | Correct reject |
| 5 | `artifact=persona, search="aggressive"` | ✓ 3 results | Search filter works |
| 6 | `artifact=persona, page=0` | ⚠ returned all 9 | Bug 1: `page` silently ignored by handler |
| 7 | `artifact=persona, page=99, page_size=5` | ⚠ returned page-1 slice + "4 more available" | Bug 1 again |
| 8 | `artifact=persona, page_size=0` | "No personas found." | Accepted; minor polish opportunity |
| 9 | `artifact=persona, page_size=1000` | ✓ all 9 | Large page_size capped at total |
| 10 | `artifact=scenario, page_size=3` | ✗ `search_scenario_impl() got unexpected 'session_id'` | Bug 2 |
| 11 | `artifact=document, page_size=3` | ✗ same | Bug 2 |
| 12 | `artifact=rubric, page_size=3` | ✗ same | Bug 2 |

## Bug 1 — `page` does nothing (pagination silently ignored)

Tool surfaces `page` (1-based, LLM-friendly) but `search_*_impl` handlers expect `page_offset` (0-based row offset). No translation. `search_personas_impl` has `**_kwargs` which swallows the unknown `page=…` silently. Handler never sees useful pagination.

Core fix: translate in the tool seed's `args_outputs` Jinja:
```python
{"name": "page_offset", "template": "{{ ((page|int - 1) * (page_size|int)) if page|int > 1 else 0 }}"}
```
Tool-seed-layer, affects every search tool. Lower urgency — returns data, just wrong slice.

## Bug 2 — context kwargs leak to handlers that don't accept them

`execute_infra_operation` kwargs path passes a full context dict to every handler: `profile_id, session_id, group_id, run_id, soft, accept, idempotency_key`. `search_personas_impl` has `**_kwargs` and absorbs extras. `search_scenario/document/rubric` don't — they TypeError on unknown kwargs.

Cross-handler inconsistency (some have `**_kwargs`, some don't), but the canonical fix is in the dispatch layer: filter `ctx_kwargs` by the handler's signature, same as we already do for data kwargs via `_coerce_kwargs_to_signature`. One MCP-layer change benefits all kwargs-path handlers.

## Minor polish

- Template renders raw JSON on error (probe 10–12) because `r.result` is `None` and `r.result.get("detail")` throws in Jinja → fallback. Template should guard with `r.result and r.result.get(...)`.
- `page_size=0` template says "No personas found." Could say "9 total, 0 requested."
- `spec_invalid` / `permission_denied` errors return raw JSON. Could template.

## Order of fixes

1. Bug 2 first — breaks 3 of 4 artifacts. `execute_infra_operation.py` kwargs branch.
2. Template robustness — one line in `search-content.jinja`.
3. Bug 1 (pagination translation) — tool-seed `args_outputs`. Lower urgency, wider change.
