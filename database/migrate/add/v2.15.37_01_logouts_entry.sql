-- v2.15.37_01_logouts_entry.sql
--
-- Add an append-only ``logouts_entry`` that mirrors ``logins_entry``
-- one-for-one. Logouts are now a first-class auth event captured in
-- their own row + MV, rather than encoded by flipping
-- ``sessions_entry.active`` (which stays purely a soft-delete flag).
--
-- The session resolver (``_get_or_create_session``) reads
-- ``logouts_mv`` alongside the activity-presence idle check to decide
-- whether to mint a new session. A row here is the canonical
-- "this session is logically ended" signal — distinct from the
-- soft-delete bool on ``sessions_entry``.

CREATE TABLE public.logouts_entry (
    id uuid DEFAULT uuidv7() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL,
    active boolean DEFAULT true NOT NULL,
    session_id uuid NOT NULL,
    CONSTRAINT logouts_entry_pkey PRIMARY KEY (id)
);

CREATE INDEX logouts_entry_session_id_idx
  ON public.logouts_entry (session_id);

CREATE INDEX idx_logouts_entry_generated
  ON public.logouts_entry (generated);

CREATE INDEX idx_logouts_entry_mcp
  ON public.logouts_entry (mcp);

CREATE TABLE public.profiles_logouts_connection (
    profiles_id uuid NOT NULL,
    logout_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL,
    active boolean DEFAULT true NOT NULL,
    CONSTRAINT profiles_logouts_connection_pkey PRIMARY KEY (profiles_id, logout_id)
);

CREATE MATERIALIZED VIEW public.logouts_mv AS
 SELECT l.id AS logout_id,
    plc.profiles_id AS profile_id,
    l.session_id,
    l.created_at,
    l.active,
    l.mcp,
    l.generated
   FROM (public.logouts_entry l
     LEFT JOIN public.profiles_logouts_connection plc
       ON (((plc.logout_id = l.id) AND (plc.active = true))))
  WITH NO DATA;

CREATE UNIQUE INDEX logouts_mv_logout_id_idx
  ON public.logouts_mv USING btree (logout_id);
