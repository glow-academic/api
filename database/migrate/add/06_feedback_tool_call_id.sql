-- Migration: Add tool_call_id to test_feedback_entry
-- Purpose: Link each feedback to the specific tool call being evaluated
--
-- call_id     = the grading agent's call that produced this feedback
-- tool_call_id = the original agent's tool call this feedback is about
--
-- Required (NOT NULL) — every feedback must reference the tool call it evaluates.
-- Existing rows (if any) are removed since they lack this context.

DELETE FROM public.test_feedback_entry WHERE true;

ALTER TABLE public.test_feedback_entry
    ADD COLUMN IF NOT EXISTS tool_call_id uuid NOT NULL;

DO $$ BEGIN
    ALTER TABLE public.test_feedback_entry
        ADD CONSTRAINT test_feedback_entry_tool_call_id_fkey
        FOREIGN KEY (tool_call_id) REFERENCES public.calls_entry(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_test_feedback_entry_tool_call_id
    ON public.test_feedback_entry (tool_call_id);
