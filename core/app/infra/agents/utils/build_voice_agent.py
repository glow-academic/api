"""Build voice agent with persona tools for voice mode."""

from typing import Any

from app.infra.agents.generic_agent import DEBUG_INFO_TOOL_SUFFIX, GenericAgent
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def build_voice_agent(
    context: dict[str, Any],
    persona_tools: list[Any],
    base_system_prompt: str,
    persona_instructions_map: dict[str, str],
) -> tuple[GenericAgent, str]:
    """Create the voice agent with persona tools and build complete instructions.

    The voice agent decides which persona should respond by calling
    the `speak` tool with the persona name and message.

    Args:
        context: Context dict with agent, model, and provider data
        persona_tools: List containing the single speak tool (created by caller)
        base_system_prompt: Base simulation prompt from agent (e.g., simulation-voice prompt)
        persona_instructions_map: Map of persona_name -> persona instructions

    Returns:
        Tuple of (GenericAgent instance, complete instructions string)
        The instructions string should be sent to RealtimeAgent's instructions field
    """

    # Note: tool_use_behavior is no longer used with direct litellm calls
    # Tool calling loop will continue until no more tool calls are made
    # The voice agent should call the speak tool, which will be handled by the tool calling loop

    # Extract persona names from persona_instructions_map
    persona_names = list(persona_instructions_map.keys())

    # Build persona descriptions with their instructions
    persona_descriptions = []
    for persona_name in persona_names:
        instructions = persona_instructions_map.get(persona_name, "")
        if instructions:
            persona_descriptions.append(f"- {persona_name}: {instructions}")
        else:
            persona_descriptions.append(f"- {persona_name}")

    # Build list of available persona names for tool usage
    persona_names_list = [f'"{name}"' for name in persona_names]

    # Build tool usage instructions
    tool_usage_section = f"""
Tool Usage Instructions:
- You MUST use the `speak` tool to respond as a persona
- The `speak` tool takes two parameters:
  * `persona`: The name of the persona that should speak (must be one of: {", ".join(persona_names_list)})
  * `message`: The message content that the persona should say
- Call exactly one tool per user message
- Never respond directly - always use the `speak` tool
- The persona name must match exactly one of the available personas listed above

When the `speak` tool is used, the specified persona will generate and speak the response based on their personality described above.
"""

    # Build complete instructions: base_prompt + persona_list + tool_usage + debug_info
    complete_instructions = f"""{base_system_prompt}

---

Available Personas and Their Personalities:
{chr(10).join(persona_descriptions)}
{tool_usage_section}
{DEBUG_INFO_TOOL_SUFFIX}"""

    # Build minimal system prompt for GenericAgent (used internally, not sent to Realtime API)
    voice_agent_prompt = f"""You are a voice agent managing a multi-party conversation.

Available personas:
{chr(10).join(f"- {name}" for name in persona_names)}

CRITICAL: You have access to the `speak` tool. You MUST use it to make a persona respond.

Your role:
- Listen to the user's input
- Decide which persona should respond based on the context
- Use the `speak` tool with:
  * `persona`: The name of the persona (must be one of: {", ".join(persona_names_list)})
  * `message`: The message content for that persona to say
- Never respond directly - always use the `speak` tool
- The persona name must match exactly one of the available personas listed above

When the `speak` tool is used, the specified persona will generate and speak the response.
You must use exactly one `speak` tool call per user message.

Example: To make the "{persona_names[0] if persona_names else "persona"}" persona respond, call: speak(persona="{persona_names[0] if persona_names else "persona"}", message="your message here")"""

    agent = GenericAgent(
        agent_name="Voice Agent",
        system_prompt=voice_agent_prompt,
        temperature=context.get("temperature", 0.7),
        model_name=context["model_name"],
        provider=context["provider_name"],
        base_url=context.get("base_url"),
        reasoning=context.get("reasoning"),
        api_key=context["api_key"],
        tools=persona_tools,
        parallel_tool_calls=False,  # Call one persona at a time
        tool_use_behavior=None,  # Not used with direct litellm calls
    )

    return (agent, complete_instructions)
