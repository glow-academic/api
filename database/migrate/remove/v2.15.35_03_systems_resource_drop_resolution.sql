-- v2.15.35_03_systems_resource_drop_resolution.sql
--
-- Drop the orphaned ``resolution_strategy`` + ``resolution_threshold``
-- columns from ``systems_resource``.
--
-- The auto-resolution engine (``resolve_tool_results`` strategy chooser)
-- was never wired into production — its consumer paths in
-- ``app/infra/types.py``, ``system_context.py``, ``websocket_context.py``,
-- ``setting/types.py|sections.py|draft.py``, and ``prepare.py`` have
-- already been removed alongside the dead engine files
-- (``resolve_tool_results.py``, ``run_tracker.py``, etc.).
--
-- Promotion / demotion is now fully client-driven via the
-- ``soft_calls_entry`` ack pattern (``idempotency_key + accept`` on
-- the canonical create/update endpoints). No threshold or strategy
-- configuration is consulted server-side.
--
-- Safety: both columns are nullable, carry no indexes, no constraints,
-- and no view/MV references project them. Pure data drop.

ALTER TABLE public.systems_resource DROP COLUMN IF EXISTS resolution_strategy;
ALTER TABLE public.systems_resource DROP COLUMN IF EXISTS resolution_threshold;
