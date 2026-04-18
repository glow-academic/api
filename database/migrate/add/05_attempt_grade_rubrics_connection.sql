-- Migration: Create attempt_grade_rubrics_connection table
-- Links grades to the rubric they were graded against (separate from chat-rubric link)

CREATE TABLE IF NOT EXISTS public.attempt_grade_rubrics_connection (
    grade_id uuid NOT NULL,
    rubrics_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL,
    CONSTRAINT attempt_grade_rubrics_connection_pkey PRIMARY KEY (grade_id, rubrics_id)
);
