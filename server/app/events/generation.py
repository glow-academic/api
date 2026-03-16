"""Artifact-scoped generation event models.

Each artifact declares a single strongly-typed progress event that covers
all of its sub-resources.  The ``resource_type`` field discriminates which
sub-resource is being generated.

These replace the old per-resource RESOURCE_EVENTS / ENTRY_EVENTS dicts.
"""

from __future__ import annotations

from pydantic import BaseModel


class GenerationProgressBase(BaseModel):
    """Base fields shared by all artifact generation progress events."""

    artifact_type: str = ""
    resource_type: str = ""
    group_id: str | None = None       # canonical — always present at runtime
    artifact_id: str | None = None    # optional — None for drafts
    run_id: str | None = None
    success: bool | None = None
    message: str | None = None
    error_stage: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    arguments_delta: str | None = None
    id: str | None = None
    generated: bool | None = None


# ---------------------------------------------------------------------------
# Persona generation progress
# ---------------------------------------------------------------------------
# Sub-resources from DB junction tables (excludes "personas" — the artifact
# itself, which already has lifecycle events):
#   names, descriptions, examples, instructions,
#   colors, icons, flags, departments, parameter_fields, voices


class PersonaGenerationProgressEvent(GenerationProgressBase):
    """Progress event for persona sub-resource generation.

    ``resource_type`` indicates which sub-resource: names, descriptions,
    examples, instructions, colors, icons, flags, departments,
    parameter_fields, or voices.
    """

    artifact_type: str = "persona"

    # --- names ---
    name: str | None = None

    # --- descriptions ---
    description: str | None = None

    # --- examples ---
    example: str | None = None

    # --- instructions ---
    template: str | None = None

    # --- colors ---
    hex_code: str | None = None

    # --- icons / flags ---
    value: str | None = None
    icon: str | None = None
    type: str | None = None

    # --- departments ---
    department_ids: list | None = None
    setting_ids: list | None = None

    # --- parameter_fields ---
    field_id: str | None = None
    updated_at: str | None = None
    parameter_id: str | None = None
    conditional_parameter_id: str | None = None
    conditional_parameter_ids: list | None = None

    # --- voices ---
    voice: str | None = None
