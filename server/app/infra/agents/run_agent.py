"""Agent execution with tool calling using litellm directly."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import litellm  # type: ignore

from app.infra.artifacts.convert_tools_to_openai_format import (
    convert_tools_to_openai_format,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentRunResult:
    """Result from running an agent with tools."""

    final_output: str
    usage: dict[str, Any]
    context_wrapper: Any  # For compatibility with existing code


class MockContextWrapper:
    """Mock context wrapper for compatibility."""

    def __init__(self, usage: dict[str, Any]):
        self.usage = usage


async def run_agent_with_tools(
    messages: list[dict[str, Any]],
    tools: list[Any] | None = None,
    tool_functions: dict[str, Any] | None = None,
    model: str = "gpt-4",
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    system_prompt: str | None = None,
    max_iterations: int = 10,
) -> AgentRunResult:
    """Run an agent with tool calling support using litellm directly.

    This replaces Runner.run() from openai-agents package.

    Args:
        messages: List of message dicts with 'role' and 'content'
        tools: List of tool configs (for conversion to OpenAI format)
        tool_functions: Dict mapping tool names to callable functions
        model: Model name (e.g., "gpt-4", "gpt-4o")
        api_key: API key for the model
        base_url: Base URL for custom models
        temperature: Temperature setting
        system_prompt: System prompt (prepended to messages)
        max_iterations: Maximum tool calling iterations

    Returns:
        AgentRunResult with final_output, usage, and context_wrapper
    """
    # Prepare messages with system prompt
    conversation_messages = []
    if system_prompt:
        conversation_messages.append({"role": "system", "content": system_prompt})
    conversation_messages.extend(messages)

    # Convert tools to OpenAI format if provided
    openai_tools = None
    if tools:
        openai_tools = convert_tools_to_openai_format(tools)

    # Prepare litellm kwargs
    litellm_kwargs: dict[str, Any] = {
        "model": model,
        "messages": conversation_messages,
        "temperature": temperature,
    }

    if api_key:
        litellm_kwargs["api_key"] = api_key
    if base_url:
        litellm_kwargs["api_base"] = base_url
    if openai_tools:
        litellm_kwargs["tools"] = openai_tools

    # Track total usage across all iterations
    total_usage: dict[str, Any] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    iteration = 0
    final_output = ""

    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent iteration {iteration}/{max_iterations}")

        # Call litellm
        try:
            response = await litellm.acompletion(**litellm_kwargs)
        except Exception as e:
            logger.error(f"Error calling litellm: {e}")
            raise

        # Extract usage from response (handle both dict and object formats)
        usage_obj = None
        if isinstance(response, dict):
            usage_obj = response.get("usage")
        elif hasattr(response, "usage"):
            usage_obj = response.usage

        if usage_obj:
            if isinstance(usage_obj, dict):
                total_usage["prompt_tokens"] += usage_obj.get("prompt_tokens", 0)
                total_usage["completion_tokens"] += usage_obj.get(
                    "completion_tokens", 0
                )
                total_usage["total_tokens"] += usage_obj.get("total_tokens", 0)
            else:
                total_usage["prompt_tokens"] += getattr(usage_obj, "prompt_tokens", 0)
                total_usage["completion_tokens"] += getattr(
                    usage_obj, "completion_tokens", 0
                )
                total_usage["total_tokens"] += getattr(usage_obj, "total_tokens", 0)

        # Check for tool calls (handle both dict and object formats)
        choices = None
        if isinstance(response, dict):
            choices = response.get("choices", [])
        elif hasattr(response, "choices"):
            choices = response.choices

        if not choices or len(choices) == 0:
            break

        choice = choices[0]
        message = None
        if isinstance(choice, dict):
            message = choice.get("message", {})
        elif hasattr(choice, "message"):
            message = choice.message

        if not message:
            break

        # Extract tool_calls from message
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls")
        else:
            tool_calls = getattr(message, "tool_calls", None)

        # Extract content from message
        message_content = None
        if isinstance(message, dict):
            message_content = message.get("content")
        else:
            message_content = getattr(message, "content", None)

        # If no tool calls, we're done
        if not tool_calls:
            final_output = message_content or ""
            break

        # Add assistant message with tool calls to conversation
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": message_content,
            "tool_calls": [],
        }

        # Process tool calls
        tool_results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            # Handle both dict and object formats
            if isinstance(tool_call, dict):
                tool_call_id = tool_call.get("id")
                function_obj = tool_call.get("function", {})
                function_name = (
                    function_obj.get("name") if isinstance(function_obj, dict) else None
                )
                function_args_str = (
                    function_obj.get("arguments", "{}")
                    if isinstance(function_obj, dict)
                    else "{}"
                )
            else:
                tool_call_id = getattr(tool_call, "id", None)
                function_obj = getattr(tool_call, "function", None)
                if function_obj:
                    if isinstance(function_obj, dict):
                        function_name = function_obj.get("name")
                        function_args_str = function_obj.get("arguments", "{}")
                    else:
                        function_name = getattr(function_obj, "name", None)
                        function_args_str = getattr(function_obj, "arguments", "{}")
                else:
                    function_name = None
                    function_args_str = "{}"

            if not function_name:
                continue

            # Parse function arguments
            try:
                function_args = (
                    json.loads(function_args_str) if function_args_str else {}
                )
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse tool call arguments: {function_args_str}"
                )
                function_args = {}

            # Execute tool function
            tool_result = "Tool execution failed"
            if tool_functions and function_name in tool_functions:
                try:
                    tool_func = tool_functions[function_name]
                    # Tools are async functions, but some might be sync
                    if callable(tool_func):
                        try:
                            # For simple tools, they just return success messages
                            # Pass context if needed (but most tools don't use it)
                            if asyncio.iscoroutinefunction(tool_func):
                                tool_result = await tool_func(**function_args)
                            else:
                                tool_result = tool_func(**function_args)
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {e}")
                            tool_result = f"Error: {str(e)}"
                    else:
                        tool_result = "Tool function not callable"
                except Exception as e:
                    logger.error(f"Error executing tool {function_name}: {e}")
                    tool_result = f"Error: {str(e)}"
            else:
                logger.warning(f"Tool function not found: {function_name}")
                tool_result = f"Tool {function_name} not available"

            # Add tool call to assistant message (for conversation history)
            if tool_call_id:
                assistant_message["tool_calls"].append(
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": function_args_str,
                        },
                    }
                )

            # Add tool result
            tool_results.append(
                {
                    "role": "tool",
                    "content": str(tool_result),
                    "tool_call_id": tool_call_id,
                }
            )

        # Add assistant message and tool results to conversation
        conversation_messages.append(assistant_message)
        conversation_messages.extend(tool_results)

        # Update litellm kwargs for next iteration
        litellm_kwargs["messages"] = conversation_messages

    if iteration >= max_iterations:
        logger.warning(
            f"Reached max iterations ({max_iterations}), returning current output"
        )

    # Create result object compatible with Runner.run() return value
    context_wrapper = MockContextWrapper(usage=total_usage)
    result = AgentRunResult(
        final_output=final_output,
        usage=total_usage,
        context_wrapper=context_wrapper,
    )

    return result
