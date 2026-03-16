"""Direct tests for litellm stream normalization."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from app.infra.artifacts.stream_litellm_events import stream_litellm_events


async def _iter_chunks(chunks: list[object]) -> AsyncIterator[object]:
    for chunk in chunks:
        yield chunk


async def _collect_events(chunks: list[object]) -> list[dict[str, object]]:
    return [event async for event in stream_litellm_events(_iter_chunks(chunks))]


@pytest.mark.asyncio
async def test_completions_stream_normalizes_text_tool_and_usage_once() -> None:
    chunks = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Hello "},
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search_docs",
                                    "arguments": '{"query":"docs"}',
                                },
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
            },
        },
    ]

    events = await _collect_events(chunks)

    assert events == [
        {"type": "assistant_role", "choice_index": 0},
        {"type": "text_start", "choice_index": 0},
        {"type": "text_delta", "choice_index": 0, "delta": "Hello "},
        {
            "type": "tool_call_start",
            "choice_index": 0,
            "tool_index": 0,
            "tool_call_id": "choice_0_tool_0",
        },
        {
            "type": "tool_call_delta",
            "choice_index": 0,
            "tool_index": 0,
            "tool_call_id": "call_1",
            "delta": '{"query":"docs"}',
            "tool_name": "search_docs",
        },
        {
            "type": "tool_call_complete",
            "choice_index": 0,
            "tool_index": 0,
            "tool_call_id": "call_1",
            "id": "call_1",
            "name": "search_docs",
            "arguments": '{"query":"docs"}',
        },
        {
            "type": "text_complete",
            "choice_index": 0,
            "text": "Hello ",
        },
        {
            "type": "message_complete",
            "choice_index": 0,
            "finish_reason": "tool_calls",
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
            },
        },
    ]


@pytest.mark.asyncio
async def test_responses_stream_normalizes_output_items_and_completion() -> None:
    chunks = [
        {
            "type": "response.output_item.added",
            "item": {
                "id": "text_1",
                "type": "text",
            },
        },
        {
            "type": "response.output_text.delta",
            "item_id": "text_1",
            "delta": "Hello from responses",
        },
        {
            "type": "response.output_text.done",
            "item_id": "text_1",
            "text": "Hello from responses",
        },
        {
            "type": "response.output_item.added",
            "item": {
                "id": "tool_item_1",
                "type": "function_call",
                "name": "lookup_user",
                "call_id": "call_resp_1",
            },
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "tool_item_1",
            "delta": '{"user_id":"42"}',
        },
        {
            "type": "response.function_call_arguments.done",
            "item_id": "tool_item_1",
            "arguments": '{"user_id":"42"}',
        },
        {
            "type": "response.completed",
            "response": {
                "usage": {
                    "input_tokens": 9,
                    "output_tokens": 4,
                }
            },
        },
    ]

    events = await _collect_events(chunks)

    assert events == [
        {"type": "text_start"},
        {"type": "text_delta", "delta": "Hello from responses"},
        {
            "type": "text_complete",
            "text": "Hello from responses",
        },
        {
            "type": "output_item",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Hello from responses",
                    }
                ],
            },
        },
        {
            "type": "tool_call_start",
            "tool_call_id": "tool_item_1",
            "tool_name": "lookup_user",
        },
        {
            "type": "tool_call_delta",
            "tool_call_id": "tool_item_1",
            "delta": '{"user_id":"42"}',
            "tool_name": "lookup_user",
        },
        {
            "type": "tool_call_complete",
            "tool_call_id": "call_resp_1",
            "name": "lookup_user",
            "arguments": '{"user_id":"42"}',
        },
        {
            "type": "output_item",
            "item": {
                "type": "function_call",
                "call_id": "call_resp_1",
                "name": "lookup_user",
                "arguments": '{"user_id":"42"}',
            },
        },
        {
            "type": "message_complete",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 9,
                "completion_tokens": 4,
            },
        },
    ]


@pytest.mark.asyncio
async def test_model_like_chunks_with_usage_emit_single_completion_event() -> None:
    chunks = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Hi"},
                    "finish_reason": "stop",
                }
            ]
        },
        SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
            model_dump=lambda: {
                "choices": [],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                },
            },
        ),
    ]

    events = await _collect_events(chunks)
    message_complete_events = [
        event for event in events if event["type"] == "message_complete"
    ]

    assert len(message_complete_events) == 1
    assert message_complete_events[0]["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
    }
