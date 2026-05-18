"""MCP resource seeds.

One row per MCP configuration a setting can attach via `mcp_id`.
`mcp_resource.agent_id` points at an `agents_resource` (the denormalized
snapshot that carries `tool_ids` and `prompt_id`), matching the
convention `tools_resource.agent_id` already uses.
"""

from database.seeds.agents import COMPOSER_AGENT_RESOURCE
from database.seeds.ids import sid

MCP_COMPOSER = sid("mcp-resource/composer")

mcp_resources = [
    dict(
        id=MCP_COMPOSER,
        agent_id=COMPOSER_AGENT_RESOURCE,
        name="Composer MCP",
        description="MCP surface backed by the Composer agent.",
    ),
]
