-- Migration: create setting_providers_junction + setting_drafts_providers_connection.
--
-- Promotes providers from a pure catalog (consumed by the ProviderKeys
-- picker for the provider × key pair UI) into a real multi-select picker
-- on the setting artifact. Mirror of the existing setting_auths_junction
-- shape: composite PK (setting_id, providers_id), FK to providers_resource
-- ON DELETE CASCADE, FK to setting_artifact ON DELETE CASCADE.
--
-- Idempotent via CREATE TABLE IF NOT EXISTS + DO-block guards for the
-- pk + fk constraints.

CREATE TABLE IF NOT EXISTS public.setting_providers_junction (
    setting_id uuid NOT NULL,
    providers_id uuid NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'setting_providers_pkey'
    ) THEN
        ALTER TABLE ONLY public.setting_providers_junction
            ADD CONSTRAINT setting_providers_pkey PRIMARY KEY (setting_id, providers_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'setting_providers_setting_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.setting_providers_junction
            ADD CONSTRAINT setting_providers_setting_id_fkey
            FOREIGN KEY (setting_id) REFERENCES public.setting_artifact(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'setting_providers_providers_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.setting_providers_junction
            ADD CONSTRAINT setting_providers_providers_id_fkey
            FOREIGN KEY (providers_id) REFERENCES public.providers_resource(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS setting_providers_setting_id_idx
    ON public.setting_providers_junction (setting_id);
CREATE INDEX IF NOT EXISTS setting_providers_providers_id_idx
    ON public.setting_providers_junction (providers_id);
CREATE INDEX IF NOT EXISTS setting_providers_active_idx
    ON public.setting_providers_junction (active);

-- Draft staging connection.

CREATE TABLE IF NOT EXISTS public.setting_drafts_providers_connection (
    draft_id uuid NOT NULL,
    providers_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'setting_drafts_providers_connection_pkey'
    ) THEN
        ALTER TABLE ONLY public.setting_drafts_providers_connection
            ADD CONSTRAINT setting_drafts_providers_connection_pkey
            PRIMARY KEY (draft_id, providers_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'setting_drafts_providers_connection_draft_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.setting_drafts_providers_connection
            ADD CONSTRAINT setting_drafts_providers_connection_draft_id_fkey
            FOREIGN KEY (draft_id) REFERENCES public.setting_drafts_entry(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'setting_drafts_providers_connection_providers_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.setting_drafts_providers_connection
            ADD CONSTRAINT setting_drafts_providers_connection_providers_id_fkey
            FOREIGN KEY (providers_id) REFERENCES public.providers_resource(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_setting_drafts_providers_resource_id
    ON public.setting_drafts_providers_connection (providers_id);
