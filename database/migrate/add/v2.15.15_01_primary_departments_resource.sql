-- Migration: add primary_departments_resource + profile junction/connection.
--
-- Replaces the old approach of deriving a profile's primary department from
-- departments_resource.is_primary (a global per-department flag that couldn't
-- model "per-profile primary"). The new model:
--
--   primary_departments_resource       — thin catalog of (id, departments_id)
--     pointers; same shape as profile_personas_resource, one catalog entry
--     per department that may be designated as a primary.
--
--   profile_primary_departments_junction        — committed binding
--     PK is (profile_id) alone, so at most one primary per profile is
--     enforced by the schema (same pattern as profile_names_junction).
--
--   profile_drafts_primary_departments_connection — draft staging
--     PK (draft_id, primary_departments_id), mirrors profile_drafts_*
--     connections.
--
-- Idempotent: each CREATE TABLE / ALTER uses IF NOT EXISTS; FKs are added
-- via DO blocks that check information_schema first, so fresh DBs (which
-- seed from schema.sql) and legacy DBs both converge.

CREATE TABLE IF NOT EXISTS public.primary_departments_resource (
    id uuid DEFAULT uuidv7() NOT NULL,
    departments_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'primary_departments_resource_pkey'
    ) THEN
        ALTER TABLE ONLY public.primary_departments_resource
            ADD CONSTRAINT primary_departments_resource_pkey PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'primary_departments_resource_departments_id_unique'
    ) THEN
        ALTER TABLE ONLY public.primary_departments_resource
            ADD CONSTRAINT primary_departments_resource_departments_id_unique UNIQUE (departments_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'primary_departments_resource_departments_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.primary_departments_resource
            ADD CONSTRAINT primary_departments_resource_departments_id_fkey
            FOREIGN KEY (departments_id) REFERENCES public.departments_resource(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_primary_departments_resource_departments_id
    ON public.primary_departments_resource (departments_id);

-- Committed junction: profile ↔ primary_departments (one per profile).

CREATE TABLE IF NOT EXISTS public.profile_primary_departments_junction (
    profile_id uuid NOT NULL,
    primary_departments_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'profile_primary_departments_pkey'
    ) THEN
        ALTER TABLE ONLY public.profile_primary_departments_junction
            ADD CONSTRAINT profile_primary_departments_pkey PRIMARY KEY (profile_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'profile_primary_departments_profile_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.profile_primary_departments_junction
            ADD CONSTRAINT profile_primary_departments_profile_id_fkey
            FOREIGN KEY (profile_id) REFERENCES public.profile_artifact(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'profile_primary_departments_primary_departments_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.profile_primary_departments_junction
            ADD CONSTRAINT profile_primary_departments_primary_departments_id_fkey
            FOREIGN KEY (primary_departments_id) REFERENCES public.primary_departments_resource(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_profile_primary_departments_primary_departments_id
    ON public.profile_primary_departments_junction (primary_departments_id);

-- Draft staging connection.

CREATE TABLE IF NOT EXISTS public.profile_drafts_primary_departments_connection (
    draft_id uuid NOT NULL,
    primary_departments_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'profile_drafts_primary_departments_connection_pkey'
    ) THEN
        ALTER TABLE ONLY public.profile_drafts_primary_departments_connection
            ADD CONSTRAINT profile_drafts_primary_departments_connection_pkey
            PRIMARY KEY (draft_id, primary_departments_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'profile_drafts_primary_departments_connection_draft_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.profile_drafts_primary_departments_connection
            ADD CONSTRAINT profile_drafts_primary_departments_connection_draft_id_fkey
            FOREIGN KEY (draft_id) REFERENCES public.profile_drafts_entry(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'profile_drafts_primary_departments_connection_resource_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.profile_drafts_primary_departments_connection
            ADD CONSTRAINT profile_drafts_primary_departments_connection_resource_id_fkey
            FOREIGN KEY (primary_departments_id) REFERENCES public.primary_departments_resource(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_profile_drafts_primary_departments_resource_id
    ON public.profile_drafts_primary_departments_connection (primary_departments_id);
