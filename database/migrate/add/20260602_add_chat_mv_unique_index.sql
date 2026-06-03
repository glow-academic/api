-- Unique index on chat_mv — required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
--
-- chat_mv is refreshed via REFRESH MATERIALIZED VIEW CONCURRENTLY chat_mv
-- (core/app/tools/entries/chat/refresh.py, wired into the refresh registry at
-- core/app/infra/refresh/config.py). Postgres requires at least one UNIQUE index
-- on a materialized view to refresh it CONCURRENTLY; without one the refresh
-- raises ObjectNotInPrerequisiteStateError (issue #42). Its sibling MVs all have
-- one (attempt_chat_mv → UNIQUE(chat_id), home_chat_mv → UNIQUE(id),
-- practice_chat_mv → UNIQUE(id)); chat_mv was the only one missing it.
--
-- Unique column: chat_entry_id. The MV's final SELECT projects
-- `tbe.id AS chat_entry_id` from public.chat_entry tbe (PRIMARY KEY (id)), and
-- every join is 1:1 — the *_agg CTEs GROUP BY chat_id, scenario_single is
-- DISTINCT ON (chat_id), and home_chat_entry / practice_chat_entry both carry
-- UNIQUE(chat_id) — so each chat_entry.id yields exactly one MV row. Therefore
-- chat_entry_id is guaranteed unique (and never NULL, being a PK projection).
--
-- Plain (non-CONCURRENT) CREATE INDEX: the migrate runner applies each file in a
-- single psql session and CREATE INDEX CONCURRENTLY cannot run in a transaction
-- block; this matches the convention in 20260520_add_operation_key_indexes.sql.

CREATE UNIQUE INDEX IF NOT EXISTS chat_mv_chat_entry_id_idx
    ON public.chat_mv USING btree (chat_entry_id);
