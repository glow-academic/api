-- Hot-path MV foreign-key indexes (report-15 P1/P2/P3) — the box-hang-under-load fix.
--
-- The three hottest materialized-view reads each filter on a FOREIGN-KEY column
-- that has NO index — only the MV's PRIMARY-KEY column is indexed. So every
-- per-request / per-page read does a FULL MV SEQ SCAN + sort that degrades as
-- the underlying data grows. This is the documented "box hangs under load"
-- profile (latency grows with total row count across all users).
--
--   P1 sessions_mv.profile_id  — search_sessions(profile_ids=[…]) runs on EVERY
--      authenticated request (require_auth → resolve_identity →
--      get_or_create_session). sessions_mv had only UNIQUE(session_id).
--   P2 runs_mv.group_id        — search_runs(group_ids=[…]) on every
--      conversation/generation-history load. runs_mv had only UNIQUE(run_id).
--   P3 attempt_mv.profile_id   — search_attempts(profile_ids=[…]) on every
--      home/practice/dashboard/record/leaderboard page. attempt_mv had only
--      UNIQUE(attempt_id) + (role_id).
--
-- Composite (fk, created_at) so the index also serves the ORDER BY …_created_at
-- the same queries apply, making them a seek instead of a scan+sort.
--
-- Idempotent (IF NOT EXISTS) and recorded in migrations.applied, so re-runs are
-- no-ops. NOT CONCURRENTLY: the migration runner wraps each file in a
-- transaction (scripts/migrate.py), and CREATE INDEX CONCURRENTLY cannot run in
-- one. A plain CREATE INDEX on an MV briefly blocks only a concurrent REFRESH,
-- which is acceptable during the deploy window. These additions are pure read
-- accelerators — no behavior/row change. Mirrors the fresh-DB definitions added
-- to schema/indexes/views/{sessions_mv,runs_mv,attempt_mv}.sql for parity.

-- P1: sessions_mv — served on every authenticated request.
CREATE INDEX IF NOT EXISTS idx_sessions_mv_profile_created
    ON public.sessions_mv USING btree (profile_id, session_created_at DESC);

-- P2: runs_mv — served on every conversation/history load.
CREATE INDEX IF NOT EXISTS idx_runs_mv_group_id
    ON public.runs_mv USING btree (group_id, run_created_at);

-- P3: attempt_mv — served on every home/practice/dashboard load.
CREATE INDEX IF NOT EXISTS idx_attempt_mv_profile_created
    ON public.attempt_mv USING btree (profile_id, attempt_created_at DESC);

-- P4: case-insensitive email lookup on the auth path (resolve_identity
-- _resolve_profile_id). The old substring `LIKE '%'||$1||'%'` could never use
-- an index; the new `LOWER(email) = LOWER($1)` equality is served by this
-- functional index (a plain btree on `email` can't serve LOWER(email)).
CREATE INDEX IF NOT EXISTS idx_emails_resource_lower_email
    ON public.emails_resource USING btree (LOWER(email));
