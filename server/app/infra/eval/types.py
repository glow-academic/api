"""Handcrafted types for eval artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.eval.create import CreateEvalItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.eval_drafts.types import GetEvalDraftResponse


class GetEvalDraftsApiResponse(BaseModel):
    """Response model for eval drafts list endpoint."""

    entries: list[GetEvalDraftResponse] | None = Field(None, description="List of eval draft entries")


# ========== Eval-specific resource types ==========


class EvalFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")  # e.g., "active", "dynamic", "groups"
    label: str = Field(..., description="Display label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Selected flag option UUID")
    show: bool = Field(True, description="Whether to show this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


# ========== GET Endpoint Types - Section Types ==========


class EvalNameSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected name resource")
    resources: list[Any] | None = Field(None, description="Available name resources")


class EvalDescriptionSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected description resource")
    resources: list[Any] | None = Field(None, description="Available description resources")


class EvalFlagSection(BaseResourceSection):
    resource: EvalFlagConfig | None = Field(None, description="Currently selected flag config")
    resources: list[EvalFlagConfig] | None = Field(None, description="Available flag configs")


class EvalDepartmentSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected departments")
    resources: list[Any] | None = Field(None, description="Available departments")


class EvalModelSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected models")
    resources: list[Any] | None = Field(None, description="Available models")


class EvalModelFlagSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected model flags")
    resources: list[Any] | None = Field(None, description="Available model flags")


class EvalModelRubricSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected model rubrics")
    resources: list[Any] | None = Field(None, description="Available model rubrics")


class EvalModelPositionSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected model positions")
    resources: list[Any] | None = Field(None, description="Available model positions")


class GetEvalApiRequest(BaseModel):
    """Request model for get eval endpoint."""

    eval_id: UUID | None = Field(None, description="Eval UUID to retrieve")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")


class GetEvalApiResponse(BaseModel):
    """Response model for get eval endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    eval_exists: bool | None = Field(None, description="Whether the eval exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Associated group UUID")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic step")
    model_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for model step")

    names: EvalNameSection | None = Field(None, description="Name section with resource and options")
    descriptions: EvalDescriptionSection | None = Field(None, description="Description section with resource and options")
    active_flags: EvalFlagSection | None = Field(None, description="Active flag section")
    dynamic_flags: EvalFlagSection | None = Field(None, description="Dynamic flag section")
    groups_flags: EvalFlagSection | None = Field(None, description="Groups flag section")
    departments: EvalDepartmentSection | None = Field(None, description="Department section with selections and options")
    models: EvalModelSection | None = Field(None, description="Model section with selections and options")
    model_flags: EvalModelFlagSection | None = Field(None, description="Model flag section")
    model_rubrics: EvalModelRubricSection | None = Field(None, description="Model rubric section")
    model_positions: EvalModelPositionSection | None = Field(None, description="Model position section")


# ========== List Endpoint Types ==========


class ListEvalApiEval(BaseModel):
    """Eval type for list endpoint with computed permissions."""

    eval_id: UUID | None = Field(None, description="Eval UUID")
    name: str | None = Field(None, description="Eval name")
    description: str | None = Field(None, description="Eval description")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    is_inactive: bool | None = Field(None, description="Whether the eval is inactive")
    is_dynamic: bool | None = Field(None, description="Whether the eval uses dynamic mode")
    use_groups: bool | None = Field(None, description="Whether the eval uses groups")
    num_runs: int | None = Field(None, description="Number of eval runs")
    num_groups: int | None = Field(None, description="Number of eval groups")
    # Computed in Python
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListEvalApiResponse(BaseModel):
    """Response model for list eval endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    evals: list[ListEvalApiEval] | None = Field(None, description="List of evals")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")
    user_role: str | None = Field(None, description="Role of the current user")


# ========== Shared Create/Update Types ==========


class EvalFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class EvalResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    eval_id: UUID | None = Field(None, description="Eval UUID")
    message: str = Field(..., description="Human-readable result message")
    errors: list[EvalFieldError] | None = Field(None, description="List of per-field errors")


# ========== Create Endpoint Types ==========


class CreateEvalApiRequest(BaseModel):
    """Request model for bulk create eval endpoint."""

    evals: list[CreateEvalItem] = Field(..., description="List of evals to create")


class CreateEvalApiResponse(BaseModel):
    """Response model for bulk create eval endpoint."""

    results: list[EvalResultItem] = Field(..., description="List of operation results")


# ========== Update Endpoint Types ==========


class UpdateEvalItem(BaseModel):
    """Single eval item for update — eval_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    eval_id: UUID = Field(..., description="Eval UUID to update")  # Required — which eval to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Multi-select — IDs only (matching get.py junctions)
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    model_ids: list[UUID] | None = Field(None, description="Model UUIDs")
    model_flag_ids: list[UUID] | None = Field(None, description="Model flag UUIDs")
    model_rubric_ids: list[UUID] | None = Field(None, description="Model rubric UUIDs")
    model_position_ids: list[UUID] | None = Field(None, description="Model position UUIDs")


class UpdateEvalApiRequest(BaseModel):
    """Request model for bulk update eval endpoint."""

    evals: list[UpdateEvalItem] = Field(..., description="List of evals to update")


class UpdateEvalApiResponse(BaseModel):
    """Response model for bulk update eval endpoint."""

    results: list[EvalResultItem] = Field(..., description="List of operation results")


class SaveEvalFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


# ========== Delete Endpoint Types ==========


class DeleteEvalApiRequest(BaseModel):
    """Request model for bulk delete eval endpoint."""

    eval_ids: list[UUID] = Field(..., description="Eval UUIDs to delete")


class DeleteEvalResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    eval_id: UUID = Field(..., description="Eval UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteEvalApiResponse(BaseModel):
    """Response model for bulk delete eval endpoint."""

    results: list[DeleteEvalResult] = Field(..., description="List of operation results")


# ========== Duplicate Endpoint Types ==========


class DuplicateEvalApiRequest(BaseModel):
    """Request model for duplicate eval endpoint."""

    eval_id: UUID = Field(..., description="Eval UUID to duplicate")


class DuplicateEvalApiResponse(BaseModel):
    """Response model for duplicate eval endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    eval_id: UUID = Field(..., description="Newly created eval UUID")
    message: str = Field(..., description="Human-readable result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchEvalDraftApiRequest(BaseModel):
    """Request model for new-style eval draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, model_ids, rubric_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    expected_version: int = Field(0, description="Expected draft version for concurrency control")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to create a resource")
    name_id: UUID | None = Field(None, description="Existing name resource UUID")
    description: str | None = Field(None, description="Description value to create a resource")
    description_id: UUID | None = Field(None, description="Existing description resource UUID")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    model_ids: list[UUID] | None = Field(None, description="Model UUIDs")
    rubric_ids: list[UUID] | None = Field(None, description="Rubric UUIDs")


class EvalDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    flag_ids: list[UUID] = Field(..., description="Selected flag option UUIDs")
    department_ids: list[UUID] = Field(..., description="Selected department UUIDs")
    model_ids: list[UUID] = Field(..., description="Selected model UUIDs")
    rubric_ids: list[UUID] = Field(..., description="Selected rubric UUIDs")


class PatchEvalDraftApiResponse(BaseModel):
    """Response model for new-style eval draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    new_version: int = Field(..., description="New draft version number after patch")
    message: str = Field(..., description="Human-readable result message")
    form_state: EvalDraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportEvalApiResponse(BaseModel):
    """Response model for export eval endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")
