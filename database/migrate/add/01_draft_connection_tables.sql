-- Idempotent migration: create missing draft connection tables
-- for agent (prompts, instructions), invocation (modalities, qualities),
-- and eval (model_flags, model_positions, model_rubrics).

-- ============================================================
-- Agent: prompts
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_drafts_prompts_connection (
    draft_id uuid NOT NULL,
    prompts_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.agent_drafts_prompts_connection
        ADD CONSTRAINT agent_drafts_prompts_connection_pkey PRIMARY KEY (draft_id, prompts_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- Agent: instructions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_drafts_instructions_connection (
    draft_id uuid NOT NULL,
    instructions_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.agent_drafts_instructions_connection
        ADD CONSTRAINT agent_drafts_instructions_connection_pkey PRIMARY KEY (draft_id, instructions_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- Invocation: modalities
-- ============================================================
CREATE TABLE IF NOT EXISTS public.invocation_drafts_modalities_connection (
    draft_id uuid NOT NULL,
    modalities_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.invocation_drafts_modalities_connection
        ADD CONSTRAINT invocation_drafts_modalities_connection_pkey PRIMARY KEY (draft_id, modalities_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- Invocation: qualities
-- ============================================================
CREATE TABLE IF NOT EXISTS public.invocation_drafts_qualities_connection (
    draft_id uuid NOT NULL,
    qualities_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.invocation_drafts_qualities_connection
        ADD CONSTRAINT invocation_drafts_qualities_connection_pkey PRIMARY KEY (draft_id, qualities_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- Eval: model_flags
-- ============================================================
CREATE TABLE IF NOT EXISTS public.eval_drafts_model_flags_connection (
    draft_id uuid NOT NULL,
    model_flags_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.eval_drafts_model_flags_connection
        ADD CONSTRAINT eval_drafts_model_flags_connection_pkey PRIMARY KEY (draft_id, model_flags_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- Eval: model_positions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.eval_drafts_model_positions_connection (
    draft_id uuid NOT NULL,
    model_positions_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.eval_drafts_model_positions_connection
        ADD CONSTRAINT eval_drafts_model_positions_connection_pkey PRIMARY KEY (draft_id, model_positions_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- Eval: model_rubrics
-- ============================================================
CREATE TABLE IF NOT EXISTS public.eval_drafts_model_rubrics_connection (
    draft_id uuid NOT NULL,
    model_rubrics_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

DO $$ BEGIN
    ALTER TABLE ONLY public.eval_drafts_model_rubrics_connection
        ADD CONSTRAINT eval_drafts_model_rubrics_connection_pkey PRIMARY KEY (draft_id, model_rubrics_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
