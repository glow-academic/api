"""Generation infrastructure types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


def _default_output_modalities() -> set[str]:
    return {"text", "call"}


def _default_input_modalities() -> set[str]:
    return {"text"}


@dataclass
class AgentDispatch:
    """Everything needed to execute one agent's LLM loop."""

    agent_id: UUID
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    llm_config: dict[str, Any]
    resource_types: list[str]
    metadata: dict[str, Any] | None = None
    developer_instruction_templates: list[str] | None = None
    # Modality pair used by the unified dispatcher. See execute.py for the
    # (input, output) → executor rules. Defaults describe a text agentic loop
    # with tool calls enabled ("call" is load-bearing — it signals tool use).
    input_modalities: set[str] = field(default_factory=_default_input_modalities)
    output_modalities: set[str] = field(default_factory=_default_output_modalities)
    # Audio / realtime passthrough
    chat_id: str | None = None
    conversation_id: str | None = None
    audios_id: str | None = None
    # Media passthrough (pre-uploaded assets or AI output)
    file_path: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    upload_id: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True)
class ReplayTapeEntry:
    """One historical tool call in a benchmark replay tape.

    During a trace-driven benchmark run, the LLM dispatches against a
    pre-loaded tape of historical tool outputs. When the LLM calls
    tool X, the dispatch loop returns the next unconsumed tape entry
    matching that tool_id — substituting the historical raw_output
    bytes verbatim, regardless of what args the LLM passed. The impl
    is never invoked, no rows are written anywhere, no soft_calls
    ledger pending entries pollute the user's UI. Pure tape playback.

    Tape consumption is per-tool: calls to tool X consume entries
    matching tool_id=X in arrival order. Other tools' entries are not
    affected.
    """

    tool_id: UUID
    operation_key: UUID
    historical_call_id: UUID
    raw_output: Any  # parsed JSON, typically a dict


@dataclass
class PrepareGenerationResult:
    """Full preparation result — ready to execute on a moment's notice."""

    run_id: UUID
    group_id: UUID
    session_id: UUID
    profile_id: UUID
    profiles_id: UUID
    artifact_type: str
    dispatches: list[AgentDispatch] = field(default_factory=list)
    test_id: UUID | None = None
    resource_types: list[str] = field(default_factory=list)
    # Set when the run was prepared from a benchmark trace (trace_id
    # → historical_run_id). The execute loop reads this to substitute
    # tool outputs from the tape instead of running impls. None for
    # non-replay runs (the standard path).
    replay_tape: list[ReplayTapeEntry] | None = None
