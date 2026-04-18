-- Migration: Recreate attempt_message_mv and attempt_content_mv
-- Removes dependency on messages_entry — derives role from persona comparison

DROP MATERIALIZED VIEW IF EXISTS attempt_content_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS attempt_message_mv CASCADE;

\i database/schema/views/attempt_message_mv.sql
\i database/schema/indexes/views/attempt_message_mv.sql
\i database/schema/views/attempt_content_mv.sql
\i database/schema/indexes/views/attempt_content_mv.sql

REFRESH MATERIALIZED VIEW attempt_message_mv;
REFRESH MATERIALIZED VIEW attempt_content_mv;
