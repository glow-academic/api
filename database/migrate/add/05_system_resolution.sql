-- Migration: Add resolution config to systems
-- Purpose: Configure how multi-agent contested outputs are resolved
--
-- resolution_strategy: how to pick winners from eval scores
--   'max'       — highest score wins per pair
--   'threshold'  — highest score wins, but reject if both below threshold
--   'consensus'  — random if score gap < threshold, otherwise highest wins
--   'random'     — coin flip (A/B test baseline)
--   NULL         — no resolution (single-agent system, no competition)
--
-- resolution_threshold: numeric parameter used by 'threshold' and 'consensus'
--   threshold: minimum acceptable score
--   consensus: minimum gap to declare a clear winner
--   ignored by 'max' and 'random'

ALTER TABLE public.systems_resource
    ADD COLUMN IF NOT EXISTS resolution_strategy text DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS resolution_threshold numeric DEFAULT NULL;
