-- Migration: Drop call_id from attempt entry tables
-- Self-contained: drops columns with CASCADE, recreates affected MVs + indexes inline

-- ============================================================================
-- Phase 1: Drop call_id columns (CASCADE drops dependent MVs automatically)
-- ============================================================================

ALTER TABLE attempt_analysis_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_archive_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_chat_completion_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_chat_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_completion_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_content_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_conversation_completion_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_conversations_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_feedback_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_grade_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_highlight_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_hint_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_improvement_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_message_completion_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_message_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_mutes_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_replacement_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_responses_entry DROP COLUMN IF EXISTS call_id CASCADE;
ALTER TABLE attempt_strength_entry DROP COLUMN IF EXISTS call_id CASCADE;

-- ============================================================================
-- Phase 2: Recreate simple MVs (call_id removed, session_id added) + indexes
-- ============================================================================

-- attempt_archive_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_archive_mv AS
 SELECT id, created_at, generated, mcp, active, attempt_id, archived, session_id
   FROM public.attempt_archive_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_archive_mv_id ON public.attempt_archive_mv USING btree (id);

-- attempt_chat_completion_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_chat_completion_mv AS
 SELECT id, chat_id, stop, error, message, session_id, created_at, active, generated, mcp
   FROM public.attempt_chat_completion_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_chat_completion_mv_id ON public.attempt_chat_completion_mv USING btree (id);

-- attempt_completion_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_completion_mv AS
 SELECT id, attempt_id, stop, error, message, session_id, created_at, active, generated, mcp
   FROM public.attempt_completion_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_completion_mv_id ON public.attempt_completion_mv USING btree (id);

-- attempt_conversation_completion_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_conversation_completion_mv AS
 SELECT id, conversation_id, stop, error, message, session_id, created_at, active, generated, mcp
   FROM public.attempt_conversation_completion_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_conversation_completion_mv_id ON public.attempt_conversation_completion_mv USING btree (id);

-- attempt_conversations_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_conversations_mv AS
 SELECT id, created_at, generated, mcp, active, chat_id, session_id
   FROM public.attempt_conversations_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS attempt_conversations_mv_id_idx ON public.attempt_conversations_mv USING btree (id);

-- attempt_message_completion_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_message_completion_mv AS
 SELECT id, attempt_message_id, stop, error, message, session_id, created_at, active, generated, mcp
   FROM public.attempt_message_completion_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_message_completion_mv_id ON public.attempt_message_completion_mv USING btree (id);

-- attempt_mutes_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS public.attempt_mutes_mv AS
 SELECT id, created_at, generated, mcp, active, conversation_id, muted, session_id
   FROM public.attempt_mutes_entry WHERE (active = true) WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS attempt_mutes_mv_conversation_id_idx ON public.attempt_mutes_mv USING btree (conversation_id);
CREATE UNIQUE INDEX IF NOT EXISTS attempt_mutes_mv_id_idx ON public.attempt_mutes_mv USING btree (id);

-- ============================================================================
-- Phase 3: Recreate complex MVs from updated schema files
-- ============================================================================

-- attempt_chat_mv (removed group_id + calls_entry/runs_entry joins)
DROP MATERIALIZED VIEW IF EXISTS attempt_chat_mv CASCADE;
\i database/schema/views/attempt_chat_mv.sql
\i database/schema/indexes/views/attempt_chat_mv.sql

-- attempt_message_mv + attempt_content_mv
DROP MATERIALIZED VIEW IF EXISTS attempt_content_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS attempt_message_mv CASCADE;
\i database/schema/views/attempt_message_mv.sql
\i database/schema/indexes/views/attempt_message_mv.sql
\i database/schema/views/attempt_content_mv.sql
\i database/schema/indexes/views/attempt_content_mv.sql

-- ============================================================================
-- Phase 4: Refresh all recreated MVs
-- ============================================================================

REFRESH MATERIALIZED VIEW attempt_archive_mv;
REFRESH MATERIALIZED VIEW attempt_chat_completion_mv;
REFRESH MATERIALIZED VIEW attempt_completion_mv;
REFRESH MATERIALIZED VIEW attempt_conversation_completion_mv;
REFRESH MATERIALIZED VIEW attempt_conversations_mv;
REFRESH MATERIALIZED VIEW attempt_message_completion_mv;
REFRESH MATERIALIZED VIEW attempt_mutes_mv;
REFRESH MATERIALIZED VIEW attempt_chat_mv;
REFRESH MATERIALIZED VIEW attempt_message_mv;
REFRESH MATERIALIZED VIEW attempt_content_mv;
