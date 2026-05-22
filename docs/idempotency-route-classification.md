# Route classification: idempotency & snapshot keys — what every route needs

**Companion to** `idempotency-and-snapshots-audit.md`. Classifies every route and
states exactly what to add. **v2 — corrected**: field presence is now measured at
the **request-type level** (the accurate source), not by scanning thin route files.
v1 over-stated the gaps because the thin routes pass the whole `request` object and
the impl extracts the key, so the route text rarely names `idempotency_key`.

**Scope:** 469 routes across 20 artifact routers. The ~13 single-segment OIDC/identity
routes (`/login`, `/token`, `/me`, `/.well-known/*`, …) are out of scope. The `/auth/*`
router is the auth-*artifact* CRUD surface (in scope), not the OIDC flow.

## Corrected coverage (the headline)

The **field contract is largely already in place** following the canonical pattern:

- **181 write routes** (MUTATION + AI_GENERATE).
  - **122 already declare `idempotency_key`** on their request type — all 6 standard
    mutations (`create/update/delete/duplicate/draft/problem`) across the 17 uniform
    artifacts, plus every `generate` (shared `ArtifactGenerateRequest`). These need
    **only the replay gate wired** — no field work.
  - **59 genuinely lack the field**: the bespoke `attempt` (`chat_*`, `start`, `stop`,
    `complete`, …), `test` (`invocation_*`, `grade`, `feedback`), `system` ops, plus
    `export` and the per-artifact `*_upload`s.
- **`snapshot_key`** is declared on the `Get*` request of all 17 uniform artifacts
  (scenario was the lone gap — **fixed in this change**), and persona additionally on
  Export/Generations. It is **declared-but-unused** everywhere (no handler honors it).

So the work splits cleanly:

1. **The replay GATE** (the real retry-safety behavior) — missing on **all 469**
   routes. This is **not an existing pattern to copy**; it's the contested design
   escalated to product (coexist-vs-unify, storage, key naming). **Not built here.**
2. **Field/contract gaps** — 59 write routes need `idempotency_key` added, and
   `scenario` needed `snapshot_key`. These follow the canonical pattern and are safe.
3. **Honoring snapshot_key** on the 62 paginated reads — real impl work, design-gated.

## Per-operation category counts

| category | # routes |
|---|---|
| MUTATION | 153 |
| READ_FILE | 85 |
| READ_LIST | 62 |
| READ_SINGLE | 59 |
| READ_MINT | 40 |
| AI_GENERATE | 28 |
| STREAM | 21 |
| REFRESH | 20 |
| PROBE | 1 |

## Priority rollup

| priority | # routes | meaning |
|---|---|---|
| P0 | 28 | AI generation — wire gate (double-billing) |
| P1 | 153 | mutation — wire gate (+add field on the 51 bespoke) |
| P2 | 62 | paginated read — honor snapshot_key |
| P3 | 21 | stream resume |
| P4 | 59 | optional single-read snapshot |
| none | 146 | downloads / group-title / refresh / probe |

## What was changed in this pass (safe, pattern-following)

- **`scenario`: added `snapshot_key` to `GetScenarioApiRequest`** to match the 16
  sibling artifacts (identical field + description). Verified: the get route passes
  named args (not a blind spread) and the impl takes `**_kwargs`, so it is inert like
  every sibling — zero behavior change, contract now uniform.
  ⚠️ Run `make openapi-gen` to refresh `core/openapi.json` (not regenerated here —
  the file was already dirty in the working tree).

## Deliberately NOT changed (and why)

- **The replay gate** — contested/paused pending product; not an existing pattern.
- **`attempt`/`test`/`system` idempotency_key** — the canonical pattern *is* the
  soft/accept dormant-ledger flow, which does not cleanly fit `chat_message`,
  `chat_response`, `invocation_run`, etc. Wiring it blindly would be semantically
  wrong; these need per-op design.
- **Honoring snapshot_key** on reads — requires real point-in-time logic, design-gated.

---

## Full per-route classification


### `/agent/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/attempt/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| archive | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| audio_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| audio_upload | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| chat_analyses | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| chat_audio | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| chat_complete | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| chat_create | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| chat_feedback | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| chat_get | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| chat_grade | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| chat_hints | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| chat_improvements | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| chat_message | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| chat_response | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| chat_silence | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| chat_speak | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |
| chat_strengths | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| chat_voice | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| complete | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| dashboard | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| draft | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| file_preview | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| home | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| image_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| leaderboard | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| practice | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| problem | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| report | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| start | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| stop | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| video_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/auth/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/cohort/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/department/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/document/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| file_preview | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| file_upload | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| text_upload | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/eval/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/field/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/model/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/parameter/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/persona/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | ✓ | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | ✓ | P2 | Honor snapshot_key to pin pagination. Field present but UNUSED. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/profile/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| emulate | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| unemulate | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/provider/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| decrypt | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/rubric/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/scenario/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| file_preview | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| image_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| image_upload | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| video_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| video_upload | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/setting/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| decrypt | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/simulation/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/system/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| activity | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| audio_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| file_preview | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| groups | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| health | PROBE | · | · | none | Out of scope — probe. |
| image_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| pricing | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| problem | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| resolve | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| session | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| sessions | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| video_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/test/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| archive | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| benchmark | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| complete | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| decrypt | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| draft | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| feedback | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| grade | AI_GENERATE | · | · | P0 | idempotency_key field ABSENT — add; wire replay GATE (missing). DOUBLE-BILLING. |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| invocation_complete | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| invocation_create | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| invocation_get | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| invocation_run | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| invocation_terminate | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| invocation_trace | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| invocations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| problem | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| start | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| stop | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |

### `/tool/*`

| op | cat | idem field | snap field | pri | action |
|---|---|---|---|---|---|
| call_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| context | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| create | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| csv | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| delete | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| draft | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| drafts | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| duplicate | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| export | MUTATION | · | · | P1 | idempotency_key field ABSENT — add field + gate. |
| file_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| generate | AI_GENERATE | ✓ | · | P0 | idempotency_key field PRESENT; wire replay GATE (missing). DOUBLE-BILLING. |
| generations | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| get | READ_SINGLE | · | ✓ | P4 | Retry-safe. snapshot_key field present (unused) — honor it for cross-call consistency (optional). |
| group | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| preview | READ_SINGLE | · | · | P4 | Retry-safe. snapshot_key field absent — honor it for cross-call consistency (optional). |
| problem | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| refresh | REFRESH | · | · | none | No change — idempotent debounced MV recompute. |
| search | READ_LIST | · | · | P2 | Honor snapshot_key to pin pagination. Field ABSENT — add it. |
| text_download | READ_FILE | · | · | none | Retry-safe — returns stored artifact by id. |
| title | READ_MINT | · | · | none | Already uses snapshot_key as group-convergence token. |
| update | MUTATION | ✓ | · | P1 | idempotency_key field PRESENT — wire replay GATE only. |
| watch | STREAM | · | · | P3 | Add resume token for mid-stream reconnect. |
