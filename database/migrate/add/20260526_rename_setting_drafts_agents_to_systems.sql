-- Rename setting_drafts_agents_connection → setting_drafts_systems_connection.
--
-- Live settings have no ``agent_ids`` concept — they store ``system_ids``
-- linked through ``setting_systems_junction``. The draft-level connection
-- table was misnamed ``agents`` at inception; later code tried to route
-- ``system_ids`` into the agents slot via an impl-layer alias
-- (``agent_ids=request.system_ids`` in core/app/infra/setting/draft.py),
-- which failed at the FK because the table's FK still targeted
-- ``agents_resource``. Result: 500 on every setting draft save once
-- system_ids were touched (see traceback from POST /setting/draft).
--
-- This migration aligns the draft table with the live-setting shape:
--   * table:  setting_drafts_agents_connection → setting_drafts_systems_connection
--   * column: agents_id → systems_id
--   * FK:     agents_resource(id) → systems_resource(id)
--   * indexes + PK + constraints renamed in lockstep
--
-- Safe to run on a live DB: the source table is empty (verified — no
-- rows ever made it past the FK violation). No data migration needed.
--
-- Absent-safe / idempotent: where the legacy ``...agents_connection`` table
-- (or column / index) never existed — e.g. the academic-demo DB whose state
-- diverges from the migration ledger (see #55) — every step below no-ops
-- instead of raising ``UndefinedTable``/``UndefinedColumn``. The migrate
-- runner applies each file in one transaction with no per-file except, so an
-- unguarded RENAME here aborted the WHOLE add-chain and silently skipped
-- later migrations. Each step is guarded so re-running on either shape (table
-- present OR absent) is safe; the rename still happens wherever the legacy
-- object is present.

BEGIN;

-- 1. Drop the FK that points to the wrong resource (already IF EXISTS).
ALTER TABLE IF EXISTS public.setting_drafts_agents_connection
    DROP CONSTRAINT IF EXISTS setting_drafts_agents_connection_agents_id_fkey;

-- 2. Rename the column — only if the legacy column is actually present.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'setting_drafts_agents_connection'
          AND column_name = 'agents_id'
    ) THEN
        ALTER TABLE public.setting_drafts_agents_connection
            RENAME COLUMN agents_id TO systems_id;
    END IF;
END $$;

-- 3. Rename the table — ALTER TABLE IF EXISTS no-ops when absent.
ALTER TABLE IF EXISTS public.setting_drafts_agents_connection
    RENAME TO setting_drafts_systems_connection;

-- 4. Re-add the FK pointing at the canonical systems resource — only if the
--    renamed table exists and the constraint isn't already there.
DO $$
BEGIN
    IF to_regclass('public.setting_drafts_systems_connection') IS NOT NULL
       AND NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.conname = 'setting_drafts_systems_connection_systems_id_fkey'
          AND t.relname = 'setting_drafts_systems_connection'
          AND n.nspname = 'public'
    ) THEN
        ALTER TABLE public.setting_drafts_systems_connection
            ADD CONSTRAINT setting_drafts_systems_connection_systems_id_fkey
            FOREIGN KEY (systems_id) REFERENCES public.systems_resource(id);
    END IF;
END $$;

-- 5. Rename the PK + indexes so they match the new table name.
--    ALTER INDEX has no IF EXISTS for RENAME, so guard via to_regclass.
DO $$
BEGIN
    IF to_regclass('public.setting_drafts_agents_connection_pkey') IS NOT NULL THEN
        ALTER INDEX public.setting_drafts_agents_connection_pkey
            RENAME TO setting_drafts_systems_connection_pkey;
    END IF;
    IF to_regclass('public.idx_setting_drafts_agents_resource_id') IS NOT NULL THEN
        ALTER INDEX public.idx_setting_drafts_agents_resource_id
            RENAME TO idx_setting_drafts_systems_resource_id;
    END IF;
END $$;

-- 6. The draft_id FK keeps its name pattern (already IF EXISTS for the drop).
ALTER TABLE IF EXISTS public.setting_drafts_systems_connection
    DROP CONSTRAINT IF EXISTS setting_drafts_agents_connection_draft_id_fkey;

DO $$
BEGIN
    IF to_regclass('public.setting_drafts_systems_connection') IS NOT NULL
       AND NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.conname = 'setting_drafts_systems_connection_draft_id_fkey'
          AND t.relname = 'setting_drafts_systems_connection'
          AND n.nspname = 'public'
    ) THEN
        ALTER TABLE public.setting_drafts_systems_connection
            ADD CONSTRAINT setting_drafts_systems_connection_draft_id_fkey
            FOREIGN KEY (draft_id) REFERENCES public.setting_drafts_entry(id) ON DELETE CASCADE;
    END IF;
END $$;

COMMIT;
