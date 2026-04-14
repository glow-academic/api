-- Migration: Add 'group' to operation_type enum.

ALTER TYPE public.operation_type ADD VALUE IF NOT EXISTS 'group';
