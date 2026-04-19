-- Add chat_message to operation_type enum (renamed from chat_send)
ALTER TYPE public.operation_type ADD VALUE IF NOT EXISTS 'chat_message' AFTER 'chat_complete';
