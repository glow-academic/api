"""Direct tests for litellm stream normalization."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from types import SimpleNamespace

import pytest

from app.infra.artifacts.stream_litellm_events import stream_litellm_events


async def _iter_chunks(chunks: Sequence[object]) -> AsyncIterator[object]:
    for chunk in chunks:
        yield chunk


async def _collect_events(chunks: Sequence[object]) -> list[dict[str, object]]:
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
                "id": "text_1",
                "status": "completed",
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
            "responses_call_id": "call_resp_1",
        },
        {
            "type": "tool_call_delta",
            "tool_call_id": "tool_item_1",
            "delta": '{"user_id":"42"}',
            "tool_name": "lookup_user",
        },
        {
            "type": "tool_call_complete",
            "tool_call_id": "tool_item_1",
            "name": "lookup_user",
            "arguments": '{"user_id": "42"}',
        },
        {
            "type": "output_item",
            "item": {
                "type": "function_call",
                "call_id": "call_resp_1",
                "name": "lookup_user",
                "arguments": '{"user_id": "42"}',
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


@pytest.mark.asyncio
async def test_completions_stream_reads_choice_level_tool_calls_and_usage_object() -> None:
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    index=0,
                    delta={},
                    tool_calls=[
                        {
                            "index": "bad-index",
                            "function": {
                                "name": "search_docs",
                                "arguments": '{"query":"docs"}',
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
        )
    ]

    events = await _collect_events(chunks)

    assert any(
        event == {
            "type": "tool_call_start",
            "choice_index": 0,
            "tool_index": 0,
            "tool_call_id": "choice_0_tool_0",
        }
        for event in events
    )
    assert any(
        event == {
            "type": "tool_call_delta",
            "choice_index": 0,
            "tool_index": 0,
            "tool_call_id": "choice_0_tool_0",
            "delta": '{"query":"docs"}',
            "tool_name": "search_docs",
        }
        for event in events
    )
    assert any(
        event == {
            "type": "tool_call_complete",
            "choice_index": 0,
            "tool_index": 0,
            "tool_call_id": "choice_0_tool_0",
            "id": None,
            "name": "search_docs",
            "arguments": '{"query":"docs"}',
        }
        for event in events
    )

    message_complete_events = [
        event for event in events if event["type"] == "message_complete"
    ]
    assert message_complete_events == [
        {
            "type": "message_complete",
            "choice_index": 0,
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 3,
            },
        }
    ]


@pytest.mark.asyncio
async def test_responses_stream_cleans_up_orphaned_text_delta() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_text.delta",
                "delta": "orphaned text",
            }
        ]
    )

    assert events == [
        {"type": "text_start"},
        {"type": "text_delta", "delta": "orphaned text"},
        {"type": "text_complete", "text": "orphaned text"},
    ]


@pytest.mark.asyncio
async def test_responses_stream_function_call_done_falls_back_to_item_id() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "tool_item_1",
                    "type": "function_call",
                    "name": "lookup_user",
                },
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "tool_item_1",
                "arguments": '{"user_id":"42"}',
            },
        ]
    )

    assert events == [
        {
            "type": "tool_call_start",
            "tool_call_id": "tool_item_1",
            "tool_name": "lookup_user",
            "responses_call_id": None,
        },
        {
            "type": "tool_call_complete",
            "tool_call_id": "tool_item_1",
            "name": "lookup_user",
            "arguments": '{"user_id": "42"}',
        },
        {
            "type": "output_item",
            "item": {
                "type": "function_call",
                "call_id": "tool_item_1",
                "name": "lookup_user",
                "arguments": '{"user_id": "42"}',
            },
        },
    ]


@pytest.mark.asyncio
async def test_responses_stream_cleanup_falls_back_to_item_id_for_incomplete_tool_call() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "tool_item_1",
                    "type": "function_call",
                    "name": "lookup_user",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "tool_item_1",
                "delta": '{"user_id":"42"}',
            },
        ]
    )

    assert events == [
        {
            "type": "tool_call_start",
            "tool_call_id": "tool_item_1",
            "tool_name": "lookup_user",
            "responses_call_id": None,
        },
        {
            "type": "tool_call_delta",
            "tool_call_id": "tool_item_1",
            "delta": '{"user_id":"42"}',
            "tool_name": "lookup_user",
        },
        {
            "type": "tool_call_complete",
            "tool_call_id": "tool_item_1",
            "name": "lookup_user",
            "arguments": '{"user_id":"42"}',
        },
    ]


@pytest.mark.asyncio
async def test_responses_stream_supports_object_style_chunks() -> None:
    chunks = [
        SimpleNamespace(
            type="response.output_item.added",
            item=SimpleNamespace(id="text_1", type="text"),
        ),
        SimpleNamespace(
            type="response.output_text.delta",
            item_id="text_1",
            delta="Hello from object chunks",
        ),
        SimpleNamespace(
            type="response.output_text.done",
            item_id="text_1",
            text="Hello from object chunks",
        ),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(
                usage=SimpleNamespace(input_tokens=2, output_tokens=1)
            ),
        ),
    ]

    events = await _collect_events(chunks)

    assert events == [
        {"type": "text_start"},
        {"type": "text_delta", "delta": "Hello from object chunks"},
        {
            "type": "text_complete",
            "text": "Hello from object chunks",
        },
        {
            "type": "output_item",
            "item": {
                "type": "message",
                "id": "text_1",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Hello from object chunks",
                    }
                ],
            },
        },
        {
            "type": "message_complete",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
            },
        },
    ]


@pytest.mark.asyncio
async def test_responses_stream_top_level_usage_emits_single_completion_event() -> None:
    events = await _collect_events(
        [
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
                "delta": "Hello from top-level usage",
            },
            {
                "type": "response.completed",
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 2,
                },
            },
        ]
    )

    message_complete_events = [
        event for event in events if event["type"] == "message_complete"
    ]

    assert message_complete_events == [
        {
            "type": "message_complete",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 2,
            },
        }
    ]


@pytest.mark.asyncio
async def test_responses_stream_uses_chunk_level_item_id_for_added_items() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_item.added",
                "item_id": "text_1",
                "item": {
                    "type": "text",
                },
            },
            {
                "type": "response.output_text.delta",
                "item_id": "text_1",
                "delta": "chunk level id",
            },
        ]
    )

    assert events == [
        {"type": "text_start"},
        {"type": "text_delta", "delta": "chunk level id"},
        {"type": "text_complete", "text": "chunk level id"},
    ]


@pytest.mark.asyncio
async def test_responses_stream_creates_missing_text_item_from_delta_item_id() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_text.delta",
                "item_id": "text_1",
                "delta": "late text",
            }
        ]
    )

    assert events == [
        {"type": "text_start"},
        {"type": "text_delta", "delta": "late text"},
        {"type": "text_complete", "text": "late text"},
    ]


@pytest.mark.asyncio
async def test_completions_stream_reads_direct_usage_dict_and_finish_reason() -> None:
    events = await _collect_events(
        [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "Hi"},
                        "finish_reason": "length",
                    }
                ]
            },
            SimpleNamespace(
                usage={"input_tokens": 4, "output_tokens": 2},
            ),
        ]
    )

    message_complete_events = [
        event for event in events if event["type"] == "message_complete"
    ]

    assert message_complete_events == [
        {
            "type": "message_complete",
            "choice_index": 0,
            "finish_reason": "length",
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": 2,
            },
        }
    ]


@pytest.mark.asyncio
async def test_responses_stream_legacy_output_item_done_completes_text() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "text_legacy",
                    "type": "text",
                },
            },
            {
                "type": "response.output_text.delta",
                "item_id": "text_legacy",
                "delta": "legacy text",
            },
            {
                "type": "response.output_item.done",
                "item_id": "text_legacy",
            },
        ]
    )

    assert events == [
        {"type": "text_start"},
        {"type": "text_delta", "delta": "legacy text"},
        {"type": "text_complete", "text": "legacy text"},
    ]


@pytest.mark.asyncio
async def test_responses_stream_legacy_output_item_done_completes_function_call() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "tool_legacy",
                    "type": "function_call",
                    "name": "lookup_user",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "tool_legacy",
                "delta": '{"user_id":"42"}',
            },
            {
                "type": "response.output_item.done",
                "item_id": "tool_legacy",
            },
        ]
    )

    assert events == [
        {
            "type": "tool_call_start",
            "tool_call_id": "tool_legacy",
            "tool_name": "lookup_user",
            "responses_call_id": None,
        },
        {
            "type": "tool_call_delta",
            "tool_call_id": "tool_legacy",
            "delta": '{"user_id":"42"}',
            "tool_name": "lookup_user",
        },
        {
            "type": "tool_call_complete",
            "tool_call_id": "tool_legacy",
            "name": "lookup_user",
            "arguments": '{"user_id":"42"}',
        },
    ]


@pytest.mark.asyncio
async def test_responses_stream_legacy_output_item_done_prefers_call_id() -> None:
    events = await _collect_events(
        [
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "tool_legacy",
                    "type": "function_call",
                    "name": "lookup_user",
                    "call_id": "call_legacy",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "tool_legacy",
                "delta": '{"user_id":"42"}',
            },
            {
                "type": "response.output_item.done",
                "item_id": "tool_legacy",
            },
        ]
    )

    assert events == [
        {
            "type": "tool_call_start",
            "tool_call_id": "tool_legacy",
            "tool_name": "lookup_user",
            "responses_call_id": "call_legacy",
        },
        {
            "type": "tool_call_delta",
            "tool_call_id": "tool_legacy",
            "delta": '{"user_id":"42"}',
            "tool_name": "lookup_user",
        },
        {
            "type": "tool_call_complete",
            "tool_call_id": "call_legacy",
            "name": "lookup_user",
            "arguments": '{"user_id":"42"}',
        },
    ]


@pytest.mark.asyncio
async def test_responses_stream_warns_for_legacy_event_types(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        events = await _collect_events([{"type": "response.done"}])

    assert events == []
    assert "Received unexpected (possibly old) event type" in caplog.text


@pytest.mark.asyncio
async def test_completions_stream_uses_dict_backed_chunks_and_deltas() -> None:
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    index=0,
                    delta=SimpleNamespace(
                        dict=lambda: {
                            "role": "assistant",
                            "content": "Hello from dict fallback",
                        }
                    ),
                    finish_reason="stop",
                )
            ],
            dict=lambda: {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": "Hello from dict fallback",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                },
            },
        )
    ]

    events = await _collect_events(chunks)

    assert events == [
        {
            "type": "message_complete",
            "choice_index": 0,
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
            },
        },
        {"type": "assistant_role", "choice_index": 0},
        {"type": "text_start", "choice_index": 0},
        {
            "type": "text_delta",
            "choice_index": 0,
            "delta": "Hello from dict fallback",
        },
        {
            "type": "text_complete",
            "choice_index": 0,
            "text": "Hello from dict fallback",
        },
    ]
