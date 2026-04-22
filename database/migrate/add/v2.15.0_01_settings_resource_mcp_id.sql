-- Migration: rename settings_resource.mcp_agent_id -> mcp_id.
--
-- The column used to hold a denormalized agents_resource id ("the agent this
-- setting's MCP binds to"). That was too aggressive a denormalization:
-- whenever mcp_resource.agent_id changed, every settings_resource snapshot
-- silently went stale.
--
-- Canonical model instead: settings_resource holds mcp_id (pointer into
-- mcp_resource, the catalog). Runtime walks
--   settings_resource.mcp_id -> mcp_resource.agent_id -> agents_resource
-- at read time. Both hops are redis-cached black boxes, so the cost is
-- negligible and the setting always sees the MCP's current agent.

ALTER TABLE public.settings_resource
    RENAME COLUMN mcp_agent_id TO mcp_id;
