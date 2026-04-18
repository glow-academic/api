-- Migration: Add assistant_persona_ids to attempt_chat_mv
-- Drops and recreates the MV to add the column, then recreates the index.

DROP MATERIALIZED VIEW IF EXISTS attempt_chat_mv CASCADE;

-- Recreate from the updated schema definition
\i database/schema/views/attempt_chat_mv.sql
\i database/schema/indexes/views/attempt_chat_mv.sql

-- Refresh with data
REFRESH MATERIALIZED VIEW attempt_chat_mv;
