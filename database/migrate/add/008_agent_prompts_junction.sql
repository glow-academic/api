-- Migration: introduce agent_prompts_junction.
--
-- prompts is declared as a full agent resource section
-- (core/app/infra/agent/permissions.py:372, sections.py:145, types.py:509)
-- but was the only section that still resolved its ids by walking
-- scalar FKs on agents_resource rows instead of reading a junction
-- table. Every other section (names/descriptions/models/tools/
-- voices/reasoning_levels/temperature_levels/qualities/rubrics/
-- agents) has an agent_X_junction.
--
-- This migration adds the missing junction, backfills it from
-- existing (agent_agents_junction × agents_resource.prompt_id) pairs
-- so no current agent loses its prompts association, and keeps
-- agents_resource.prompt_id in place as the per-embodiment primary
-- prompt. The junction is the canonical artifact-level read path
-- going forward.

CREATE TABLE IF NOT EXISTS public.agent_prompts_junction (
    agent_id uuid NOT NULL,
    prompts_id uuid NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

ALTER TABLE ONLY public.agent_prompts_junction
    DROP CONSTRAINT IF EXISTS agent_prompts_junction_pkey;
ALTER TABLE ONLY public.agent_prompts_junction
    ADD CONSTRAINT agent_prompts_junction_pkey PRIMARY KEY (agent_id, prompts_id);

ALTER TABLE ONLY public.agent_prompts_junction
    DROP CONSTRAINT IF EXISTS agent_prompts_junction_agent_id_fkey;
ALTER TABLE ONLY public.agent_prompts_junction
    ADD CONSTRAINT agent_prompts_junction_agent_id_fkey
    FOREIGN KEY (agent_id) REFERENCES public.agent_artifact(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.agent_prompts_junction
    DROP CONSTRAINT IF EXISTS agent_prompts_junction_prompts_id_fkey;
ALTER TABLE ONLY public.agent_prompts_junction
    ADD CONSTRAINT agent_prompts_junction_prompts_id_fkey
    FOREIGN KEY (prompts_id) REFERENCES public.prompts_resource(id) ON DELETE CASCADE;

-- Backfill: for each active (agent_id, agents_resource) pair that has
-- a prompt_id set, seed the junction. Matches the legacy derivation
-- in agent/context.py that unioned per-embodiment prompt_ids.
INSERT INTO public.agent_prompts_junction (agent_id, prompts_id, active, generated, mcp)
SELECT DISTINCT
    j.agent_id,
    ar.prompt_id AS prompts_id,
    true,
    false,
    false
FROM public.agent_agents_junction j
JOIN public.agents_resource ar ON ar.id = j.agents_id
WHERE j.active = true
  AND ar.prompt_id IS NOT NULL
ON CONFLICT (agent_id, prompts_id) DO NOTHING;
