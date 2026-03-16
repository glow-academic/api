"""Pure data types for the generation preparation pipeline.

These are intermediate representations that flow between pure functions
and thin I/O handlers. No I/O, no imports of globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class MessageSpec:
    """A single message to be sent to the LLM and optionally persisted.

    Attributes:
        role: "system" | "developer" | "user"
        content: What goes to the LLM (str or list[dict] for multipart media).
        raw_text: Plain text for DB persistence (always str).
        persist: Whether to write to DB via persist_run_message.
                 False for extra_messages (chat history) which are pre-persisted.
    """

    role: str
    content: str | list[dict[str, Any]]
    raw_text: str
    persist: bool = True


@dataclass(frozen=True)
class LLMConfig:
    """Resolved model/provider configuration for one agent."""

    model: str
    api_key: str
    base_url: str
    temperature: float
    reasoning: str | None
    provider: str
    voice: str | None
    quality: str | None


@dataclass(frozen=True)
class AgentDispatch:
    """Everything needed to dispatch one agent to the token factory."""

    agent_id: UUID
    resource_types: list[str]
    entry_types: list[str]
    messages: list[MessageSpec]
    llm_config: LLMConfig
    scoped_tools: list[dict[str, Any]]
    metadata: dict[str, Any]
    developer_instruction_templates: list[str] | None = None

    @property
    def messages_for_llm(self) -> list[dict[str, Any]]:
        """Messages formatted for the LLM (content may be multipart)."""
        return [{"role": m.role, "content": m.content} for m in self.messages]


@dataclass(frozen=True)
class PreparedGeneration:
    """Complete output of the preparation pipeline — ready for I/O."""

    artifact_type: str
    run_id: UUID
    group_id: UUID
    session_id: UUID
    profile_id: UUID
    artifact_id: UUID | None
    draft_id: UUID | None
    sid: str
    save: bool
    modality: str
    resource_types: list[str]
    agent_ids_for_run: list[UUID]
    dispatches: list[AgentDispatch]
    all_artifact_types: list[str] = field(default_factory=list)

    @property
    def num_agents(self) -> int:
        return len(self.dispatches)
