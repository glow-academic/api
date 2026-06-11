-- Partial-unique index on grant_consumptions_entry — serializes the single-use
-- emulation-grant consume (I1: concurrent double-consume TOCTOU / impersonation
-- replay).
--
-- The grant-consume path (core/app/infra/identity/default_idp.py) used to
-- SELECT for an existing consumption, assert none, then INSERT a new
-- consumption row — with NO serialization and NO unique constraint (grant_id
-- had only a non-unique btree index). Two concurrent OIDC logins carrying the
-- same single-use emulation grant (via login_hint) both saw no consumption,
-- both passed the gate, both inserted, and both minted an emulation session —
-- a single-use impersonation grant replayed twice.
--
-- This partial-unique index permits AT MOST ONE *active* consumption per
-- grant_id. create_grant_consumption now inserts guarded by
-- ON CONFLICT (grant_id) WHERE active = true DO NOTHING RETURNING; the caller
-- treats a no-row result as "already consumed → 403". This index is the hard
-- backstop that closes the check→insert race under true concurrency — the
-- second committer writes 0 rows and is rejected (no double emulation session).
-- Soft (inactive) consumptions are exempt from the predicate, so the soft path
-- and any historical inactive rows stay legal.
--
-- Plain (non-CONCURRENT) CREATE INDEX: the migrate runner applies each file in
-- a single transaction and CREATE INDEX CONCURRENTLY cannot run in a
-- transaction block; matches 20260611_add_soft_calls_terminal_unique.sql.
--
-- PRE-DEDUP (self-healing): instances that already hit the double-consume race
-- have >1 active consumption per grant_id; the bare CREATE UNIQUE INDEX would
-- raise a unique violation on those rows, roll the whole file back (incl. its
-- migrations.applied insert), and fail identically on every subsequent deploy.
-- So collapse duplicate active consumptions FIRST. Which row to keep: the one
-- grant_consumptions_mv surfaces — it filters active = true; keep the latest
-- active row per grant_id (created_at DESC, id DESC tie-break) and delete the
-- rest. Idempotent: on a clean instance no grant_id has >1 active row, so the
-- DELETE removes nothing.

WITH ranked AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY grant_id
               ORDER BY created_at DESC, id DESC
           ) AS rn
    FROM public.grant_consumptions_entry
    WHERE active = true
)
DELETE FROM public.grant_consumptions_entry g
USING ranked r
WHERE g.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS grant_consumptions_entry_grant_uidx
    ON public.grant_consumptions_entry (grant_id)
    WHERE (active = true);
