-- Migration: attempt_audio_entry — audio attachments to chat messages.
--
-- Post-hoc attachment pattern, mirrors attempt_hint_entry /
-- attempt_strength_entry / attempt_improvement_entry. A row represents
-- "this message has this audio attached." Each attachment is its own
-- entry with its own id — allows multiple audio attachments per message,
-- per-attachment soft-delete, and referencing a specific attach event.
--
-- message_id → attempt_message_entry.id (CASCADE — audio is cleaned up
--   when the message is deleted)
-- audios_id  → audios_resource.id (the resource-level public handle;
--   download and display go through this)
--
-- The realtime adapter auto-creates these rows for assistant turns
-- (correlating its captured audios_id with the model's tool-call message
-- in the same response). For the user side the client explicitly calls
-- POST /attempt/chat/audio after persisting the message.

CREATE TABLE IF NOT EXISTS public.attempt_audio_entry (
    id uuid DEFAULT uuidv7() NOT NULL,
    message_id uuid NOT NULL,
    audios_id uuid NOT NULL,
    session_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

ALTER TABLE ONLY public.attempt_audio_entry
    ADD CONSTRAINT attempt_audio_entry_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attempt_audio_entry
    ADD CONSTRAINT attempt_audio_entry_message_id_fkey
    FOREIGN KEY (message_id) REFERENCES public.attempt_message_entry(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attempt_audio_entry
    ADD CONSTRAINT attempt_audio_entry_audios_id_fkey
    FOREIGN KEY (audios_id) REFERENCES public.audios_resource(id);

CREATE INDEX IF NOT EXISTS idx_attempt_audio_entry_message_id
    ON public.attempt_audio_entry USING btree (message_id);
CREATE INDEX IF NOT EXISTS idx_attempt_audio_entry_audios_id
    ON public.attempt_audio_entry USING btree (audios_id);
CREATE INDEX IF NOT EXISTS idx_attempt_audio_entry_message_created_at
    ON public.attempt_audio_entry USING btree (message_id, created_at);
