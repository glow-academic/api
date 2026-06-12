-- analysis-family MV own-row liveness filters (soft-delete leak fix, L1).
--
-- The C6-A fix (calls_mv) + the D1 fix (attempt_analysis_mv) added the missing
-- `active = true` liveness predicates, but the five analysis-family MVs that
-- JOIN attempt_message_entry (alias `sm`) and attempt_chat_bridge_entry
-- (alias `ac`) still filtered only their own row + the chat (`c`) + the
-- attempt (`a`) — never `sm.active` / `ac.active`. Both joined tables carry an
-- `active boolean NOT NULL DEFAULT true` column, so soft-deleted / dormant
-- message + chat-bridge rows leaked their dependent strengths / hints /
-- improvements / highlights / replacements into these hot reads.
--
-- This mirrors the calls_mv (C6-A) + attempt_analysis_mv (D1) fixes and the
-- sibling MVs that already filter `sm.active` / `ac.active` (e.g. the
-- attempt_message_mv-family). Affected MVs:
--   attempt_strength_mv, attempt_hint_mv, attempt_improvement_mv,
--   attempt_highlight_mv, attempt_replacement_mv.
--
-- Readers affected: core/app/tools/entries/attempt_{strength,hint,improvement,
-- highlight,replacement}/{search,get}.py all query these MVs (search.py also
-- bypass-inlines the MV definition via resolve_mv_source), so the filter must
-- live in the MV body to cover the bypass path too.
--
-- Postgres has no CREATE OR REPLACE for materialized views, so drop + recreate.
-- Each MV's unique index (required for REFRESH ... CONCURRENTLY) is dropped by
-- the cascade and recreated inline. The added filters only remove rows (never
-- duplicate), so each id projection stays unique and non-null.
--
-- Safe on a live DB: read-only redefinitions, the only blip is a cache miss
-- until the inline REFRESHes below repopulate them. No MV depends on another
-- MV here (highlight/replacement join the strength/improvement *_entry tables,
-- not the MVs), so the per-MV drop+recreate order is independent.

BEGIN;

-- attempt_strength_mv ------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS public.attempt_strength_mv;

CREATE MATERIALIZED VIEW public.attempt_strength_mv AS
 SELECT s.id AS strength_id,
    s.message_id,
    s.grade_id,
    s.name,
    s.description,
    s.created_at
   FROM ((((public.attempt_strength_entry s
     JOIN public.attempt_message_entry sm ON ((sm.id = s.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((s.active = true) AND (sm.active = true) AND (c.active = true) AND (ac.active = true) AND (a.active = true))
  WITH NO DATA;

CREATE UNIQUE INDEX attempt_strength_mv_strength_id_idx ON public.attempt_strength_mv USING btree (strength_id);

REFRESH MATERIALIZED VIEW public.attempt_strength_mv;

-- attempt_hint_mv ----------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS public.attempt_hint_mv;

CREATE MATERIALIZED VIEW public.attempt_hint_mv AS
 SELECT h.id AS hint_id,
    h.message_id,
    h.hint,
    h.created_at
   FROM ((((public.attempt_hint_entry h
     JOIN public.attempt_message_entry sm ON ((sm.id = h.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((h.active = true) AND (sm.active = true) AND (c.active = true) AND (ac.active = true) AND (a.active = true))
  WITH NO DATA;

CREATE UNIQUE INDEX attempt_hint_mv_hint_id_idx ON public.attempt_hint_mv USING btree (hint_id);

REFRESH MATERIALIZED VIEW public.attempt_hint_mv;

-- attempt_improvement_mv ---------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS public.attempt_improvement_mv;

CREATE MATERIALIZED VIEW public.attempt_improvement_mv AS
 SELECT i.id AS improvement_id,
    i.message_id,
    i.name,
    i.description,
    i.created_at
   FROM ((((public.attempt_improvement_entry i
     JOIN public.attempt_message_entry sm ON ((sm.id = i.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((i.active = true) AND (sm.active = true) AND (c.active = true) AND (ac.active = true) AND (a.active = true))
  WITH NO DATA;

CREATE UNIQUE INDEX attempt_improvement_mv_improvement_id_idx ON public.attempt_improvement_mv USING btree (improvement_id);

REFRESH MATERIALIZED VIEW public.attempt_improvement_mv;

-- attempt_highlight_mv -----------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS public.attempt_highlight_mv;

CREATE MATERIALIZED VIEW public.attempt_highlight_mv AS
 SELECT hl.id AS highlight_id,
    hl.strength_id,
    hl.section,
    hl.idx,
    hl.created_at
   FROM (((((public.attempt_highlight_entry hl
     JOIN public.attempt_strength_entry s ON ((s.id = hl.strength_id)))
     JOIN public.attempt_message_entry sm ON ((sm.id = s.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((hl.active = true) AND (s.active = true) AND (sm.active = true) AND (c.active = true) AND (ac.active = true) AND (a.active = true))
  WITH NO DATA;

CREATE UNIQUE INDEX attempt_highlight_mv_highlight_id_idx ON public.attempt_highlight_mv USING btree (highlight_id);

REFRESH MATERIALIZED VIEW public.attempt_highlight_mv;

-- attempt_replacement_mv ---------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS public.attempt_replacement_mv;

CREATE MATERIALIZED VIEW public.attempt_replacement_mv AS
 SELECT rp.id AS replacement_id,
    rp.improvement_id,
    rp.section,
    rp.replace,
    rp.idx,
    rp.created_at
   FROM (((((public.attempt_replacement_entry rp
     JOIN public.attempt_improvement_entry i ON ((i.id = rp.improvement_id)))
     JOIN public.attempt_message_entry sm ON ((sm.id = i.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((rp.active = true) AND (i.active = true) AND (sm.active = true) AND (c.active = true) AND (ac.active = true) AND (a.active = true))
  WITH NO DATA;

CREATE UNIQUE INDEX attempt_replacement_mv_replacement_id_idx ON public.attempt_replacement_mv USING btree (replacement_id);

REFRESH MATERIALIZED VIEW public.attempt_replacement_mv;

COMMIT;
