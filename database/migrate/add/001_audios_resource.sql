-- Migration: add audios_resource
--
-- Canonical library parity with images_resource / videos_resource /
-- files_resource / texts_resource. Named reusable audio assets.
--
-- Entry-level rows live in audios_entry; they're promoted to the library
-- via audios_audios_connection (created by /attempt/audio/upload).

CREATE TABLE IF NOT EXISTS public.audios_resource (
    id uuid DEFAULT uuidv7() CONSTRAINT audios_resource_id_not_null NOT NULL,
    created_at timestamp with time zone DEFAULT now() CONSTRAINT audios_resource_created_at_not_null NOT NULL,
    name text CONSTRAINT audios_resource_name_not_null NOT NULL,
    description text DEFAULT '' CONSTRAINT audios_resource_description_not_null NOT NULL,
    active boolean DEFAULT true CONSTRAINT audios_resource_active_not_null NOT NULL,
    generated boolean DEFAULT false CONSTRAINT audios_resource_generated_not_null NOT NULL,
    mcp boolean DEFAULT false CONSTRAINT audios_resource_mcp_not_null NOT NULL
);

ALTER TABLE ONLY public.audios_resource
    ADD CONSTRAINT audios_resource_pkey PRIMARY KEY (id);

CREATE INDEX IF NOT EXISTS audios_resource_active_idx ON public.audios_resource USING btree (active);
CREATE INDEX IF NOT EXISTS audios_resource_created_at_idx ON public.audios_resource USING btree (created_at);
CREATE INDEX IF NOT EXISTS audios_resource_name_idx ON public.audios_resource USING btree (name);
CREATE INDEX IF NOT EXISTS idx_audios_resource_mcp ON public.audios_resource USING btree (mcp);
