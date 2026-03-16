"""Create the hint generation agent from context data."""

from typing import Any

from app.infra.agents.generic_agent import GenericAgent
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def build_hint_agent(context: dict[str, Any], hint_tools: list[Any]) -> GenericAgent:
    """Create the hint generation agent from context data.

    Args:
        context: Context dict with agent, model, and provider data
        hint_tools: List of hint tools to use (created by caller)

    Returns:
        GenericAgent instance configured for hint generation
    """

    # Note: tool_use_behavior is no longer used with direct litellm calls
    # Tool calling loop will continue until no more tool calls are made
    # If specific stopping conditions are needed, they can be implemented
    # in the run_agent_with_tools function

    return GenericAgent(
        agent_name=context["agent_name"],
        system_prompt=context["system_prompt"],
        temperature=context["temperature"],
        model_name=context["model_name"],
        provider=context["provider"],
        base_url=context["base_url"],
        api_key=context["api_key"],
        reasoning=context["reasoning"],
        tools=hint_tools,
        parallel_tool_calls=True,  # Enable parallel execution
        tool_use_behavior=None,  # Not used with direct litellm calls
    )
