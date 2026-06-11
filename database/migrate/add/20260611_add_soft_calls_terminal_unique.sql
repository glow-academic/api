-- Partial-unique index on soft_calls_entry — serializes the soft-call ack
-- transition (A3: concurrent double-ack TOCTOU).
--
-- The soft-call ledger (core/app/tools/entries/soft_calls/create.py) is
-- INSERT-only: each state change (pending → accepted/rejected) appends a new
-- row, and soft_calls_mv keeps the latest per call_id. The three ack sites
-- (infra/attempt/complete.py, infra/attempt/start.py, infra/auth/update.py)
-- used to read the latest row, assert status == 'pending', apply a side effect
-- (activate rows), then INSERT a terminal 'accepted' row — with NO
-- serialization. Two concurrent acks both read 'pending', both applied the
-- side effect, and both appended an 'accepted' row.
--
-- This partial-unique index permits AT MOST ONE terminal (non-pending) ledger
-- row per call_id. The atomic conditional insert in resolve_soft_call
-- (core/app/tools/entries/soft_calls/resolve.py) inserts the terminal row
-- guarded by NOT EXISTS; this index is the hard backstop that closes the
-- check→insert race under true concurrency — the second committer hits a
-- unique violation and is treated as "already resolved" (no double side
-- effect). Pending rows are unconstrained (the propose write + any retries
-- stay legal).
--
-- Plain (non-CONCURRENT) CREATE INDEX: the migrate runner applies each file in
-- a single psql session and CREATE INDEX CONCURRENTLY cannot run in a
-- transaction block; matches the convention in 20260602_add_chat_mv_unique_index.sql.
--
-- PRE-DEDUP (self-healing): this index targets exactly the instances that hit
-- the pre-fix double-ack race — i.e. the ones that ALREADY have duplicate
-- terminal rows per call_id. Without a dedup pass the bare CREATE UNIQUE INDEX
-- raises a unique violation on those rows, the runner rolls the file's whole
-- transaction back (incl. its migrations.applied insert), and it fails
-- identically on every subsequent deploy — the backstop never lands on exactly
-- the instances that need it. So collapse duplicate terminal rows FIRST, then
-- create the index.
--
-- Which row to keep: the one soft_calls_mv would surface. The MV is
--   DISTINCT ON (call_id) ... WHERE active = true ORDER BY call_id, created_at DESC
-- so per call_id keep the latest active terminal row; mirror that ordering
-- exactly (active first, then created_at DESC, id DESC as a deterministic
-- tie-break) and delete the rest. This is idempotent: on a clean instance no
-- terminal call_id has >1 row, so the DELETE removes nothing.

WITH ranked AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY call_id
               ORDER BY active DESC, created_at DESC, id DESC
           ) AS rn
    FROM public.soft_calls_entry
    WHERE status <> 'pending'::text
)
DELETE FROM public.soft_calls_entry s
USING ranked r
WHERE s.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS soft_calls_entry_terminal_call_uidx
    ON public.soft_calls_entry (call_id)
    WHERE (status <> 'pending'::text);
