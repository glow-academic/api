-- Migration: Add unique index to test_invocation_mv for CONCURRENTLY refresh
-- Required by PostgreSQL to use REFRESH MATERIALIZED VIEW CONCURRENTLY

CREATE UNIQUE INDEX IF NOT EXISTS test_invocation_mv_invocation_id_idx
ON test_invocation_mv (invocation_id);
