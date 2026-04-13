-- Migration: Add agent delegation support to tools
-- Purpose: A tool can optionally delegate execution to a specialist agent.
--
-- This adds:
-- 1. tool_agents_junction — links tool_artifact to agents_resource
-- 2. tool_drafts_agents_connection — draft version of the same
-- 3. agent_id column on tools_resource (singular — one delegate agent per tool)

-- ── Junction table: tool → agents ───────────────────────────────────

CREATE TABLE IF NOT EXISTS public.tool_agents_junction (
    tool_id uuid NOT NULL,
    agents_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_agents_junction
        ADD CONSTRAINT tool_agents_junction_pkey PRIMARY KEY (tool_id, agents_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_agents_junction
        ADD CONSTRAINT tool_agents_tool_id_fkey FOREIGN KEY (tool_id)
        REFERENCES public.tool_artifact(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_agents_junction
        ADD CONSTRAINT tool_agents_agents_id_fkey FOREIGN KEY (agents_id)
        REFERENCES public.agents_resource(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Drafts connection: tool_draft → agents ──────────────────────────

CREATE TABLE IF NOT EXISTS public.tool_drafts_agents_connection (
    draft_id uuid NOT NULL,
    agents_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_drafts_agents_connection
        ADD CONSTRAINT tool_drafts_agents_connection_pkey PRIMARY KEY (draft_id, agents_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_drafts_agents_connection
        ADD CONSTRAINT tool_drafts_agents_draft_id_fkey FOREIGN KEY (draft_id)
        REFERENCES public.tool_drafts_entry(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.tool_drafts_agents_connection
        ADD CONSTRAINT tool_drafts_agents_agents_id_fkey FOREIGN KEY (agents_id)
        REFERENCES public.agents_resource(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Add agent_id to tools_resource ──────────────────────────────────

ALTER TABLE public.tools_resource
    ADD COLUMN IF NOT EXISTS agent_id uuid;

DO $$ BEGIN
    ALTER TABLE public.tools_resource
        ADD CONSTRAINT tools_resource_agent_id_fkey FOREIGN KEY (agent_id)
        REFERENCES public.agents_resource(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
