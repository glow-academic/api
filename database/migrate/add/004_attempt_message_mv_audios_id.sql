-- Migration: attempt_message_mv exposes audios_id via attempt_audio_entry
--
-- Drop-and-recreate the MV so clients see the resource-level audios_id
-- on each message. We left-join the most recent active attempt_audio_entry
-- row for each message and surface its audios_id. Messages without an
-- audio attachment show audios_id = NULL.

DROP MATERIALIZED VIEW IF EXISTS public.attempt_message_mv CASCADE;

CREATE MATERIALIZED VIEW public.attempt_message_mv AS
 WITH base_messages AS (
         SELECT sm.id AS message_id,
            sm.chat_id,
            ac.attempt_id,
            a.user_persona_id,
            sm.created_at,
            (mc.attempt_message_id IS NOT NULL) AS completed
           FROM ((((public.attempt_message_entry sm
             JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
             JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
             JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
             LEFT JOIN LATERAL ( SELECT attempt_message_completion_entry.attempt_message_id
                   FROM public.attempt_message_completion_entry
                  WHERE ((attempt_message_completion_entry.attempt_message_id = sm.id) AND (attempt_message_completion_entry.active = true))
                  ORDER BY attempt_message_completion_entry.created_at DESC
                 LIMIT 1) mc ON (true))
          WHERE ((sm.active = true) AND (c.active = true) AND (a.active = true))
        ), message_type AS (
         SELECT bm.message_id,
            bm.chat_id,
            bm.attempt_id,
                CASE
                    WHEN (first_content.persona_id = bm.user_persona_id) THEN 'query'::text
                    ELSE 'response'::text
                END AS type,
            bm.created_at,
            bm.completed
           FROM (base_messages bm
             LEFT JOIN LATERAL ( SELECT ace.persona_id
                   FROM public.attempt_content_entry ace
                  WHERE ((ace.message_id = bm.message_id) AND (ace.active = true))
                  ORDER BY ace.created_at
                 LIMIT 1) first_content ON (true))
        )
 SELECT mt.message_id,
    mt.chat_id,
    mt.attempt_id,
    mt.type,
    mt.created_at,
    mt.completed,
    NULL::uuid AS text_id,
    NULL::text AS history_file_path,
    latest_audio.audios_id,
    tree.parent_id AS parent_message_id,
    (row_number() OVER (PARTITION BY COALESCE(tree.parent_id, mt.chat_id) ORDER BY mt.created_at, mt.message_id))::integer AS sibling_index,
    (count(*) OVER (PARTITION BY COALESCE(tree.parent_id, mt.chat_id)))::integer AS sibling_count
   FROM ((message_type mt
     LEFT JOIN public.attempt_message_tree_entry tree ON (((tree.child_id = mt.message_id) AND (tree.active = true))))
     LEFT JOIN LATERAL ( SELECT aae.audios_id
           FROM public.attempt_audio_entry aae
          WHERE ((aae.message_id = mt.message_id) AND (aae.active = true))
          ORDER BY aae.created_at DESC
         LIMIT 1) latest_audio ON (true))
  WITH NO DATA;

CREATE UNIQUE INDEX idx_attempt_message_mv_message_id
    ON public.attempt_message_mv USING btree (message_id);

CREATE INDEX IF NOT EXISTS idx_attempt_message_mv_chat_id
    ON public.attempt_message_mv USING btree (chat_id);
