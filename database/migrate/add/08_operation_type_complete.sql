-- Add 'complete' to operation_type enum (attempt-level completion)
ALTER TYPE public.operation_type ADD VALUE IF NOT EXISTS 'complete' AFTER 'chat_complete';
