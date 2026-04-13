-- Migration: Add unique indexes to materialized views for CONCURRENTLY refresh
-- Required by PostgreSQL to use REFRESH MATERIALIZED VIEW CONCURRENTLY

CREATE UNIQUE INDEX IF NOT EXISTS test_invocation_mv_invocation_id_idx
ON test_invocation_mv (invocation_id);

CREATE UNIQUE INDEX IF NOT EXISTS attempt_chat_mv_chat_id_idx
ON attempt_chat_mv (chat_id);

CREATE UNIQUE INDEX IF NOT EXISTS attempt_conversations_mv_id_idx
ON attempt_conversations_mv (id);

CREATE UNIQUE INDEX IF NOT EXISTS runs_mv_run_id_idx
ON runs_mv (run_id);

CREATE UNIQUE INDEX IF NOT EXISTS test_grade_mv_id_idx
ON test_grade_mv (id);
