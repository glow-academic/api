"""Pydantic models for generation-domain internal bus emits.

Each model represents a dict payload passed to ``internal_sio.emit()``.
Construct the model, then call ``.model_dump(mode="json")``
before sending via internal_sio.emit(..., model.model_dump(mode="json")).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GenerationProgressData(BaseModel):
    type: str = "progress"
    sid: str
    artifact_type: str
    group_id: str
    run_id: str
    completed_resources: int
    total_resources: int
    percentage: int
    last_completed_resource: str


class GenerationSavedData(BaseModel):
    type: str = "saved"
    sid: str
    artifact_type: str
    group_id: str
    run_id: str
    artifact_id: str | None = None


class GenerationCompleteData(BaseModel):
    type: str = "complete"
    sid: str
    artifact_type: str
    group_id: str
    run_id: str
    success: bool
    message: str
    artifact_id: str | None = None
    resource_actions: dict[str, Any] | None = None


class GenerationErrorData(BaseModel):
    type: str = "error"
    sid: str
    artifact_type: str
    group_id: str | None = None
    resource_type: str | None = None
    resource_types: list[str] | None = None
    resource_id: str | None = None
    run_id: str | None = None
    success: bool = False
    message: str


class GenerationStartedData(BaseModel):
    sid: str
    artifact_type: str
    group_id: str
    run_id: str
    resource_types: list[str]


class GenerationStartedEvent(BaseModel):
    """Client-facing payload for server/generate/started.py."""

    artifact_type: str
    group_id: str
    run_id: str
    resource_types: list[str]


# ═══════════════════════════════════════════════════════════════════════════
# Generate gate types — moved from routes/v5/socket/ to avoid import chain
# ═══════════════════════════════════════════════════════════════════════════


class GenerateErrorApiRequest(BaseModel):
    """Payload for generate_*_error events (internal server-to-server).

    Used for internal error propagation with socket ID for routing.
    """

    sid: str
    error_message: str
    artifact_type: str | None = None
    group_id: str | None = None
    resource_type: str | None = None
    resource_types: list[str] | None = None
    resource_id: str | None = None


from typing import Literal

from pydantic import model_validator

ArtifactOperation = Literal[
    "get", "list", "duplicate", "delete", "draft", "save", "docs", "export", "refresh"
]
ResourceOperation = Literal["get", "create", "link", "search", "docs"]
EntryOperation = Literal["get", "search", "docs", "create", "refresh"]


class ArtifactTypeItem(BaseModel):
    """Typed artifact operation reference."""

    name: str
    operation: ArtifactOperation


class ResourceTypeItem(BaseModel):
    """Typed resource operation reference."""

    name: str
    operation: ResourceOperation


class EntryTypeItem(BaseModel):
    """Typed entry operation reference."""

    name: str
    operation: EntryOperation


class GeneratePayload(BaseModel):
    """Unified client-to-server payload for the `generate` WebSocket event."""

    artifact_types: list[ArtifactTypeItem]
    artifact_id: Any | None = None
    draft_id: Any | None = None
    resource_types: list[ResourceTypeItem]
    entry_types: list[EntryTypeItem] | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_resource_types(cls, data: Any) -> Any:
        """Auto-coerce plain strings to ResourceTypeItem for backward compatibility."""
        if isinstance(data, dict):
            raw = data.get("resource_types")
            if isinstance(raw, list):
                data["resource_types"] = [
                    {"name": item, "operation": "create"}
                    if isinstance(item, str)
                    else item
                    for item in raw
                ]
        return data

    @property
    def artifact_type(self) -> str:
        """Derived primary artifact type — the name of the first artifact_types entry."""
        return self.artifact_types[0].name if self.artifact_types else "unknown"

    user_instructions: list[str] | None = None
    save: bool = False
    run_id: str | None = None
    group_id: str | None = None
    modality: str = "call"
    extra_messages: list[dict[str, str]] | None = None
    metadata: dict[str, Any] | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Generate artifact types — moved from generate_artifact.py to avoid import chain
# ═══════════════════════════════════════════════════════════════════════════


class ModelConfig(BaseModel):
    """Model configuration for token factory."""

    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    reasoning: str | None = None
    provider: str | None = None
    voice: str | None = None
    quality: str | None = None
    length_seconds: int | None = None
    response_format: dict[str, Any] | None = None
    tool_choice: Any | None = None
    extra_body: dict[str, Any] | None = None


class GenerateArtifactPayload(BaseModel):
    """Payload for generate_artifact internal event."""

    sid: str | None = None
    run_id: str
    group_id: str | None = None
    modality: str = "text"
    artifact_type: str | None = None
    resource_type: str | None = None
    resource_types: list[str] | None = None
    resource_id: str | None = None
    messages: list[dict[str, Any]]
    llm_config: ModelConfig
    tools: list[dict[str, Any]] | None = None
    tool_timeout_seconds: float = 60.0
    file_path: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    upload_id: str | None = None
    chat_id: str | None = None
    metadata: dict[str, Any] | None = None
    message_id: str | None = None
    profile_id: str | None = None
    profiles_id: str | None = None
    session_id: str | None = None
    artifact_id: str | None = None
    draft_id: str | None = None
    developer_instruction_templates: list[str] | None = None
    agent_id: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Client-facing generation event types (server → client)
# ═══════════════════════════════════════════════════════════════════════════

from pydantic import Field


class GenerationProgressEvent(BaseModel):
    """Server-to-client: generation resource progress."""

    artifact_type: str = Field(..., description="Type of artifact being generated")
    group_id: str = Field(..., description="UUID of the generation group")
    run_id: str = Field(..., description="UUID of the generation run")
    completed_resources: int = Field(..., description="Number of resources completed so far")
    total_resources: int = Field(..., description="Total number of resources to generate")
    percentage: int = Field(..., description="Progress percentage (0-100)")
    last_completed_resource: str = Field(..., description="Name of the last completed resource")


class GenerationCompleteEvent(BaseModel):
    """Server-to-client: generation complete (all agents finished)."""

    artifact_type: str = Field(..., description="Type of artifact generated")
    group_id: str = Field(..., description="UUID of the generation group")
    run_id: str = Field(..., description="UUID of the generation run")
    success: bool = Field(True, description="Whether generation succeeded")
    message: str = Field("", description="Completion message")
    artifact_id: str | None = Field(None, description="UUID of the generated artifact")


class GenerationSavedEvent(BaseModel):
    """Server-to-client: artifact persisted after generation."""

    artifact_type: str = Field(..., description="Type of artifact saved")
    group_id: str = Field(..., description="UUID of the generation group")
    run_id: str = Field(..., description="UUID of the generation run")
    artifact_id: str | None = Field(None, description="UUID of the saved artifact")


class GenerationErrorEvent(BaseModel):
    """Server-to-client: generation error."""

    artifact_type: str = Field(..., description="Type of artifact that failed")
    group_id: str | None = Field(None, description="UUID of the generation group")
    resource_type: str | None = Field(None, description="Type of resource that failed")
    resource_types: list[str] | None = Field(None, description="List of resource types that failed")
    resource_id: str | None = Field(None, description="UUID of the failed resource")
    run_id: str | None = Field(None, description="UUID of the generation run")
    success: bool = Field(False, description="Always False for error events")
    message: str = Field(..., description="Error message")


class GenerationMediaProgressEvent(BaseModel):
    """Server-to-client: media generation progress (image/video)."""

    modality: str = Field(..., description="Media modality: 'image' or 'video'")
    artifact_type: str = Field(..., description="Type of artifact being generated")
    group_id: str | None = Field(None, description="UUID of the generation group")
    run_id: str | None = Field(None, description="UUID of the generation run")
    resource_type: str | None = Field(None, description="Type of resource being generated")
    resource_id: str | None = Field(None, description="UUID of the resource")
    status: str = Field(..., description="Current status: 'started' or 'in_progress'")
    message: str = Field(..., description="Progress message")


class GenerationMediaCompleteEvent(BaseModel):
    """Server-to-client: media generation complete (image/video)."""

    modality: str = Field(..., description="Media modality: 'image' or 'video'")
    artifact_type: str = Field(..., description="Type of artifact generated")
    group_id: str | None = Field(None, description="UUID of the generation group")
    run_id: str | None = Field(None, description="UUID of the generation run")
    resource_type: str | None = Field(None, description="Type of resource generated")
    resource_id: str | None = Field(None, description="UUID of the resource")
    file_path: str | None = Field(None, description="Path to the generated media file")
    mime_type: str | None = Field(None, description="MIME type of the media file")
    file_size: int | None = Field(None, description="File size in bytes")
    upload_id: str | None = Field(None, description="UUID of the upload record")
