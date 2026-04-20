-- Migration: add audios_audios_connection
--
-- Links audios_entry (per-session instance) to audios_resource (library
-- asset). Mirrors images_images_connection. A connection row is created
-- by /attempt/audio/upload when promoting a capture to a library asset.

CREATE TABLE IF NOT EXISTS public.audios_audios_connection (
    audio_id uuid NOT NULL,
    audios_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

ALTER TABLE ONLY public.audios_audios_connection
    ADD CONSTRAINT audios_audios_connection_pkey PRIMARY KEY (audio_id, audios_id);

ALTER TABLE ONLY public.audios_audios_connection
    ADD CONSTRAINT audios_audios_connection_audio_id_fkey
    FOREIGN KEY (audio_id) REFERENCES public.audios_entry(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.audios_audios_connection
    ADD CONSTRAINT audios_audios_connection_audios_id_fkey
    FOREIGN KEY (audios_id) REFERENCES public.audios_resource(id);

CREATE INDEX IF NOT EXISTS idx_audios_audios_connection_audio_id ON public.audios_audios_connection USING btree (audio_id);
CREATE INDEX IF NOT EXISTS idx_audios_audios_connection_audios_id ON public.audios_audios_connection USING btree (audios_id);
