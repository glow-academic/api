-- Migration: Drop remaining version columns from agent draft connection tables
-- These were missed by migration 08 because they were recreated from schema.sql

ALTER TABLE public.agent_drafts_departments_connection DROP COLUMN IF EXISTS version;
ALTER TABLE public.agent_drafts_descriptions_connection DROP COLUMN IF EXISTS version;
