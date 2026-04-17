-- Migration: Add agent draft snapshot connection
-- Purpose: unblock canonical draft persistence for agent prompt/instruction state.
--
-- Why this exists:
-- - Published agents already persist prompt/instruction through agent_agents_junction
--   -> agents_resource snapshots, not direct prompt/instruction junctions.
-- - Agent drafts do not currently have the draft-side equivalent connection table.
-- - Because of that, agent draft PATCH can echo prompt/instruction in form_state, but
--   draft reload and pending/accept flows cannot persist them canonically.
--
-- Scope:
-- - Add agent_drafts_agents_connection
-- - Add the matching FK constraints
-- - Add the supporting resource-id index
--
-- Intentionally not included:
-- - No direct agent_drafts_prompts_connection or agent_drafts_instructions_connection.
--   That would diverge from the published artifact model.
-- - No pending_ids/query rewrites. Those are application-layer changes on top of this.

CREATE TABLE IF NOT EXISTS public.agent_drafts_agents_connection (
    draft_id uuid NOT NULL,
    agents_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.agent_drafts_agents_connection
        ADD CONSTRAINT agent_drafts_agents_connection_pkey PRIMARY KEY (draft_id, agents_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.agent_drafts_agents_connection
        ADD CONSTRAINT agent_drafts_agents_connection_draft_id_fkey FOREIGN KEY (draft_id)
        REFERENCES public.agent_drafts_entry(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY public.agent_drafts_agents_connection
        ADD CONSTRAINT agent_drafts_agents_connection_agents_id_fkey FOREIGN KEY (agents_id)
        REFERENCES public.agents_resource(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_agent_drafts_agents_resource_id
    ON public.agent_drafts_agents_connection USING btree (agents_id);
