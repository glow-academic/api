"""Generic helper for parsing agent streaming events with callbacks."""

import json
from collections.abc import Awaitable, Callable
from typing import Any


class ToolCallState:
    """State tracking for a single tool call."""

    def __init__(self, tool_call_id: str, call_id: str | None = None):
        """Initialize tool call state.

        Args:
            tool_call_id: The real tool call ID (used for tracking)
            call_id: The call_id from the agent (may be None)
        """
        self.tool_call_id = tool_call_id
        self.call_id = call_id
        self.tool_name: str | None = None
        self.arguments_raw = ""
        self.completed = False


class StreamEventCallbacks:
    """Callbacks for handling different stream event types."""

    def __init__(
        self,
        on_tool_call_start: Callable[[str, str, str | None], Awaitable[None]]
        | None = None,
        on_tool_call_progress: Callable[[str, str], Awaitable[None]] | None = None,
        on_tool_call_complete: Callable[[str, dict[str, Any]], Awaitable[None]]
        | None = None,
    ):
        """Initialize callbacks.

        Args:
            on_tool_call_start: Called when tool call starts (tool_call_id, tool_name, call_id)
            on_tool_call_progress: Called with argument delta (tool_call_id, arguments_delta)
            on_tool_call_complete: Called when tool call completes (tool_call_id, final_arguments_dict)
        """
        self.on_tool_call_start = on_tool_call_start
        self.on_tool_call_progress = on_tool_call_progress
        self.on_tool_call_complete = on_tool_call_complete


async def stream_agent_events(
    result_runner: Any,  # Result from Runner.run_streamed() - has stream_events() method
    callbacks: StreamEventCallbacks,
    tool_call_id_generator: Callable[[str | None], str] | None = None,
) -> None:
    """Parse agent streaming events and call callbacks.

    Generic helper that handles all the manual parsing logic for agent streams.
    Works for any agent - just pass callbacks for what you want to handle.

    Args:
        result_runner: Runner instance from Runner.run_streamed()
        callbacks: Callbacks for different event types
        tool_call_id_generator: Optional function to generate tool_call_id from call_id.
                              If None, uses call_id directly, or generates if call_id is None.
                              Function signature: (call_id: str | None) -> str
    """
    tool_calls: dict[str, ToolCallState] = {}
    fake_id_to_real_id: dict[str, str] = {}
    tool_call_counter = 0

    def get_or_create_tool_call_id(
        call_id: str | None, fake_item_id: str | None
    ) -> str | None:
        """Get or create tool_call_id from call_id or fake_item_id.

        Args:
            call_id: The call_id from the agent (preferred)
            fake_item_id: The fake item ID from the event (fallback)

        Returns:
            The real tool_call_id, or None if neither is available
        """
        if call_id:
            return call_id
        if fake_item_id:
            if fake_item_id in fake_id_to_real_id:
                return fake_id_to_real_id[fake_item_id]
            # Generate new ID
            if tool_call_id_generator:
                real_id = tool_call_id_generator(call_id)
            else:
                tool_call_counter += 1
                real_id = f"tool_{tool_call_counter}_{fake_item_id[:8]}"
            fake_id_to_real_id[fake_item_id] = real_id
            return real_id
        return None

    async for event in result_runner.stream_events():
        if not hasattr(event, "type") or event.type != "raw_response_event":
            continue

        event_data = getattr(event, "data", None)
        if not event_data:
            continue

        event_data_type = getattr(event_data, "type", None)

        # Handle tool call start
        if event_data_type == "response.output_item.added":
            item = getattr(event_data, "item", None)
            if item and getattr(item, "type", None) == "function_call":
                fake_item_id = getattr(item, "id", None) or getattr(
                    event_data, "item_id", None
                )
                tool_name = getattr(item, "name", None)
                call_id = getattr(item, "call_id", None)

                tool_call_id = get_or_create_tool_call_id(call_id, fake_item_id)
                if not tool_call_id or not tool_name:
                    continue

                # Create or update tool call state
                if tool_call_id not in tool_calls:
                    tool_calls[tool_call_id] = ToolCallState(
                        tool_call_id=tool_call_id, call_id=call_id
                    )
                tool_calls[tool_call_id].tool_name = tool_name

                # Call callback
                if callbacks.on_tool_call_start:
                    await callbacks.on_tool_call_start(tool_call_id, tool_name, call_id)

        # Handle argument deltas
        elif event_data_type == "response.function_call_arguments.delta":
            call_id = getattr(event_data, "call_id", None)
            fake_item_id = getattr(event_data, "item_id", None)
            arguments_delta = getattr(event_data, "delta", None)

            if not arguments_delta:
                continue

            tool_call_id = get_or_create_tool_call_id(call_id, fake_item_id)
            if not tool_call_id:
                continue

            # Update state
            if tool_call_id not in tool_calls:
                tool_calls[tool_call_id] = ToolCallState(
                    tool_call_id=tool_call_id, call_id=call_id
                )
            tool_calls[tool_call_id].arguments_raw += arguments_delta

            # Update tool name if we have call_id match
            if not tool_calls[tool_call_id].tool_name and call_id:
                for tc_id, tc_state in tool_calls.items():
                    if tc_state.call_id == call_id and tc_state.tool_name:
                        tool_calls[tool_call_id].tool_name = tc_state.tool_name
                        break

            # Call callback
            if callbacks.on_tool_call_progress:
                await callbacks.on_tool_call_progress(tool_call_id, arguments_delta)

        # Handle tool call completion
        elif event_data_type == "response.output_item.done":
            item = getattr(event_data, "item", None)
            call_id = getattr(item, "call_id", None) if item else None
            if not call_id:
                call_id = getattr(event_data, "call_id", None)
            fake_item_id = getattr(event_data, "item_id", None)

            tool_call_id = get_or_create_tool_call_id(call_id, fake_item_id)
            if not tool_call_id or tool_call_id not in tool_calls:
                continue

            tool_call_state = tool_calls[tool_call_id]
            if tool_call_state.completed:
                continue

            tool_call_state.completed = True

            # Parse final arguments
            final_args = {}
            try:
                if tool_call_state.arguments_raw:
                    final_args = json.loads(tool_call_state.arguments_raw)
            except json.JSONDecodeError:
                pass

            # Call callback
            if callbacks.on_tool_call_complete:
                await callbacks.on_tool_call_complete(tool_call_id, final_args)

            # Clean up
            del tool_calls[tool_call_id]
