-- Migration: Fix messages_mv to return modality-specific resource IDs
-- instead of generic upload_ids, and rename columns to reflect this.
--
-- Root cause: messages_mv aggregated u.id (uploads_entry.id) for all modalities.
-- The download endpoints expect resource IDs (text_id, image_id, etc.),
-- not upload_ids. upload_ids should never leave the backend.

DROP MATERIALIZED VIEW IF EXISTS messages_mv;

CREATE MATERIALIZED VIEW public.messages_mv AS
 WITH uploads_agg AS (
         SELECT mue.message_id,
            COALESCE(array_agg(DISTINCT tu.text_id) FILTER (WHERE (tu.id IS NOT NULL)), ARRAY[]::uuid[]) AS text_ids,
            COALESCE(array_agg(DISTINCT au.audio_id) FILTER (WHERE (au.id IS NOT NULL)), ARRAY[]::uuid[]) AS audio_ids,
            COALESCE(array_agg(DISTINCT iu.image_id) FILTER (WHERE (iu.id IS NOT NULL)), ARRAY[]::uuid[]) AS image_ids,
            COALESCE(array_agg(DISTINCT vu.video_id) FILTER (WHERE (vu.id IS NOT NULL)), ARRAY[]::uuid[]) AS video_ids,
            COALESCE(array_agg(DISTINCT fu.file_id) FILTER (WHERE (fu.id IS NOT NULL)), ARRAY[]::uuid[]) AS file_ids,
            COALESCE(array_agg(DISTINCT cu.call_id) FILTER (WHERE (cu.id IS NOT NULL)), ARRAY[]::uuid[]) AS call_ids
           FROM (((((((public.message_uploads_entry mue
             JOIN public.uploads_entry u ON (((u.id = mue.upload_id) AND (u.active = true))))
             LEFT JOIN public.text_uploads_entry tu ON (((tu.upload_id = u.id) AND (tu.active = true))))
             LEFT JOIN public.audio_uploads_entry au ON (((au.upload_id = u.id) AND (au.active = true))))
             LEFT JOIN public.image_uploads_entry iu ON (((iu.upload_id = u.id) AND (iu.active = true))))
             LEFT JOIN public.video_uploads_entry vu ON (((vu.upload_id = u.id) AND (vu.active = true))))
             LEFT JOIN public.file_uploads_entry fu ON (((fu.upload_id = u.id) AND (fu.active = true))))
             LEFT JOIN public.call_uploads_entry cu ON (((cu.upload_id = u.id) AND (cu.active = true))))
          WHERE (mue.active = true)
          GROUP BY mue.message_id
        )
 SELECT m.id AS message_id,
    m.run_id,
    (m.role)::text AS role,
    m.created_at AS message_created_at,
    COALESCE(ua.text_ids, ARRAY[]::uuid[]) AS text_ids,
    COALESCE(ua.audio_ids, ARRAY[]::uuid[]) AS audio_ids,
    COALESCE(ua.image_ids, ARRAY[]::uuid[]) AS image_ids,
    COALESCE(ua.video_ids, ARRAY[]::uuid[]) AS video_ids,
    COALESCE(ua.file_ids, ARRAY[]::uuid[]) AS file_ids,
    COALESCE(ua.call_ids, ARRAY[]::uuid[]) AS call_ids
   FROM (public.messages_entry m
     LEFT JOIN uploads_agg ua ON ((ua.message_id = m.id)))
  WHERE ((m.active = true) AND (m.run_id IS NOT NULL))
  WITH NO DATA;

-- Recreate indexes
CREATE UNIQUE INDEX IF NOT EXISTS messages_mv_message_id_idx ON public.messages_mv (message_id);
CREATE INDEX IF NOT EXISTS messages_mv_run_id_idx ON public.messages_mv (run_id);

-- Populate
REFRESH MATERIALIZED VIEW messages_mv;
