-- Add unique constraint on attempt_completion_entry(attempt_id)
-- so attempt_complete is idempotent (ON CONFLICT DO NOTHING).
DO $$ BEGIN
    ALTER TABLE public.attempt_completion_entry
        ADD CONSTRAINT attempt_completion_entry_attempt_unique UNIQUE (attempt_id);
EXCEPTION WHEN duplicate_table THEN
    NULL;
END $$;
