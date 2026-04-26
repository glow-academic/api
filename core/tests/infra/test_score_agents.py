"""Tests for ``score_agents`` — the canonical modality-first selection.

Pure Python, no I/O, no fixtures from the live graph. Verifies the
rule set independently of how ResolvedAgent instances are populated by
``_resolve_tool_graph_impl``.

Rules under test (see tool_graph.score_agents):
  1. input-modality filter  — ``request ⊆ agent.input_modalities``
  2. output-modality filter — ``request ⊆ agent.output_modalities``
  3. tool filter            — only when operations requested; (artifact, op)
                              pairs must all be in ``agent.tool_targets``
  4. least-privilege rank   — ascending
                              (len(out), len(in), len(tools), str(agent_id))
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.infra.tool_graph import ResolvedAgent, score_agents


def _agent(
    name: str,
    *,
    in_mods: set[str],
    out_mods: set[str],
    tool_targets: set[tuple[str, str]] | None = None,
    agent_id: UUID | None = None,
    system_id: UUID | None = None,
) -> ResolvedAgent:
    return ResolvedAgent(
        agent_id=agent_id or uuid4(),
        system_id=system_id or uuid4(),
        model_id=uuid4(),
        input_modalities=frozenset(in_mods),
        output_modalities=frozenset(out_mods),
        tool_targets=frozenset(tool_targets or set()),
    )


# Roster — mirrors actual seed
def _roster() -> dict[str, ResolvedAgent]:
    sys_id = uuid4()
    return {
        "Attempt": _agent(
            "Attempt",
            in_mods={"text", "call"},
            out_mods={"text", "call"},
            tool_targets={
                ("attempt", "chat_message"),
                ("attempt", "get"),
                ("attempt", "chat_grade"),
            },
            system_id=sys_id,
        ),
        "Attempt Realtime": _agent(
            "Attempt Realtime",
            in_mods={"text", "audio", "call", "image"},
            out_mods={"text", "audio", "call"},
            tool_targets={
                ("attempt", "chat_message"),
                ("attempt", "get"),
            },
            system_id=sys_id,
        ),
        "Transcribe": _agent(
            "Transcribe",
            in_mods={"audio"},
            out_mods={"text"},
            tool_targets=set(),
            system_id=sys_id,
        ),
        "Audio": _agent(
            "Audio",
            in_mods={"text"},
            out_mods={"audio"},
            tool_targets=set(),
            system_id=sys_id,
        ),
        "Test Grade": _agent(
            "Test Grade",
            in_mods={"text", "audio", "call", "image"},
            out_mods={"text"},
            tool_targets={("test", "chat_grade")},
            system_id=sys_id,
        ),
        "Persona Gemini": _agent(
            "Persona Gemini",
            in_mods={"text", "audio", "call", "image", "video"},
            out_mods={"text", "call", "image"},
            tool_targets={("persona", "create"), ("persona", "update")},
            system_id=sys_id,
        ),
    }


def test_stt_picks_transcribe_via_least_privilege():
    """STT (audio→text, no ops) picks Transcribe over Realtime/Test Grade."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"audio"},
        request_output_modalities={"text"},
        artifact_type="attempt",
    )
    assert result, "expected at least one candidate"
    assert result[0].agent_id == roster["Transcribe"].agent_id


def test_tts_picks_audio_over_realtime():
    """TTS (text→audio, no ops) picks Audio over Realtime."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"text"},
        request_output_modalities={"audio"},
        artifact_type="attempt",
    )
    assert result
    assert result[0].agent_id == roster["Audio"].agent_id


def test_text_chat_picks_attempt_over_realtime():
    """Text chat with chat_message op picks narrower Attempt agent."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"text"},
        request_output_modalities={"text"},
        artifact_type="attempt",
        operations=["chat_message"],
    )
    assert result
    assert result[0].agent_id == roster["Attempt"].agent_id


def test_realtime_voice_only_realtime_qualifies():
    """Audio in + {audio, call, text} out + ops → only Attempt Realtime."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"audio"},
        request_output_modalities={"audio", "call", "text"},
        artifact_type="attempt",
        operations=["chat_message", "get"],
    )
    assert len(result) == 1
    assert result[0].agent_id == roster["Attempt Realtime"].agent_id


def test_test_grade_op_isolates_grader():
    """Audio in + text out + (test, chat_grade) → Test Grade only."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"audio"},
        request_output_modalities={"text"},
        artifact_type="test",
        operations=["chat_grade"],
    )
    assert len(result) == 1
    assert result[0].agent_id == roster["Test Grade"].agent_id


def test_persona_create_with_image_input():
    """Image+text in + text out + (persona, create) → Persona Gemini."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"image", "text"},
        request_output_modalities={"text"},
        artifact_type="persona",
        operations=["create"],
    )
    assert len(result) == 1
    assert result[0].agent_id == roster["Persona Gemini"].agent_id


def test_no_video_producer_returns_empty():
    """If no agent produces the requested output, candidate list is empty."""
    roster = _roster()
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities={"text"},
        request_output_modalities={"video"},
        artifact_type="attempt",
    )
    assert result == []


def test_no_implicit_text_default():
    """Empty request modalities should not implicitly include any default."""
    roster = _roster()
    # Caller passes no input modalities at all — every agent's input set
    # is a superset of ∅, so every agent passes input filter. Output
    # filter of {text} narrows it.
    result = score_agents(
        agents=list(roster.values()),
        request_input_modalities=set(),
        request_output_modalities={"text"},
        artifact_type="attempt",
    )
    # Transcribe still wins: smallest output set ({text}=1) and smallest
    # input set ({audio}=1) among the {text}-output agents.
    assert result[0].agent_id == roster["Transcribe"].agent_id


def test_least_privilege_tool_count_tiebreak():
    """When two agents tie on output and input size, fewer tools wins."""
    sys_id = uuid4()
    a_few_tools = _agent(
        "FewTools",
        in_mods={"text"},
        out_mods={"text"},
        tool_targets={("x", "op1")},
        system_id=sys_id,
    )
    a_many_tools = _agent(
        "ManyTools",
        in_mods={"text"},
        out_mods={"text"},
        tool_targets={("x", "op1"), ("x", "op2"), ("x", "op3")},
        system_id=sys_id,
    )
    result = score_agents(
        agents=[a_many_tools, a_few_tools],  # order-independent
        request_input_modalities={"text"},
        request_output_modalities={"text"},
        artifact_type="x",
        operations=["op1"],
    )
    assert result[0].agent_id == a_few_tools.agent_id
