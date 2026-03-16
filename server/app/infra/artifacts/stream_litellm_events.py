"""Parse litellm streaming chunks into structured events.

Handles both completions() API (choices-based) and responses() API (response-based) formats.
Pure parsing/transformation only - no AI calls, no DB, no emits.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


# ----------------------------
# Streaming parser state classes
# ----------------------------
@dataclass
class TextState:
    started: bool = False
    buffer: str = ""


@dataclass
class ToolFnState:
    name: str | None = None
    arguments: str = ""


@dataclass
class ToolCallState:
    id: str | None = None
    type: str = "function"
    function: ToolFnState = field(default_factory=ToolFnState)


@dataclass
class ChoiceState:
    text: TextState = field(default_factory=TextState)
    tool_calls: dict[int, ToolCallState] = field(default_factory=dict)
    finish_reason: str | None = None


async def stream_litellm_events(
    stream: AsyncIterator[Any],
) -> AsyncIterator[dict[str, Any]]:
    """Convert litellm streaming chunks into structured events.

    Handles both completions() API (choices-based) and responses() API (response-based).
    Normalizes both to the same event schema.

    Yields events:
    - text_start: First text delta received
    - text_delta: Incremental text content
    - text_complete: Text streaming complete
    - tool_call_start: Tool call started (with stable tool_call_id)
    - tool_call_delta: Incremental tool call arguments (with stable tool_call_id)
    - tool_call_complete: Tool call complete (with stable tool_call_id)
    - message_complete: Message complete with finish_reason

    Args:
        stream: AsyncIterator from litellm.acompletion(stream=True) or litellm.aresponses(stream=True)

    Yields:
        Event dictionaries with 'type' and relevant fields
    """
    # Detect format on first chunk
    format_detected: str | None = None
    choices: dict[int, ChoiceState] = {}
    response_items: dict[
        str, dict[str, Any]
    ] = {}  # item_id -> state for responses() format

    def get_choice_state(choice_index: int) -> ChoiceState:
        if choice_index not in choices:
            choices[choice_index] = ChoiceState()
        return choices[choice_index]

    def stable_tool_key(choice_index: int, tool_index: int) -> str:
        # stable even if provider omits tool_call_id
        return f"choice_{choice_index}_tool_{tool_index}"

    # Track usage across all chunks
    # Usage represents completion - when we find it, emit completion event
    # All text/tool deltas are progress events (already handled)
    final_usage_data: dict[str, Any] | None = None
    usage_event_emitted = False
    response_completed_received = (
        False  # Track if response.completed was received (for Responses API)
    )

    async for chunk in stream:
        # Check every chunk for usage
        # LiteLLM docs: final chunk has usage field with token stats, choices is empty array
        chunk_dict_for_usage_check = None
        if hasattr(chunk, "model_dump"):
            try:
                chunk_dict_for_usage_check = chunk.model_dump()
            except Exception:
                pass
        elif hasattr(chunk, "dict"):
            try:
                chunk_dict_for_usage_check = chunk.dict()
            except Exception:
                pass
        elif isinstance(chunk, dict):
            chunk_dict_for_usage_check = chunk

        # Check for usage in chunk (may be in final chunk with empty choices)
        if chunk_dict_for_usage_check and isinstance(chunk_dict_for_usage_check, dict):
            usage_obj = chunk_dict_for_usage_check.get("usage")
            if (
                usage_obj is not None
            ):  # Check for non-null usage (final chunk has actual usage, others have null)
                if isinstance(usage_obj, dict):
                    # Extract usage from dict
                    final_usage_data = {
                        "prompt_tokens": usage_obj.get(
                            "prompt_tokens", usage_obj.get("input_tokens", 0)
                        ),
                        "completion_tokens": usage_obj.get(
                            "completion_tokens", usage_obj.get("output_tokens", 0)
                        ),
                    }
                elif hasattr(usage_obj, "prompt_tokens"):
                    # Extract usage from object
                    final_usage_data = {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    }

                # Usage represents completion - emit message_complete with usage immediately
                # This is centralized: usage = completion, regardless of when it arrives
                if final_usage_data:
                    # Get finish_reason from the last choice state if available
                    finish_reason = "stop"
                    if choices:
                        last_choice_state = choices.get(0)
                        if last_choice_state and last_choice_state.finish_reason:
                            finish_reason = last_choice_state.finish_reason

                    yield {
                        "type": "message_complete",
                        "choice_index": 0,
                        "finish_reason": finish_reason,
                        "usage": final_usage_data,
                    }
                    usage_event_emitted = True

        # Also check chunk.usage directly (for Pydantic models)
        if not final_usage_data and hasattr(chunk, "usage"):
            usage_obj = chunk.usage
            if usage_obj is not None:  # Check for non-null usage
                if hasattr(usage_obj, "prompt_tokens"):
                    final_usage_data = {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    }
                elif isinstance(usage_obj, dict):
                    final_usage_data = {
                        "prompt_tokens": usage_obj.get(
                            "prompt_tokens", usage_obj.get("input_tokens", 0)
                        ),
                        "completion_tokens": usage_obj.get(
                            "completion_tokens", usage_obj.get("output_tokens", 0)
                        ),
                    }

                # Usage represents completion - emit message_complete with usage immediately
                if final_usage_data:
                    # Get finish_reason from the last choice state if available
                    finish_reason = "stop"
                    if choices:
                        last_choice_state = choices.get(0)
                        if last_choice_state and last_choice_state.finish_reason:
                            finish_reason = last_choice_state.finish_reason

                    yield {
                        "type": "message_complete",
                        "choice_index": 0,
                        "finish_reason": finish_reason,
                        "usage": final_usage_data,
                    }
                    usage_event_emitted = True

        # Detect format on first chunk
        if format_detected is None:
            if hasattr(chunk, "type") or (
                isinstance(chunk, dict) and chunk.get("type")
            ):
                # Responses API format (has "type" field)
                format_detected = "responses"
            elif hasattr(chunk, "choices") or (
                isinstance(chunk, dict) and "choices" in chunk
            ):
                # Completions API format (has "choices" field)
                format_detected = "completions"
            else:
                # Default to completions for backward compatibility
                format_detected = "completions"

        # Route to appropriate parser
        if format_detected == "responses":
            async for event in _parse_responses_chunk(chunk, response_items):
                # Track if response.completed was received (signals stream completion for Responses API)
                if event.get("type") == "message_complete":
                    response_completed_received = True
                yield event
            # For Responses API, break after response.completed (message_complete) is received
            # The stream may not properly signal completion, so we break manually
            if response_completed_received and final_usage_data:
                break
        else:
            # For completions format, check if this is the final usage chunk (empty choices, has usage)
            # According to LiteLLM docs, final chunk has empty choices array and usage field
            is_final_usage_chunk = False
            if chunk_dict_for_usage_check and isinstance(
                chunk_dict_for_usage_check, dict
            ):
                choices_check = chunk_dict_for_usage_check.get("choices", [])
                usage_check = chunk_dict_for_usage_check.get("usage")
                # Final usage chunk: empty choices and non-null usage
                if (
                    not choices_check or len(choices_check) == 0
                ) and usage_check is not None:
                    is_final_usage_chunk = True

            # Skip parsing final usage chunk (it has no choices to parse, usage already captured and emitted above)
            # Usage = completion, so we already emitted message_complete when we found usage
            if not is_final_usage_chunk:
                # Parse chunk for progress events (text_delta, tool_call_delta, etc.)
                # These are all progress events, not completion events
                async for event in _parse_completions_chunk(
                    chunk, choices, get_choice_state, stable_tool_key
                ):
                    # Don't emit message_complete from parser - usage is the completion signal
                    # Only emit message_complete when we find usage (handled above)
                    if event.get("type") != "message_complete":
                        yield event

    # After streaming completes, emit final message_complete with usage if we found it in final chunk
    # This handles the case where usage chunk comes after all other chunks
    if final_usage_data and not usage_event_emitted:
        # Emit a message_complete event with usage
        # This will be merged/handled by the event processor
        yield {
            "type": "message_complete",
            "finish_reason": "stop",  # Default finish reason
            "usage": final_usage_data,
        }

    # Emit final completion events for responses format (only for items not already done)
    if format_detected == "responses":
        # Check for any incomplete items and emit completion events
        for item_id, item_state in response_items.items():
            if item_state.get("done"):
                continue  # Already emitted completion event
            if item_state.get("type") == "text" and item_state.get("started"):
                yield {
                    "type": "text_complete",
                    "text": item_state.get("buffer", ""),
                }
            elif item_state.get("type") == "function_call":
                call_id = item_state.get("call_id", item_id)
                yield {
                    "type": "tool_call_complete",
                    "tool_call_id": call_id,
                    "name": item_state.get("name"),
                    "arguments": item_state.get("arguments", ""),
                }


async def _parse_responses_chunk(
    chunk: Any,
    response_items: dict[str, dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    """Parse responses() API format chunks.

    Responses API uses events like:
    - response.output_item.added
    - response.output_text.delta (for text content)
    - response.function_call_arguments.delta (for tool call arguments)
    - response.output_item.done
    - response.completed (message complete)
    """
    chunk_type = None
    if hasattr(chunk, "type"):
        chunk_type = chunk.type
    elif isinstance(chunk, dict):
        chunk_type = chunk.get("type")

    if not chunk_type:
        return

    # Log unexpected event types for debugging (but don't fail)
    import logging

    logger = logging.getLogger(__name__)
    unexpected_types = {
        "response.output_item.delta",  # Old incorrect type
        "response.done",  # Old incorrect type
    }
    if chunk_type in unexpected_types:
        logger.warning(
            f"Received unexpected (possibly old) event type: {chunk_type}. "
            f"This may indicate a parsing issue."
        )

    # Handle response.output_item.added
    if chunk_type == "response.output_item.added":
        item = None
        item_id = None
        if hasattr(chunk, "item"):
            item = chunk.item
            item_id = getattr(item, "id", None) or getattr(chunk, "item_id", None)
        elif isinstance(chunk, dict):
            item = chunk.get("item", {})
            item_id = item.get("id") if isinstance(item, dict) else None
            if not item_id:
                item_id = chunk.get("item_id")

        if not item_id or not item:
            return

        item_type = None
        if hasattr(item, "type"):
            item_type = item.type
        elif isinstance(item, dict):
            item_type = item.get("type")

        if item_type == "text":
            response_items[item_id] = {"type": "text", "started": True, "buffer": ""}
            yield {"type": "text_start"}
        elif item_type == "function_call":
            function_name = None
            call_id = None
            if hasattr(item, "name"):
                function_name = item.name
            elif isinstance(item, dict):
                function_name = item.get("name")
            if hasattr(item, "call_id"):
                call_id = item.call_id
            elif isinstance(item, dict):
                call_id = item.get("call_id")

            response_items[item_id] = {
                "type": "function_call",
                "name": function_name,
                "arguments": "",
                "call_id": call_id,
            }
            yield {
                "type": "tool_call_start",
                "tool_call_id": item_id,
                "tool_name": function_name,
            }

    # Handle response.output_text.delta (for text content)
    elif chunk_type == "response.output_text.delta":
        item_id = None
        delta = None
        if hasattr(chunk, "item_id"):
            item_id = chunk.item_id
        elif isinstance(chunk, dict):
            item_id = chunk.get("item_id")

        if hasattr(chunk, "delta"):
            delta = chunk.delta
        elif isinstance(chunk, dict):
            delta = chunk.get("delta")

        if delta:
            # Find or create text item by item_id
            if item_id and item_id in response_items:
                item_state = response_items[item_id]
                if item_state.get("type") == "text":
                    item_state["buffer"] = item_state.get("buffer", "") + delta
                    yield {"type": "text_delta", "delta": delta}
            elif item_id:
                # Create new text item if not found (shouldn't happen, but handle gracefully)
                response_items[item_id] = {
                    "type": "text",
                    "started": True,
                    "buffer": delta,
                }
                yield {"type": "text_start"}
                yield {"type": "text_delta", "delta": delta}
            else:
                # No item_id, create a temporary item
                temp_id = "temp_text_0"
                if temp_id not in response_items:
                    response_items[temp_id] = {
                        "type": "text",
                        "started": True,
                        "buffer": "",
                    }
                    yield {"type": "text_start"}
                response_items[temp_id]["buffer"] += delta
                yield {"type": "text_delta", "delta": delta}

    # Handle response.function_call_arguments.delta (for tool call arguments)
    elif chunk_type == "response.function_call_arguments.delta":
        item_id = None
        delta = None
        if hasattr(chunk, "item_id"):
            item_id = chunk.item_id
        elif isinstance(chunk, dict):
            item_id = chunk.get("item_id")

        if hasattr(chunk, "delta"):
            delta = chunk.delta
        elif isinstance(chunk, dict):
            delta = chunk.get("delta")

        if item_id and item_id in response_items and delta:
            item_state = response_items[item_id]
            if item_state.get("type") == "function_call":
                item_state["arguments"] = item_state.get("arguments", "") + delta
                yield {
                    "type": "tool_call_delta",
                    "tool_call_id": item_id,
                    "delta": delta,
                    "tool_name": item_state.get("name"),
                }

    # Handle response.output_text.done (text item complete)
    elif chunk_type == "response.output_text.done":
        item_id = None
        text = None
        if hasattr(chunk, "item_id"):
            item_id = chunk.item_id
        elif isinstance(chunk, dict):
            item_id = chunk.get("item_id")

        if hasattr(chunk, "text"):
            text = chunk.text
        elif isinstance(chunk, dict):
            text = chunk.get("text")

        if item_id and item_id in response_items:
            item_state = response_items[item_id]
            if item_state.get("type") == "text" and not item_state.get("done"):
                # Use provided text or accumulated buffer
                final_text = text if text is not None else item_state.get("buffer", "")
                # Mark as done to prevent duplicate emission in cleanup loop
                item_state["done"] = True
                yield {
                    "type": "text_complete",
                    "text": final_text,
                }
                # Also yield the raw output item for Responses API conversation history
                yield {
                    "type": "output_item",
                    "item": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": final_text}],
                    },
                }

    # Handle response.function_call_arguments.done (function call complete)
    elif chunk_type == "response.function_call_arguments.done":
        item_id = None
        arguments = None
        if hasattr(chunk, "item_id"):
            item_id = chunk.item_id
        elif isinstance(chunk, dict):
            item_id = chunk.get("item_id")

        if hasattr(chunk, "arguments"):
            arguments = chunk.arguments
        elif isinstance(chunk, dict):
            arguments = chunk.get("arguments")

        if item_id and item_id in response_items:
            item_state = response_items[item_id]
            if item_state.get("type") == "function_call" and not item_state.get("done"):
                # Use provided arguments or accumulated arguments
                final_arguments = (
                    arguments
                    if arguments is not None
                    else item_state.get("arguments", "")
                )
                # Get the call_id from the item state (set during response.output_item.added)
                call_id = item_state.get("call_id", item_id)
                # Mark as done to prevent duplicate emission in cleanup loop
                item_state["done"] = True
                yield {
                    "type": "tool_call_complete",
                    "tool_call_id": call_id,  # Use actual call_id from model
                    "name": item_state.get("name"),
                    "arguments": final_arguments,
                }
                # Also yield the raw output item for Responses API conversation history
                yield {
                    "type": "output_item",
                    "item": {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": item_state.get("name"),
                        "arguments": final_arguments,
                    },
                }

    # Handle response.output_item.done (legacy/fallback)
    elif chunk_type == "response.output_item.done":
        item_id = None
        if hasattr(chunk, "item_id"):
            item_id = chunk.item_id
        elif isinstance(chunk, dict):
            item_id = chunk.get("item_id")

        if not item_id or item_id not in response_items:
            return

        item_state = response_items[item_id]
        if item_state.get("type") == "text":
            yield {
                "type": "text_complete",
                "text": item_state.get("buffer", ""),
            }
        elif item_state.get("type") == "function_call":
            yield {
                "type": "tool_call_complete",
                "tool_call_id": item_id,
                "name": item_state.get("name"),
                "arguments": item_state.get("arguments", ""),
            }

    # Handle response.completed (message complete)
    elif chunk_type == "response.completed":
        usage_data = None
        # ResponseCompletedEvent has usage nested in chunk.response.usage
        if hasattr(chunk, "response"):
            response_obj = chunk.response
            if hasattr(response_obj, "usage"):
                usage_obj = response_obj.usage
                if hasattr(usage_obj, "input_tokens"):
                    usage_data = {
                        "prompt_tokens": getattr(usage_obj, "input_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "output_tokens", 0),
                    }
                elif hasattr(usage_obj, "prompt_tokens"):
                    usage_data = {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    }
        elif isinstance(chunk, dict):
            response = chunk.get("response", {})
            if isinstance(response, dict):
                usage = response.get("usage")
                if isinstance(usage, dict):
                    usage_data = {
                        "prompt_tokens": usage.get(
                            "input_tokens", usage.get("prompt_tokens", 0)
                        ),
                        "completion_tokens": usage.get(
                            "output_tokens", usage.get("completion_tokens", 0)
                        ),
                    }
            # Fallback: check chunk.usage directly (for dict format)
            if not usage_data:
                usage = chunk.get("usage")
                if isinstance(usage, dict):
                    usage_data = {
                        "prompt_tokens": usage.get(
                            "input_tokens", usage.get("prompt_tokens", 0)
                        ),
                        "completion_tokens": usage.get(
                            "output_tokens", usage.get("completion_tokens", 0)
                        ),
                    }

        ev: dict[str, Any] = {
            "type": "message_complete",
            "finish_reason": "stop",
        }
        if usage_data:
            ev["usage"] = usage_data
        yield ev


async def _parse_completions_chunk(
    chunk: Any,
    choices: dict[int, ChoiceState],
    get_choice_state: Any,
    stable_tool_key: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Parse completions() API format chunks (original implementation)."""
    # Normalize chunk choices
    if hasattr(chunk, "choices"):
        chunk_choices = chunk.choices
    elif isinstance(chunk, dict):
        chunk_choices = chunk.get("choices", [])
    else:
        return

    for ch in chunk_choices:
        # index
        if hasattr(ch, "index"):
            i = ch.index
        elif isinstance(ch, dict):
            i = ch.get("index", 0)
        else:
            i = 0

        st = get_choice_state(i)

        # delta
        if hasattr(ch, "delta"):
            delta_raw = ch.delta
        elif isinstance(ch, dict):
            delta_raw = ch.get("delta", {}) or {}
        else:
            delta_raw = {}

        # Convert delta to dict if it's a Pydantic model
        if not isinstance(delta_raw, dict):
            if hasattr(delta_raw, "model_dump"):
                try:
                    delta = delta_raw.model_dump()
                except Exception:
                    delta = {}
            elif hasattr(delta_raw, "dict"):
                try:
                    delta = delta_raw.dict()
                except Exception:
                    delta = {}
            else:
                delta = {}
        else:
            delta = delta_raw

        # finish_reason
        if hasattr(ch, "finish_reason"):
            finish_reason = ch.finish_reason
        elif isinstance(ch, dict):
            finish_reason = ch.get("finish_reason")
        else:
            finish_reason = None

        # Check for tool_calls in choice object (not just delta) - they might be here when finish_reason is set
        choice_tool_calls = None
        if hasattr(ch, "tool_calls"):
            choice_tool_calls = ch.tool_calls
        elif isinstance(ch, dict):
            choice_tool_calls = ch.get("tool_calls")

        # Also check if tool_calls are in the accumulated choice state
        # When finish_reason is "tool_calls", the complete tool_calls might be in the choice state
        accumulated_tool_calls = None
        if hasattr(st, "tool_calls"):
            accumulated_tool_calls = st.tool_calls
        elif hasattr(st, "__dict__"):
            accumulated_tool_calls = getattr(st, "tool_calls", None)

        if not isinstance(delta, dict):
            delta = {}

        # assistant role
        if delta.get("role") == "assistant":
            yield {"type": "assistant_role", "choice_index": i}

        # -------- TEXT: start/delta
        content_piece = delta.get("content")
        if content_piece:
            if not st.text.started:
                st.text.started = True
                yield {"type": "text_start", "choice_index": i}
            st.text.buffer += content_piece
            yield {"type": "text_delta", "choice_index": i, "delta": content_piece}

        # -------- TOOLS: start/delta
        # Check both delta and choice object for tool_calls
        # When finish_reason is "tool_calls", tool_calls might be in the choice object, not delta
        tool_calls_delta = delta.get("tool_calls") or []
        if not tool_calls_delta and choice_tool_calls:
            tool_calls_delta = (
                choice_tool_calls if isinstance(choice_tool_calls, list) else []
            )

        # When finish_reason is "tool_calls", we should NOT process accumulated tool_calls as deltas
        # They've already been processed, and completion logic will emit tool_call_complete events
        # Only process tool_calls from delta/choice if they're actually new deltas
        # Skip accumulated tool_calls conversion when finish_reason is "tool_calls" - let completion logic handle it

        for tc in tool_calls_delta:
            if not isinstance(tc, dict):
                continue

            tool_index = tc.get("index", 0)
            if not isinstance(tool_index, int):
                tool_index = 0

            if tool_index not in st.tool_calls:
                st.tool_calls[tool_index] = ToolCallState()
                # stable id until/if provider gives real id
                tool_call_id = stable_tool_key(i, tool_index)
                yield {
                    "type": "tool_call_start",
                    "choice_index": i,
                    "tool_index": tool_index,
                    "tool_call_id": tool_call_id,
                }

            tc_state = st.tool_calls[tool_index]

            # If provider gives an ID, store it
            if tc.get("id"):
                tc_state.id = tc["id"]
            if tc.get("type"):
                tc_state.type = tc["type"]

            fn = tc.get("function") or {}
            if isinstance(fn, dict) and fn.get("name"):
                tc_state.function.name = fn["name"]

            args_piece = fn.get("arguments") if isinstance(fn, dict) else None
            if args_piece:
                tc_state.function.arguments += args_piece
                yield {
                    "type": "tool_call_delta",
                    "choice_index": i,
                    "tool_index": tool_index,
                    "tool_call_id": (tc_state.id or stable_tool_key(i, tool_index)),
                    "delta": args_piece,
                    "tool_name": tc_state.function.name,
                }

        # -------- COMPLETION
        if finish_reason is not None:
            st.finish_reason = finish_reason

            # usage extraction
            usage_data: dict[str, Any] | None = None
            # Try to get usage from model_dump/dict first (for Pydantic models)
            chunk_dict_for_usage = None
            if hasattr(chunk, "model_dump"):
                try:
                    chunk_dict_for_usage = chunk.model_dump()
                except:
                    pass
            elif hasattr(chunk, "dict"):
                try:
                    chunk_dict_for_usage = chunk.dict()
                except:
                    pass

            if (
                chunk_dict_for_usage
                and isinstance(chunk_dict_for_usage, dict)
                and "usage" in chunk_dict_for_usage
            ):
                usage_obj = chunk_dict_for_usage["usage"]
                if isinstance(usage_obj, dict):
                    usage_data = {
                        "prompt_tokens": usage_obj.get("prompt_tokens", 0),
                        "completion_tokens": usage_obj.get("completion_tokens", 0),
                    }
                elif hasattr(usage_obj, "prompt_tokens"):
                    usage_data = {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    }
            elif hasattr(chunk, "usage"):
                usage_obj = chunk.usage
                if hasattr(usage_obj, "prompt_tokens"):
                    usage_data = {
                        "prompt_tokens": usage_obj.prompt_tokens,
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    }
            elif isinstance(chunk, dict):
                usage_data = chunk.get("usage")

            # Don't emit message_complete here - usage is the completion signal
            # message_complete will be emitted when we find usage (handled in main loop)
            # This parser only emits progress events (text_delta, tool_call_delta, etc.)

            # tool_call_complete for each
            if st.tool_calls:
                for tool_index, tc_state in st.tool_calls.items():
                    yield {
                        "type": "tool_call_complete",
                        "choice_index": i,
                        "tool_index": tool_index,
                        "tool_call_id": (tc_state.id or stable_tool_key(i, tool_index)),
                        "id": tc_state.id,  # raw provider id (may be None)
                        "name": tc_state.function.name,
                        "arguments": tc_state.function.arguments,
                    }

            # text_complete
            if st.text.started:
                yield {
                    "type": "text_complete",
                    "choice_index": i,
                    "text": st.text.buffer,
                }
