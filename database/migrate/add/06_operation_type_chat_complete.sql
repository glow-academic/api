-- Add chat_complete to operation_type enum
ALTER TYPE public.operation_type ADD VALUE IF NOT EXISTS 'chat_complete' AFTER 'chat_hints';
