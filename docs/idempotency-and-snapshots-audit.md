# Audit: existing idempotency / snapshot / dedup machinery

**Status:** audit only — no design decisions, no implementation. Produced before
the design doc to establish ground truth, per the working constraint *"Read
existing code before designing. Don't propose a contract that contradicts what's
already partially there."*

**Repo audited:** `glow-academic-api` (public). The private `learnloopllc-glow-api`
mirror has near-identical hit counts (`idempotency` 2250 vs 2252, `operation_key`
341/341, `soft_calls_entry` 31/31, `snapshot` 446/446), so it is not a richer
upstream to crib from — it is the same code.

---

## TL;DR — the headline finding

The codebase already contains pervasive `idempotency_key`, `operation_key`,
`snapshot_key`, and `soft_calls_entry` machinery. **But it is not a partial
implementation of the retry-safety contract the brief describes — it is a
*different, fully-built feature* that reuses the same vocabulary.**

| Term in code | What the brief means | What it actually is here |
|---|---|---|
| `idempotency_key` | client token to dedup a retried mutation; same key ⇒ cached response | a `call_id` for a **two-phase "soft write → accept/reject" approval workflow** (draft a dormant change, then explicitly confirm it). No retry dedup. |
| `snapshot_key` | server-minted point-in-time token for consistent reads | a **client-supplied UUID used as a Redis `SET NX` race candidate** so concurrent fan-out reads converge on one `group_id`. No point-in-time view. |
| `operation_key` | "universal" unified key | persisted on `calls_entry` but **not used as a dedup gate**; the "idempotency_key for writes, snapshot_key for reads" comment is aspirational. |

**The central risk for the design work is a vocabulary collision.** If the new
retry-safety contract reuses the names `idempotency_key` / `snapshot_key`, it will
be conflated with two unrelated existing mechanisms. "Subsume or align with the
existing ledger" (the brief's instruction) is the wrong move here — the existing
ledger solves a different problem and should probably keep its names while the new
contract gets distinct ones.

So the realistic framing is **not** "finish the partial idempotency work." It is:
*the retry-safety / read-consistency contract the brief wants does not exist yet;
two similarly-named features do; design must avoid colliding with them.*

> **Correction (added after deeper read — supersedes the "no caching" claims below).**
> The retry-safety *plumbing* is more built than this audit first stated. Every
> audited route funnels through `run_artifact_operation_with_audit`, which (a)
> **pre-mints a stable `call_id` before execution** (`audit.py:235`) and (b) writes
> a **per-call JSON receipt** to `uploads/call/<call_id>.json`, appended-to as
> events fire (`create_tool_call`, `append_call_event`). What is genuinely missing
> is exactly **one** thing: a *pre-execution replay gate* — look up an existing
> receipt by the client's `operation_key` and return it instead of re-running. That
> gate exists on **0** routes (verified, including persona). So "build response
> caching from scratch" is wrong; "add the replay gate on top of the existing
> receipt store" is right. Full per-route breakdown:
> **`idempotency-route-classification.md`**.

---

## 1. Write side: what `idempotency_key` / `operation_key` actually do

### It is a draft-then-confirm approval flow, not retry dedup

The flow (e.g. `core/app/infra/auth/delete.py`, `core/app/infra/invocation/draft.py`):

1. **First call with `soft=True`** writes the artifact rows as `active=False`
   (dormant) and appends a `soft_calls_entry` row with `status="pending"`, keyed
   by `call_id = idempotency_key`.
2. **Follow-up call with `{idempotency_key, accept: true|false}`** looks up the
   ledger by `call_id` (`get_soft_call`), then promotes the dormant change
   (`accept`) or restores prior state (`reject`).

This is an **AI/human-in-the-loop approval gate** (LLM proposes a change → it sits
dormant → someone accepts it), not network-retry protection. The second call is
*intentionally a different request* (`accept` toggles), the opposite of classic
idempotency replay where the client resends the *same* request.

Evidence: `auth/delete.py:62-113` (ack/reject path), `invocation/draft.py:176-259`
(`idempotency_key = ... or request.draft_id`, accept promotes the dormant draft),
`execute_infra_operation.py:81` (`soft` = "create dormant records").

### None of the classic idempotency guarantees are present

| Guarantee the brief wants | Present? | Evidence |
|---|---|---|
| Pre-execution lookup-then-return-cached gate | ❌ | `calls/create.py:24-38` — `INSERT ... COALESCE($7, uuidv7())`; every call mints a fresh `call_id`, no `SELECT` before insert |
| UNIQUE constraint on `operation_key` | ❌ | no unique index in schema |
| Concurrency serialization (advisory lock / `FOR UPDATE` / `SET NX`) on writes | ❌ | none found around the write path; two concurrent same-key requests both execute |
| Request fingerprint / body hash | ❌ | `soft_calls_entry` stores a `patch` jsonb but no hash; same key + different body is silently accepted as a new ledger row |
| `409` on same-key-different-body | ❌ | no mismatch detection anywhere |
| Cached-response replay (same status/body/headers) | ❌ | the ledger stores state (`patch`), not the HTTP response |

**Net:** the framework does not prevent duplicate mutations on retry or
concurrent same-key requests. That safety property — the brief's whole point —
is unbuilt.

### Transport: envelope, not header

Keys are **request-body envelope fields** (Pydantic models), never HTTP headers.
`grep -ri "Idempotency-Key"` (header) returns nothing. They appear only on a
*subset* of mutations (delete / duplicate / problem / refresh / draft), not on all
450 POST mutations. So the codebase has effectively pre-decided the
"header vs envelope" question the brief flags — in favor of **envelope**, which
also matches the WebSocket-transport goal.

---

## 2. Read side: what `snapshot_key` actually does

### Real in exactly one place: group resolution

`core/app/infra/group/resolve.py` is the only genuine consumer:

- `snapshot_key` is a **client-supplied UUID candidate** (`resolve.py:328`
  `candidate = snapshot_key or _mint_group_id()`).
- It is used as a Redis `SET key val NX EX window` race (`resolve.py:329-368`):
  concurrent fan-out reads (e.g. a page firing `/persona/group` +
  `/persona/context` + `/persona/search` at once) converge on a single
  `group_id` instead of fragmenting.
- It is echoed back in the response (`resolve.py:466`
  `snapshot_key = snapshot_key or resolved_group_id`).

This is a **convergence coordinator**, not a snapshot. It is not a Postgres LSN,
txid, or MVCC snapshot; it pins nothing across time.

### Declared-but-unused everywhere else

`snapshot_key: str | None` with the identical description *"Cache snapshot key for
consistent reads across related requests"* is inherited onto the request/response
models of ~all resource namespaces (persona, agent, document, cohort, profile,
model, parameter, field, department, provider, simulation, system…). In every
handler sampled — `persona/get`, `agent/get`, `document/get`, `cohort/get`,
`persona/search` — **the handler never reads `request.snapshot_key`**; it is pure
declaration debt. (Sampled, not exhaustive across all 20 namespaces — confirming
the rest is a follow-up item.)

- **Pagination is offset-based** (`page_limit`/`page_offset`), not snapshot-pinned;
  multi-page reads are *not* point-in-time consistent.
- **Streams ignore it**: `GET /persona/watch` (SSE) takes only `group_id` /
  `run_id` (`routes/persona/watch.py:21-44`); no `snapshot_key`.

**Net:** point-in-time read consistency — the brief's snapshot-key goal — is
unbuilt outside group convergence.

---

## 3. Storage: `soft_calls_entry`

Real Postgres table (`database/schema/tables/entries/soft.sql:8-21`; mirror at
`database/schema.sql:11121`).

- **Columns:** `id` (uuidv7 PK), `created_at`, `call_id` (FK→`calls_entry`,
  CASCADE), `artifact`, `operation`, `status` CHECK ∈ {pending, accepted,
  rejected}, `artifact_id`, `patch` jsonb, plus `active`/`mcp`/`generated` flags.
- **Keyed by `call_id`**, not `operation_key`; **no UNIQUE on `call_id`** — it is an
  append-only ledger. `soft_calls_mv` collapses to latest-per-`call_id`
  (`DISTINCT ON`), refreshed by `refresh_soft_calls` (`REFRESH MATERIALIZED VIEW
  CONCURRENTLY`).
- **No TTL / GC.** `created_at` is used only for ordering. `refresh.py` is a view
  refresh, not a sweeper. Rows accumulate unbounded. (The brief assumes a bounded
  TTL exists; it does not.)
- **No request fingerprint** column.

### Crash-consistency gap (relevant to the brief's §5)

- Soft *create* writes the ledger row **inside** the business transaction
  (`auth/create.py:166-189`) — good; both roll back together.
- Soft *accept/reject* updates the ledger in a **separate** transaction from the
  business promotion (`auth/create.py:90-105`). Crash between them ⇒ artifact is
  live but ledger still says `pending`. This is exactly the "DB write succeeded
  but idempotency entry never persisted" failure the brief asks about — and it is
  currently unhandled.

---

## 4. Endpoint scope (validates the brief's premises)

- **482 paths, 450 POST / 32 GET.** This is an RPC-style POST-everything API.
  ⇒ **mutation-vs-read cannot be derived from HTTP method.** `/persona/get`,
  `/persona/search` are POST reads; `group/resolve` is a "read" that may *mint*.
  The per-endpoint table must classify semantically, not by verb.
- **"Top-level routes are all auth" — true under the single-segment reading.**
  The only single-segment routes are `/`, `/.well-known/*`, `/authorize`,
  `/callback`, `/jwks`, `/login`, `/logout`, `/me`, `/oidc-callback`, `/token`,
  `/userinfo` — all auth/OIDC/identity/root. Everything else is namespaced
  (~20 resource groups × ~21 ops). So **route depth is a sound include/exclude
  cut**, but tells you nothing about which primitive applies (every namespace mixes
  reads and writes). Caveat: `/me` is an identity *read*, not "auth setup."
- **No `/upload/*` namespace exists.** The brief's "file uploads" non-goal points
  at endpoints that aren't here; upload-like ops are `*_download` / `csv` /
  `export` POSTs *inside* each namespace.

---

## 5. Gaps vs. the intended contract (summary)

| Capability | Built today? |
|---|---|
| Retry-safe mutation dedup (cached response on same key) | ❌ |
| Same-key-different-body ⇒ 409 | ❌ |
| Concurrent same-key serialization | ❌ |
| Mutation key on *all* mutations | ❌ (subset only) |
| Point-in-time read consistency / snapshot | ❌ (only group convergence) |
| Pagination pinned to a snapshot | ❌ (offset-based) |
| Stream snapshot | ❌ |
| Bounded TTL / GC on the dedup store | ❌ (unbounded) |
| Crash-consistency on the accept/reject leg | ❌ |
| Header-based keys | ❌ (envelope, by existing convention) |
| Draft→accept approval workflow | ✅ (this is what exists) |
| Group convergence across concurrent reads | ✅ (this is what exists) |

---

## 6. Recommendations for the design phase

1. **Rename to avoid collision.** Do not reuse `idempotency_key` (= approval
   token) or `snapshot_key` (= group race token) for the new retry-safety
   primitives. Propose distinct names (e.g. `Idempotency-Key`/`request_id` for
   write dedup, `read_consistency_token` for snapshots) and treat the existing
   ledger as a *coexisting* feature, not something to subsume.
2. **Keep the envelope convention.** The codebase and the WebSocket goal both
   point to envelope fields; the "header vs envelope" decision is effectively
   already made.
3. **The new write-dedup gate is genuinely new code.** There is no lookup gate,
   no lock, no fingerprint to extend — so Phase A ("shared middleware + storage
   primitives") is build-from-scratch, not retrofit. `soft_calls_entry` is the
   wrong store to reuse (it's an append-only approval ledger, keyed by call_id, no
   TTL/fingerprint); a new dedup table or Redis layout is warranted.
4. **Snapshot keys need a real source.** Decide LSN vs txid vs `(ts, seq)`; the
   current UUID-race token does not provide point-in-time semantics.
5. **Persona is still the right Phase-B canary** — full uniform CRUD shape, already
   carries the (unused) `snapshot_key` field, and `/persona/watch` is the one GET
   (SSE) to exercise the stream question.

## 7. Open questions to escalate

- **Coexist vs. unify the ledger?** The brief assumes unify; this audit suggests
  coexist (different problems). Confirm intent.
- **Is the draft→accept workflow meant to *be* idempotency, or orthogonal?** If
  product intends "soft write" to double as retry-safety, that's a redesign of the
  approval flow, not an add-on.
- **TTL for long-running AI generations** — moot until a store exists, but the
  brief's worry stands: 24h may be too short for generation acks.
- **Exhaustive coverage table** — sampling shows `snapshot_key` unused outside
  group resolve; confirming all 20 namespaces + listing which mutations carry
  `idempotency_key` today is the next concrete artifact (the per-endpoint table).
