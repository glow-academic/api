-- v2.15.18_01_test_invocation_traces_rename.sql
--
-- Rename test_invocation_groups_* → test_invocation_traces_* across the
-- schema, mirroring attempt's "trace/conversation" terminology. Drop the
-- now-unused traces-side agents connection (agent identity lives on the
-- parent test_invocation, not on the trace).
--
-- Migrations 01-03 mutate schema; migration 04 recreates the MVs that
-- depended on the old shapes.
--
-- Idempotent: each rename guarded by EXISTS lookups; drop guarded by
-- IF EXISTS.

-- ──────────────────────────────────────────────────────────────────────
-- 0. Drop dependent MVs up-front. Migration 04 recreates them.
--    CASCADE handles the cross-MV dependency tree (test_invocation_mv
--    referenced groups + runs connections via CTE joins).
-- ──────────────────────────────────────────────────────────────────────
DROP MATERIALIZED VIEW IF EXISTS public.test_invocation_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.test_invocation_groups_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.test_invocation_groups_completion_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.test_invocation_runs_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.test_invocation_runs_completion_mv CASCADE;

-- ──────────────────────────────────────────────────────────────────────
-- 1. Rename the entry table.
-- ──────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'test_invocation_groups_entry'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'test_invocation_traces_entry'
    ) THEN
        ALTER TABLE public.test_invocation_groups_entry
          RENAME TO test_invocation_traces_entry;
    END IF;
END $$;

-- ──────────────────────────────────────────────────────────────────────
-- 2. Rename the completion entry + its FK column.
-- ──────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'test_invocation_groups_completion_entry'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'test_invocation_traces_completion_entry'
    ) THEN
        ALTER TABLE public.test_invocation_groups_completion_entry
          RENAME TO test_invocation_traces_completion_entry;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'test_invocation_traces_completion_entry'
          AND column_name = 'test_invocation_groups_id'
    ) THEN
        ALTER TABLE public.test_invocation_traces_completion_entry
          RENAME COLUMN test_invocation_groups_id TO test_invocation_traces_id;
    END IF;
END $$;

-- ──────────────────────────────────────────────────────────────────────
-- 3. Rename the 8 kept connection tables (instructions, prompts, tools,
--    modalities, voices, temperature_levels, reasoning_levels, qualities)
--    and their FK columns.
-- ──────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    conn_name text;
    old_table text;
    new_table text;
BEGIN
    FOREACH conn_name IN ARRAY ARRAY[
        'instructions',
        'prompts',
        'tools',
        'modalities',
        'voices',
        'temperature_levels',
        'reasoning_levels',
        'qualities'
    ] LOOP
        old_table := format('test_invocation_groups_%s_connection', conn_name);
        new_table := format('test_invocation_traces_%s_connection', conn_name);

        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = old_table
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = new_table
        ) THEN
            EXECUTE format('ALTER TABLE public.%I RENAME TO %I', old_table, new_table);
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = new_table
              AND column_name = 'test_invocation_groups_id'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I RENAME COLUMN test_invocation_groups_id TO test_invocation_traces_id',
                new_table
            );
        END IF;
    END LOOP;
END $$;

-- ──────────────────────────────────────────────────────────────────────
-- 4. Drop the trace-side agents connection — agent identity lives on
--    test_invocation_entry (test_invocation_agents_connection), not on
--    the trace. Both manual replay and online eval derive it from there.
-- ──────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS public.test_invocation_groups_agents_connection;
