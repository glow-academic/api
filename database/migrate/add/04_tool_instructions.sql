-- Migration: Add instructions support to tools
-- Purpose: Tool response templates (Layer 3 of three-layer prompt architecture)
--
-- This adds:
-- 1. tool_instructions_junction — links tools to instructions_resource (response templates)
-- 2. tool_drafts_instructions_connection — draft version of the same
-- 3. instruction_id column on tools_resource (singular — one response template per tool)

-- ── Junction table: tool → instructions ──────────────────────────────

CREATE TABLE IF NOT EXISTS public.tool_instructions_junction (
    tool_id uuid NOT NULL,
    instructions_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_instructions_junction
        ADD CONSTRAINT tool_instructions_junction_pkey PRIMARY KEY (tool_id, instructions_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_instructions_junction
        ADD CONSTRAINT tool_instructions_tool_id_fkey FOREIGN KEY (tool_id)
        REFERENCES public.tool_artifact(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_instructions_junction
        ADD CONSTRAINT tool_instructions_instructions_id_fkey FOREIGN KEY (instructions_id)
        REFERENCES public.instructions_resource(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Drafts connection: tool_draft → instructions ─────────────────────

CREATE TABLE IF NOT EXISTS public.tool_drafts_instructions_connection (
    draft_id uuid NOT NULL,
    instructions_id uuid NOT NULL,
    version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_drafts_instructions_connection
        ADD CONSTRAINT tool_drafts_instructions_connection_pkey PRIMARY KEY (draft_id, instructions_id, version);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_drafts_instructions_connection
        ADD CONSTRAINT tool_drafts_instructions_draft_id_fkey FOREIGN KEY (draft_id)
        REFERENCES public.tool_drafts_entry(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_drafts_instructions_connection
        ADD CONSTRAINT tool_drafts_instructions_instructions_id_fkey FOREIGN KEY (instructions_id)
        REFERENCES public.instructions_resource(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Add instruction_id to tools_resource ─────────────────────────────

ALTER TABLE public.tools_resource
    ADD COLUMN IF NOT EXISTS instruction_id uuid;

DO $$ BEGIN
    ALTER TABLE public.tools_resource
        ADD CONSTRAINT tools_resource_instruction_id_fkey FOREIGN KEY (instruction_id)
        REFERENCES public.instructions_resource(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
