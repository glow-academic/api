"""render_history must emit one ``role:tool`` result per tool_call_id (G4).

The Chat Completions / Responses contract requires EXACTLY one ``tool`` message
for every id in an assistant message's ``tool_calls`` array. A history row that
carries N>1 calls used to emit a single tool result bound only to the LAST id,
leaving the other ids unanswered → the next provider turn 400s. This is a pure
rendering concern, so no DB / Redis — just the data-shape contract.
"""

from __future__ import annotations

from uuid import uuid4

from app.infra.generation.chat_history import HistoryMessage, HistoryToolCall
from app.infra.generation.render_history import render_history_for_dispatch


def _tool(tid, name):
    return {"id": str(tid), "name": name}


def test_multi_tool_call_row_emits_one_result_per_call_id():
    """A 2-call assistant row → 2 tool_call entries AND 2 matching results."""
    tid_a, tid_b = uuid4(), uuid4()
    call_a, call_b = uuid4(), uuid4()
    history = [
        HistoryMessage(
            role="assistant",
            text="rendered combined result",
            tool_calls=[
                HistoryToolCall(call_id=call_a, tool_id=tid_a, arguments={"x": 1}),
                HistoryToolCall(call_id=call_b, tool_id=tid_b, arguments={"y": 2}),
            ],
        ),
    ]

    out = render_history_for_dispatch(
        history,
        input_modalities={"text", "call"},
        scoped_tools=[_tool(tid_a, "tool_a"), _tool(tid_b, "tool_b")],
    )

    assistant_msgs = [m for m in out if m["role"] == "assistant"]
    tool_msgs = [m for m in out if m["role"] == "tool"]

    # One assistant message advertising BOTH calls.
    assert len(assistant_msgs) == 1
    advertised_ids = {tc["id"] for tc in assistant_msgs[0]["tool_calls"]}
    assert advertised_ids == {str(call_a), str(call_b)}

    # Every advertised id has its own tool result — no orphans (the 400 cause).
    assert len(tool_msgs) == 2
    answered_ids = {m["tool_call_id"] for m in tool_msgs}
    assert answered_ids == advertised_ids

    # Each tool result carries non-empty content (the API rejects null/missing).
    assert all(isinstance(m["content"], str) and m["content"] for m in tool_msgs)
    # The full rendered body lands on the first call.
    first = next(m for m in tool_msgs if m["tool_call_id"] == str(call_a))
    assert first["content"] == "rendered combined result"


def test_single_tool_call_row_still_one_result():
    """The common single-call path is unchanged: 1 call → 1 result."""
    tid, call = uuid4(), uuid4()
    history = [
        HistoryMessage(
            role="assistant",
            text="the result",
            tool_calls=[HistoryToolCall(call_id=call, tool_id=tid, arguments={})],
        ),
    ]
    out = render_history_for_dispatch(
        history, input_modalities={"text", "call"}, scoped_tools=[_tool(tid, "t")]
    )
    tool_msgs = [m for m in out if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == str(call)
    assert tool_msgs[0]["content"] == "the result"


def test_tool_call_row_without_call_modality_falls_back_to_text():
    """An agent without ``call`` input modality still gets plain-text history,
    never an orphaned structured call (no tool_calls payload at all)."""
    tid, call = uuid4(), uuid4()
    history = [
        HistoryMessage(
            role="assistant",
            text="what happened",
            tool_calls=[HistoryToolCall(call_id=call, tool_id=tid, arguments={})],
        ),
    ]
    out = render_history_for_dispatch(
        history, input_modalities={"text"}, scoped_tools=[_tool(tid, "t")]
    )
    assert all("tool_calls" not in m for m in out)
    assert all(m["role"] != "tool" for m in out)
    assert out == [{"role": "assistant", "content": "what happened"}]
