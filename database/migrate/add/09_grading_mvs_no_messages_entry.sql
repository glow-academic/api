-- Remove messages_entry dependency from grading MVs.
-- Same fix as 04_attempt_mv_no_messages_entry.sql but for strength/improvement/hint/highlight/replacement.

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
  WHERE ((s.active = true) AND (c.active = true) AND (a.active = true))
  WITH NO DATA;
CREATE UNIQUE INDEX ON public.attempt_strength_mv (strength_id);
REFRESH MATERIALIZED VIEW public.attempt_strength_mv;

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
  WHERE ((i.active = true) AND (c.active = true) AND (a.active = true))
  WITH NO DATA;
CREATE UNIQUE INDEX ON public.attempt_improvement_mv (improvement_id);
REFRESH MATERIALIZED VIEW public.attempt_improvement_mv;

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
  WHERE ((h.active = true) AND (c.active = true) AND (a.active = true))
  WITH NO DATA;
CREATE UNIQUE INDEX ON public.attempt_hint_mv (hint_id);
REFRESH MATERIALIZED VIEW public.attempt_hint_mv;

DROP MATERIALIZED VIEW IF EXISTS public.attempt_highlight_mv;
CREATE MATERIALIZED VIEW public.attempt_highlight_mv AS
 SELECT hl.id AS highlight_id,
    hl.strength_id,
    hl.section,
    hl.created_at
   FROM (((((public.attempt_highlight_entry hl
     JOIN public.attempt_strength_entry s ON ((s.id = hl.strength_id)))
     JOIN public.attempt_message_entry sm ON ((sm.id = s.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((hl.active = true) AND (s.active = true) AND (c.active = true) AND (a.active = true))
  WITH NO DATA;
CREATE UNIQUE INDEX ON public.attempt_highlight_mv (highlight_id);
REFRESH MATERIALIZED VIEW public.attempt_highlight_mv;

DROP MATERIALIZED VIEW IF EXISTS public.attempt_replacement_mv;
CREATE MATERIALIZED VIEW public.attempt_replacement_mv AS
 SELECT rp.id AS replacement_id,
    rp.improvement_id,
    rp.section,
    rp.replace,
    rp.created_at
   FROM (((((public.attempt_replacement_entry rp
     JOIN public.attempt_improvement_entry i ON ((i.id = rp.improvement_id)))
     JOIN public.attempt_message_entry sm ON ((sm.id = i.message_id)))
     JOIN public.attempt_chat_entry c ON ((c.id = sm.chat_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
  WHERE ((rp.active = true) AND (i.active = true) AND (c.active = true) AND (a.active = true))
  WITH NO DATA;
CREATE UNIQUE INDEX ON public.attempt_replacement_mv (replacement_id);
REFRESH MATERIALIZED VIEW public.attempt_replacement_mv;
