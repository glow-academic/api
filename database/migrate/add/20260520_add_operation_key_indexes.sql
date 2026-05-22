-- Idempotency replay gate — lookup indexes on operation_key.
--
-- The gate composes search_calls(operation_keys=[...]) → calls_mv lookup to find
-- a prior completed call for a client-supplied operation_key and replay its
-- receipt instead of re-executing. These indexes turn that lookup into a seek.
--
-- NOTE: a UNIQUE(operation_key) integrity constraint on calls_entry is
-- intentionally NOT added here. It must land together with the replay gate —
-- the gate's replay is what prevents the duplicate INSERT that the constraint
-- would otherwise reject. Adding it before the gate exists could turn a
-- currently-silent duplicate operation_key (e.g. an LLM-dispatch retry) into a
-- hard INSERT failure. Verified safe to add later: 15/15 keys distinct, 0 nulls.

-- Read path: search_calls reads calls_mv; this index serves the gate's lookup.
CREATE INDEX IF NOT EXISTS idx_calls_mv_operation_key
    ON public.calls_mv (operation_key);

-- Base-table lookup + precursor to the future UNIQUE(operation_key) constraint.
CREATE INDEX IF NOT EXISTS idx_calls_entry_operation_key
    ON public.calls_entry (operation_key);
