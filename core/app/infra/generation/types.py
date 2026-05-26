"""Generation infrastructure types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.infra.websocket.generation_types import EvalSetup


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
    # ``True`` when the run was prepared from a benchmark trace
    # (``trace_id`` set). Threaded into ``InfraContext.eval`` so every
    # ``create_soft_call`` written during the run is tagged ``eval=true``
    # and stays out of normal UI listings. Tool dispatch is live with
    # ``soft=True`` — no replay tape, real impls run against current
    # state, writes stage dormant.
    eval: bool = False
    # Multi-candidate eval scaffold — one ``InvocationSlot`` per
    # rubric-bearing agent dispatched on this run. Rides on the
    # artifact's generate response so audit emits it as a first-class
    # field on ``<artifact>.generate.completed``. ``None`` for runs
    # with no rubric-bearing agent.
    eval_setup: EvalSetup | None = None
    # Caller-supplied label + caller-supplied descriptive text. Media
    # dispatches forward these onto the ``{m}s_resource`` row so
    # generated assets get human-readable names and descriptions instead
    # of UUID fallbacks. ``title`` mirrors ``payload.title``;
    # ``description`` falls back to the joined ``payload.instructions``
    # so the LLM doesn't have to repeat itself.
    title: str | None = None
    description: str | None = None
