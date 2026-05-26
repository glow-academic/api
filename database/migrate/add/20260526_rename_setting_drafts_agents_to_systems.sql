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

BEGIN;

-- 1. Drop the FK that points to the wrong resource.
ALTER TABLE public.setting_drafts_agents_connection
    DROP CONSTRAINT IF EXISTS setting_drafts_agents_connection_agents_id_fkey;

-- 2. Rename the column.
ALTER TABLE public.setting_drafts_agents_connection
    RENAME COLUMN agents_id TO systems_id;

-- 3. Rename the table.
ALTER TABLE public.setting_drafts_agents_connection
    RENAME TO setting_drafts_systems_connection;

-- 4. Re-add the FK pointing at the canonical systems resource.
ALTER TABLE public.setting_drafts_systems_connection
    ADD CONSTRAINT setting_drafts_systems_connection_systems_id_fkey
    FOREIGN KEY (systems_id) REFERENCES public.systems_resource(id);

-- 5. Rename the PK + indexes so they match the new table name.
ALTER INDEX public.setting_drafts_agents_connection_pkey
    RENAME TO setting_drafts_systems_connection_pkey;

ALTER INDEX public.idx_setting_drafts_agents_resource_id
    RENAME TO idx_setting_drafts_systems_resource_id;

-- 6. The draft_id FK keeps its name pattern.
ALTER TABLE public.setting_drafts_systems_connection
    DROP CONSTRAINT IF EXISTS setting_drafts_agents_connection_draft_id_fkey;

ALTER TABLE public.setting_drafts_systems_connection
    ADD CONSTRAINT setting_drafts_systems_connection_draft_id_fkey
    FOREIGN KEY (draft_id) REFERENCES public.setting_drafts_entry(id) ON DELETE CASCADE;

COMMIT;
