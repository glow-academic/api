-- Migration: project `idx` onto attempt_highlight_mv + attempt_replacement_mv.
--
-- Both base tables (attempt_highlight_entry, attempt_replacement_entry)
-- already carry an `idx` integer that records the insertion position
-- of the child within its strength / improvement. The MVs never
-- projected it, so search tools couldn't order by it and a consumer
-- reading the column from the MV 500'd with "column idx does not
-- exist". (That was patched temporarily by dropping idx from the
-- highlight SELECT — this migration is the canonical fix.)
--
-- attempt_hint_entry does NOT carry an idx column today; that would
-- require a separate migration with a default+backfill. Out of scope.
--
-- Drop-and-recreate style matches 004/005/006. Indexes preserved
-- with their original names for compatibility with existing catalog
-- references.

DROP MATERIALIZED VIEW IF EXISTS public.attempt_highlight_mv CASCADE;

CREATE MATERIALIZED VIEW public.attempt_highlight_mv AS
 SELECT hl.id AS highlight_id,
    hl.strength_id,
    hl.section,
    hl.idx,
    hl.created_at
   FROM public.attempt_highlight_entry hl
     JOIN public.attempt_strength_entry s ON s.id = hl.strength_id
     JOIN public.attempt_message_entry sm ON sm.id = s.message_id
     JOIN public.attempt_chat_entry c ON c.id = sm.chat_id
     JOIN public.attempt_chat_bridge_entry ac ON ac.attempt_chat_id = c.id
     JOIN public.attempt_entry a ON a.id = ac.attempt_id
  WHERE hl.active = true AND s.active = true AND c.active = true AND a.active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS attempt_highlight_mv_highlight_id_idx
    ON public.attempt_highlight_mv USING btree (highlight_id);

DROP MATERIALIZED VIEW IF EXISTS public.attempt_replacement_mv CASCADE;

CREATE MATERIALIZED VIEW public.attempt_replacement_mv AS
 SELECT rp.id AS replacement_id,
    rp.improvement_id,
    rp.section,
    rp.replace,
    rp.idx,
    rp.created_at
   FROM public.attempt_replacement_entry rp
     JOIN public.attempt_improvement_entry i ON i.id = rp.improvement_id
     JOIN public.attempt_message_entry sm ON sm.id = i.message_id
     JOIN public.attempt_chat_entry c ON c.id = sm.chat_id
     JOIN public.attempt_chat_bridge_entry ac ON ac.attempt_chat_id = c.id
     JOIN public.attempt_entry a ON a.id = ac.attempt_id
  WHERE rp.active = true AND i.active = true AND c.active = true AND a.active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS attempt_replacement_mv_replacement_id_idx
    ON public.attempt_replacement_mv USING btree (replacement_id);
