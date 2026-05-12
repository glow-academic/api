"""Pydantic models for generation-domain internal bus emits.

Each model represents a dict payload passed to ``internal_sio.emit()``.
Construct the model, then call ``.model_dump(mode="json")``
before sending via internal_sio.emit(..., model.model_dump(mode="json")).
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

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
    tool_results: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


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
# Generate gate types — moved from routes/socket/ to avoid import chain
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


from pydantic import model_validator

# ═══════════════════════════════════════════════════════════════════════════
# Internal bus payload — flows between prepare and execute
# ═══════════════════════════════════════════════════════════════════════════


class GeneratePayload(BaseModel):
    """Internal bus payload — built by the server from ArtifactGenerateRequest.

    The canonical internal representation of a generation request.
    WebSocket clients can also send data matching this shape directly.
    """

    artifact_type: str = "unknown"
    # Optional caller-supplied label for media generations. Becomes the
    # ``name`` on the produced ``{m}s_resource`` row so the asset shows
    # up in pickers as something human (e.g. "University Office") instead
    # of the UUID-derived fallback. ``media_upload_impl`` handles
    # collisions by suffixing with " 1", " 2", … so multiple generates
    # under the same title still get distinct rows. Regular uploads
    # already derive a name from the filename, so this field is only
    # needed on the LLM-driven generation path.
    title: str | None = None
    instructions: list[str] | None = None
    # Role to attribute the persisted ``instructions`` messages to.
    # Defaults to ``"user"`` (FE-direct flow: a human typed something).
    # The INFRA_OPS tool dispatcher overrides to ``"assistant"`` because
    # in the tool-driven path the parent LLM crafted those instructions
    # as a tool argument — they aren't human input. Persona/scenario
    # text generation reads ``payload.instructions_role`` in
    # ``prepare_generation`` and uses it for ``persist_run_message``.
    instructions_role: str = "user"
    operations: list[str] | None = None
    dangerous: bool = False
    params: dict[str, Any] | None = None
    group_id: str | None = None
    run_id: str | None = None
    # FE-provided stable id (typically a fresh uuid4 generated client-side).
    # When set, the server uses it as the ``runs_entry.id``. Lets the FE
    # subscribe to events scoped to this run_id BEFORE the run is created,
    # so no race on the first events of the run.
    client_run_id: str | None = None
    modalities: list[str] | None = None     # requested output modalities
    audios_id: str | None = None            # resource-level audio handle for STT input
    conversation_id: str | None = None      # live realtime conversation buffer
    # Internal-only fields (not in client-facing request)
    extra_messages: list[dict[str, str]] | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: Any) -> Any:
        """Coerce legacy formats for backward compatibility.

        Handles old clients sending permissions, artifact_types, user_instructions, etc.
        """
        if not isinstance(data, dict):
            return data

        # Strip fully removed fields
        for key in ("resources", "resource_types", "permission_ids", "entry_types"):
            data.pop(key, None)

        # Legacy: permissions [{artifact, operation}] → operations [str]
        raw_perms = data.pop("permissions", None)
        if raw_perms and isinstance(raw_perms, list) and "operations" not in data:
            ops: list[str] = []
            artifact = None
            for p in raw_perms:
                if isinstance(p, dict):
                    ops.append(p.get("operation", ""))
                    artifact = artifact or p.get("artifact")
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    ops.append(p[1])
                    artifact = artifact or p[0]
            if ops:
                data["operations"] = ops
            if artifact and not data.get("artifact_type"):
                data["artifact_type"] = artifact

        # Legacy: artifact_types [{name, operation}] → artifact_type + operations
        raw_at = data.pop("artifact_types", None)
        if raw_at and isinstance(raw_at, list) and not data.get("artifact_type"):
            first = raw_at[0] if raw_at else {}
            if isinstance(first, dict):
                data.setdefault("artifact_type", first.get("name", "unknown"))
                if "operations" not in data:
                    data["operations"] = [
                        item.get("operation", "get")
                        for item in raw_at
                        if isinstance(item, dict)
                    ]

        # Legacy: user_instructions → instructions
        raw_ui = data.pop("user_instructions", None)
        if raw_ui and "instructions" not in data:
            data["instructions"] = raw_ui

        # Legacy: artifact_id / draft_id → params
        artifact_id = data.pop("artifact_id", None)
        draft_id = data.pop("draft_id", None)
        if artifact_id or draft_id:
            params = data.get("params") or {}
            if artifact_id and "artifact_id" not in params:
                params["artifact_id"] = str(artifact_id)
            if draft_id and "draft_id" not in params:
                params["draft_id"] = str(draft_id)
            data["params"] = params

        return data


# ═══════════════════════════════════════════════════════════════════════════
# Per-artifact generate types — used by <artifact>/generate endpoints
# ═══════════════════════════════════════════════════════════════════════════


class GenerateConfig(BaseModel):
    """Developer configuration — all optional with sensible defaults."""

    operations: list[str] | None = None  # ["draft", "get", "group"] — defaults to artifact's standard ops
    dangerous: bool = False              # True = execute immediately, False = review first
    params: dict[str, Any] | None = None  # developer context (draft_id, entity_id, etc.)
    group_id: str | None = None          # optional — server resolves if omitted


class ArtifactGenerateRequest(BaseModel):
    """Per-artifact generate request. Artifact type is implicit from the endpoint URL."""

    instructions: list[str] | None = None   # what the user wants (text input)
    config: GenerateConfig | None = None    # developer configuration
    modalities: list[str] | None = None     # output modalities: ["text"], ["audio"], ["video"], ["audio", "text"]
    audios_id: UUID | None = None           # resource-level audio handle (STT input)
    conversation_id: UUID | None = None     # continue a realtime session
    trace_id: UUID | None = None            # test bundle handle (test_invocation_traces_entry)
                                             # everything else (is_dynamic, agent, tools,
                                             # instructions, prompts, modalities) is derived
                                             # server-side via black boxes
    idempotency_key: UUID | None = None     # ack
    accept: bool = True                     # ack
    # Block on the full execute+refresh pipeline (default) vs. fire the
    # run as a background asyncio task and return ``run_id`` immediately.
    # ``None`` lets the calling layer pick the default — today the HTTP
    # route and the LLM tool dispatcher both default to ``True`` (blocking).
    # Flip to ``False`` to opt into fire-and-forget; pair with ``X_Watch``
    # if the caller wants to block on a specific run later.
    wait_for_complete: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: Any) -> Any:
        """Coerce legacy request formats for backward compatibility."""
        if not isinstance(data, dict):
            return data

        # Already new format
        if "config" in data:
            # Still map user_instructions → instructions
            raw_ui = data.pop("user_instructions", None)
            if raw_ui and "instructions" not in data:
                data["instructions"] = raw_ui
            return data

        # Legacy format detected — restructure into new shape
        raw_ui = data.pop("user_instructions", None)
        if raw_ui and "instructions" not in data:
            data["instructions"] = raw_ui

        config: dict[str, Any] = {}

        # permissions [{artifact, operation}] → operations [str]
        raw_perms = data.pop("permissions", None)
        if raw_perms and isinstance(raw_perms, list):
            config["operations"] = [
                p.get("operation", "") if isinstance(p, dict)
                else (p[1] if isinstance(p, (list, tuple)) else "")
                for p in raw_perms
            ]

        config["dangerous"] = data.pop("dangerous", False)
        config["group_id"] = data.pop("group_id", None)

        # Merge artifact_id, draft_id, params into config.params
        params = data.pop("params", None) or {}
        artifact_id = data.pop("artifact_id", None)
        draft_id = data.pop("draft_id", None)
        if artifact_id:
            params["artifact_id"] = str(artifact_id)
        if draft_id:
            params["draft_id"] = str(draft_id)
        if params:
            config["params"] = params

        # Drop server-internal fields that don't belong in client request
        for k in ("permission_ids", "modality", "extra_messages",
                   "metadata", "sid", "run_id", "resources", "resource_types"):
            data.pop(k, None)

        data["config"] = config
        return data


class InvocationSlot(BaseModel):
    """One agent's slot in a multi-agent generation pool.

    Populated by ``setup_generation_test`` when an agent carries a
    rubric. The client uses these IDs to drive the eval workflow:
    review the candidate's output, optionally fire a grader against
    its ``invocation_id``, and promote/reject by call_id via the
    existing ``idempotency_key + accept`` pattern.
    """

    invocation_id: UUID
    agent_id: UUID
    rubric_id: UUID | None = None


class EvalSetup(BaseModel):
    """Run-level eval scaffold — first-class on the generate response.

    Audit's ``**output`` spread carries this onto
    ``<artifact>.generate.completed``. Null when no rubric-bearing
    agent participated.
    """

    test_id: UUID
    invocations: list[InvocationSlot]


class ProducedMedia(BaseModel):
    """One asset produced by a generation run.

    ``resource_id`` is the canonical id the per-artifact download tools
    accept (e.g. ``Scenario_Image_Download(image_id=resource_id)`` for
    ``modality="image"``). It maps to ``images_resource.id`` /
    ``videos_resource.id`` / ``audios_resource.id`` depending on the
    modality.
    """

    modality: Literal["image", "video", "audio"]
    resource_id: UUID
    upload_id: UUID
    mime_type: str | None = None
    file_size: int | None = None


class ArtifactGenerateResponse(BaseModel):
    """Response from a per-artifact generate endpoint."""

    group_id: str
    run_id: str | None = None
    idempotency_key: UUID | None = None
    # Eval scaffold for multi-candidate generations. Rides on the
    # audit-emitted ``<artifact>.generate.completed`` event via the
    # framework's ``**output`` spread — clients pick it up directly,
    # no metadata digging required.
    eval: EvalSetup | None = None
    # Media artifacts produced by this run — typically populated by
    # ``execute_media_dispatch`` (image/video generation) and bubbled up
    # so the calling LLM tool can fetch via X_Image_Download /
    # X_Video_Download without a separate watch step. Empty for runs
    # that didn't produce any media (or for fire-and-forget runs that
    # returned before media finished).
    produced_media: list[ProducedMedia] = []


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
