-- Migration: Add session_id to attempt entry tables, backfill from calls_entry
-- Non-destructive: both call_id and session_id coexist temporarily

-- Step 1: Add session_id column to all tables that have call_id but not session_id
ALTER TABLE attempt_analysis_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_archive_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_chat_completion_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_chat_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_completion_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_content_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_conversation_completion_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_conversations_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_feedback_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_grade_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_highlight_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_hint_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_improvement_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_message_completion_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_message_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_mutes_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_replacement_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_responses_entry ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE attempt_strength_entry ADD COLUMN IF NOT EXISTS session_id UUID;

-- Step 2: Backfill session_id from calls_entry via call_id
UPDATE attempt_analysis_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_analysis_entry.call_id AND attempt_analysis_entry.session_id IS NULL;
UPDATE attempt_archive_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_archive_entry.call_id AND attempt_archive_entry.session_id IS NULL;
UPDATE attempt_chat_completion_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_chat_completion_entry.call_id AND attempt_chat_completion_entry.session_id IS NULL;
UPDATE attempt_chat_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_chat_entry.call_id AND attempt_chat_entry.session_id IS NULL;
UPDATE attempt_completion_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_completion_entry.call_id AND attempt_completion_entry.session_id IS NULL;
UPDATE attempt_content_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_content_entry.call_id AND attempt_content_entry.session_id IS NULL;
UPDATE attempt_conversation_completion_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_conversation_completion_entry.call_id AND attempt_conversation_completion_entry.session_id IS NULL;
UPDATE attempt_conversations_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_conversations_entry.call_id AND attempt_conversations_entry.session_id IS NULL;
UPDATE attempt_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_entry.call_id AND attempt_entry.session_id IS NULL;
UPDATE attempt_feedback_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_feedback_entry.call_id AND attempt_feedback_entry.session_id IS NULL;
UPDATE attempt_grade_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_grade_entry.call_id AND attempt_grade_entry.session_id IS NULL;
UPDATE attempt_highlight_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_highlight_entry.call_id AND attempt_highlight_entry.session_id IS NULL;
UPDATE attempt_hint_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_hint_entry.call_id AND attempt_hint_entry.session_id IS NULL;
UPDATE attempt_improvement_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_improvement_entry.call_id AND attempt_improvement_entry.session_id IS NULL;
UPDATE attempt_message_completion_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_message_completion_entry.call_id AND attempt_message_completion_entry.session_id IS NULL;
UPDATE attempt_message_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_message_entry.call_id AND attempt_message_entry.session_id IS NULL;
UPDATE attempt_mutes_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_mutes_entry.call_id AND attempt_mutes_entry.session_id IS NULL;
UPDATE attempt_replacement_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_replacement_entry.call_id AND attempt_replacement_entry.session_id IS NULL;
UPDATE attempt_responses_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_responses_entry.call_id AND attempt_responses_entry.session_id IS NULL;
UPDATE attempt_strength_entry SET session_id = c.session_id FROM calls_entry c WHERE c.id = attempt_strength_entry.call_id AND attempt_strength_entry.session_id IS NULL;
