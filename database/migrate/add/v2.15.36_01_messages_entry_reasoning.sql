-- v2.15.36_01_messages_entry_reasoning.sql
--
-- Add a ``reasoning`` boolean flag to ``messages_entry`` (mirrors the
-- existing typing flags ``mcp`` and ``generated``). A row with
-- ``reasoning = true`` represents a chain-of-thought trace emitted by
-- a reasoning-capable model (Gemma 4, GPT-5 with reasoning_effort,
-- DeepSeek-V3, etc.) — kept as its own row so the UI can collapse the
-- thought block independently of the final answer, and so MV-level
-- filters can exclude reasoning from list/summary views cheaply.
--
-- Backwards-compatible: default false means every existing row is
-- treated as a normal (non-reasoning) message until callers opt in.
--
-- Recreates ``messages_mv`` to project the new column so downstream
-- queries can filter on it without a join back to the base table. The
-- two existing indexes on the MV (``message_id_idx``, ``run_id_idx``)
-- are dropped by CASCADE and re-created here. Adds a partial index on
-- the base table for the common "non-reasoning messages for a run"
-- query path used by the chat-history fetch.

ALTER TABLE public.messages_entry
  ADD COLUMN reasoning BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX idx_messages_entry_run_id_no_reasoning
  ON public.messages_entry (run_id, created_at)
  WHERE active = true AND reasoning = false;

DROP MATERIALIZED VIEW IF EXISTS public.messages_mv CASCADE;

CREATE MATERIALIZED VIEW public.messages_mv AS
 WITH uploads_agg AS (
        SELECT mue.message_id,
               COALESCE(array_agg(DISTINCT tu.text_id)  FILTER (WHERE tu.id IS NOT NULL), ARRAY[]::uuid[]) AS text_ids,
               COALESCE(array_agg(DISTINCT au.audio_id) FILTER (WHERE au.id IS NOT NULL), ARRAY[]::uuid[]) AS audio_ids,
               COALESCE(array_agg(DISTINCT iu.image_id) FILTER (WHERE iu.id IS NOT NULL), ARRAY[]::uuid[]) AS image_ids,
               COALESCE(array_agg(DISTINCT vu.video_id) FILTER (WHERE vu.id IS NOT NULL), ARRAY[]::uuid[]) AS video_ids,
               COALESCE(array_agg(DISTINCT fu.file_id)  FILTER (WHERE fu.id IS NOT NULL), ARRAY[]::uuid[]) AS file_ids,
               COALESCE(array_agg(DISTINCT cu.call_id)  FILTER (WHERE cu.id IS NOT NULL), ARRAY[]::uuid[]) AS call_ids
          FROM message_uploads_entry mue
          JOIN uploads_entry u            ON u.id = mue.upload_id AND u.active = true
          LEFT JOIN text_uploads_entry  tu ON tu.upload_id = u.id AND tu.active = true
          LEFT JOIN audio_uploads_entry au ON au.upload_id = u.id AND au.active = true
          LEFT JOIN image_uploads_entry iu ON iu.upload_id = u.id AND iu.active = true
          LEFT JOIN video_uploads_entry vu ON vu.upload_id = u.id AND vu.active = true
          LEFT JOIN file_uploads_entry  fu ON fu.upload_id = u.id AND fu.active = true
          LEFT JOIN call_uploads_entry  cu ON cu.upload_id = u.id AND cu.active = true
         WHERE mue.active = true
         GROUP BY mue.message_id
      )
 SELECT m.id AS message_id,
        m.run_id,
        m.role,
        m.reasoning,
        m.created_at AS message_created_at,
        COALESCE(ua.text_ids,  ARRAY[]::uuid[]) AS text_ids,
        COALESCE(ua.audio_ids, ARRAY[]::uuid[]) AS audio_ids,
        COALESCE(ua.image_ids, ARRAY[]::uuid[]) AS image_ids,
        COALESCE(ua.video_ids, ARRAY[]::uuid[]) AS video_ids,
        COALESCE(ua.file_ids,  ARRAY[]::uuid[]) AS file_ids,
        COALESCE(ua.call_ids,  ARRAY[]::uuid[]) AS call_ids
   FROM messages_entry m
   LEFT JOIN uploads_agg ua ON ua.message_id = m.id
  WHERE m.active = true AND m.run_id IS NOT NULL;

CREATE UNIQUE INDEX messages_mv_message_id_idx
  ON public.messages_mv (message_id);

CREATE INDEX messages_mv_run_id_idx
  ON public.messages_mv (run_id);
