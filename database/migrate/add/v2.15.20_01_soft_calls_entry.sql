-- v2.15.20_01_soft_calls_entry.sql
--
-- Canonical ack/lifecycle ledger for soft tool-call writes.
--
-- Each soft create / update / delete / duplicate driven by an LLM tool
-- call records one or more rows here, keyed by ``call_id`` (the
-- ``calls_entry.id`` of the originating tool invocation). Rows are
-- INSERT-only; the latest row per ``call_id`` is the current truth and
-- materialized via ``soft_calls_mv``.
--
-- Vocabulary mirrors ``permissions_resource``: ``(artifact, operation)``
-- — e.g. ``('persona','create')``, ``('scenario','update')``.
--
-- Why this exists:
--   - Replaces the silently-broken assumption that
--     ``idempotency_key == artifact_id`` baked into every artifact's
--     ack short-circuit. The new contract is
--     ``idempotency_key == call_id``; the impl looks up the entry to
--     resolve ``artifact_id`` and ``operation``.
--   - Distinguishes "pending create" (active=false + ledger row
--     operation='create') from "pending delete" (active=false + ledger
--     row operation='delete') without overloading ``active``.
--   - Single black-box table — replaces 63 legacy
--     ``<resource>_calls_connection`` tables whose drop is queued for a
--     follow-up PR once this pattern is verified end-to-end.
--
-- Whole migration runs inside one transaction so a partial failure
-- never leaves the schema half-recreated. The MV is created WITH NO
-- DATA — runtime refresh fills it.

BEGIN;

-- ── Entry table ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.soft_calls_entry (
    created_at  timestamp with time zone DEFAULT now() NOT NULL,
    id          uuid DEFAULT uuidv7() NOT NULL,
    generated   boolean DEFAULT false NOT NULL,
    mcp         boolean DEFAULT false NOT NULL,
    active      boolean DEFAULT true NOT NULL,
    call_id     uuid NOT NULL,
    artifact    text NOT NULL,
    operation   text NOT NULL,
    status      text NOT NULL,
    artifact_id uuid NOT NULL,
    patch       jsonb
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'soft_calls_entry_pkey'
    ) THEN
        ALTER TABLE ONLY public.soft_calls_entry
            ADD CONSTRAINT soft_calls_entry_pkey PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'soft_calls_entry_call_fkey'
    ) THEN
        ALTER TABLE ONLY public.soft_calls_entry
            ADD CONSTRAINT soft_calls_entry_call_fkey
            FOREIGN KEY (call_id) REFERENCES public.calls_entry(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'soft_calls_entry_status_check'
    ) THEN
        ALTER TABLE ONLY public.soft_calls_entry
            ADD CONSTRAINT soft_calls_entry_status_check
            CHECK (status IN ('pending', 'accepted', 'rejected'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_soft_calls_entry_call_lookup
    ON public.soft_calls_entry (call_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_soft_calls_entry_target_lookup
    ON public.soft_calls_entry (artifact, artifact_id, status);

-- ── Latest-status materialized view ──────────────────────────────
-- One row per call_id — the most recent ledger row wins. Use this for
-- ack lookups and search-time filtering. The base table remains the
-- full append-only history if forensic queries ever need it.

CREATE MATERIALIZED VIEW IF NOT EXISTS public.soft_calls_mv AS
SELECT DISTINCT ON (s.call_id)
    s.id AS soft_call_entry_id,
    s.call_id,
    s.artifact,
    s.operation,
    s.status,
    s.artifact_id,
    s.patch,
    s.created_at
FROM public.soft_calls_entry s
WHERE s.active = true
ORDER BY s.call_id, s.created_at DESC
WITH NO DATA;

-- Unique index on call_id is required for REFRESH MATERIALIZED VIEW
-- CONCURRENTLY. Secondary index supports search-by-target lookups.
CREATE UNIQUE INDEX IF NOT EXISTS idx_soft_calls_mv_call
    ON public.soft_calls_mv (call_id);

CREATE INDEX IF NOT EXISTS idx_soft_calls_mv_target
    ON public.soft_calls_mv (artifact, artifact_id, status);

COMMIT;
