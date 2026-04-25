"""Handcrafted types for eval artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.eval_drafts.types import GetEvalDraftResponse


class GetEvalDraftsApiResponse(BaseModel):
    """Response model for eval drafts list endpoint."""

    entries: list[GetEvalDraftResponse] | None = Field(None, description="List of eval draft entries")


# ========== Eval-specific resource types ==========


class EvalNameResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'eval_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class EvalDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalModelResource(BaseModel):
    id: UUID | None = Field(None, description="Model resource identifier")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description text")
    modality_ids: list[UUID] | None = Field(None, description="Associated modality identifiers")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalModelFlagResource(BaseModel):
    id: UUID | None = Field(None, description="Model-flag resource identifier")
    model_id: UUID | None = Field(None, description="Associated model identifier")
    flag_id: UUID | None = Field(None, description="Associated flag identifier")
    type: str | None = Field(None, description="Flag type (e.g. 'model_active') of the linked flags_resource row")
    value: bool | None = Field(None, description="Underlying bool value of the linked flags_resource row")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description text")
    icon: str | None = Field(None, description="Icon identifier")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalModelFlagOptionResource(BaseModel):
    """Cross-product option row: one per (model_id, flag_type, value) tuple.
    The ModelFlags picker groups these by (model_id, type) and renders a
    Switch per group; toggling picks the row whose `value` matches the new
    state and sends its flag_id (or denormalized {model_id,type,value}) up
    through the draft endpoint."""

    model_id: UUID | None = Field(None, description="Model identifier")
    flag_id: UUID | None = Field(None, description="Flag resource identifier (flags_resource row)")
    type: str | None = Field(None, description="Flag type, e.g. 'model_active'")
    value: bool | None = Field(None, description="Underlying flag value for this option")
    name: str | None = Field(None, description="Display name from the flags_resource row")
    description: str | None = Field(None, description="Description text from the flags_resource row")
    icon: str | None = Field(None, description="Icon SVG markup hydrated from icons_resource")


class EvalModelFlagValue(BaseModel):
    """Denormalized per-(model, type) selection. Clients send these to update
    model-flag selections without needing the underlying flag_id; the server
    resolves (type, value) -> flag_id and upserts the model_flags_resource
    junction row."""

    model_id: UUID = Field(..., description="Target model identifier")
    type: str = Field(..., description="Flag type, e.g. 'model_active'")
    value: bool = Field(..., description="Desired flag value")


class EvalModelRubricResource(BaseModel):
    id: UUID | None = Field(None, description="Model-rubric resource identifier")
    model_id: UUID | None = Field(None, description="Associated model identifier")
    rubric_id: UUID | None = Field(None, description="Associated rubric identifier")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalModelPositionResource(BaseModel):
    id: UUID | None = Field(None, description="Model-position resource identifier")
    model_id: UUID | None = Field(None, description="Associated model identifier")
    value: int | float | None = Field(None, description="Associated position value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class EvalRubricResource(BaseModel):
    """Top-level rubric catalog entry. The ModelRubrics picker renders
    one of these per option (alongside a "no rubric" clear state)."""

    id: UUID | None = Field(None, description="Rubric resource UUID")
    name: str | None = Field(None, description="Rubric display name")
    description: str | None = Field(None, description="Rubric description")


class SectionFilter(BaseModel):
    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(
        None,
        description="Reserved for compatibility with shared filter parsing",
    )


class GetEvalApiRequest(BaseModel):
    """Request model for get eval endpoint."""

    id: UUID | None = Field(None, description="Eval UUID to retrieve")
    eval_id: UUID | None = Field(None, description="Legacy eval UUID to retrieve")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    models: SectionFilter | None = Field(None, description="Filter options for models section")
    model_flags: SectionFilter | None = Field(None, description="Filter options for model flags section")
    model_rubrics: SectionFilter | None = Field(None, description="Filter options for model rubrics section")
    model_positions: SectionFilter | None = Field(None, description="Filter options for model positions section")


class GetEvalApiResponse(BaseModel):
    """Canonical flat composed response for the eval editor."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    eval_exists: bool | None = Field(None, description="Whether the eval exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Associated group UUID")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for the basic step")
    model_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for the model step")
    show_ai_generate: bool | None = Field(None, description="Whether any AI generate action should be shown")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[EvalNameResource] | None = Field(None, description="Name resources")
    descriptions: list[EvalDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[EvalFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[EvalDepartmentResource] | None = Field(None, description="Department resources")
    models: list[EvalModelResource] | None = Field(None, description="Model resources")
    model_flags: list[EvalModelFlagResource] | None = Field(None, description="Model flag resources (linked junction rows)")
    model_flag_options: list[EvalModelFlagOptionResource] | None = Field(
        None,
        description=(
            "Cross-product (model x flag-type x value) options for the ModelFlags picker."
        ),
    )
    model_rubrics: list[EvalModelRubricResource] | None = Field(None, description="Model rubric resources")
    model_positions: list[EvalModelPositionResource] | None = Field(None, description="Model position resources")
    rubrics: list[EvalRubricResource] | None = Field(None, description="Top-level rubric catalog for the ModelRubrics picker")


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
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
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


class CreateEvalItem(ScopedItem):
    """Single eval item for create — no eval_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "model_ids": "models",
        "model_flag_ids": "model_flags",
        "model_rubric_ids": "model_rubrics",
        "model_position_ids": "model_positions",
        "active": "flags",
    }

    id: UUID | None = Field(None, description="Optional pre-assigned UUID")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    # Optional single-select — provide ID or value
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
    # Denormalized bool — resolved to a flag_ids entry server-side.
    active: bool | None = Field(None, description="Denormalized eval_active flag state; resolved to a flag_ids entry server-side")


class CreateEvalApiRequest(BaseModel):
    """Request model for bulk create eval endpoint."""

    evals: list[CreateEvalItem] = Field(..., description="List of evals to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateEvalApiResponse(BaseModel):
    """Response model for bulk create eval endpoint."""

    results: list[EvalResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateEvalItem(ScopedItem):
    """Single eval item for update — eval_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateEvalItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="Eval UUID to update")  # Required — which eval to update
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
    # Denormalized bool — resolved to a flag_ids entry server-side.
    active: bool | None = Field(None, description="Denormalized eval_active flag state; resolved to a flag_ids entry server-side")


class UpdateEvalApiRequest(BaseModel):
    """Request model for bulk update eval endpoint."""

    evals: list[UpdateEvalItem] = Field(..., description="List of evals to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateEvalApiResponse(BaseModel):
    """Response model for bulk update eval endpoint."""

    results: list[EvalResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveEvalFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


# ========== Delete Endpoint Types ==========


class DeleteEvalApiRequest(BaseModel):
    """Request model for bulk delete eval endpoint."""

    eval_ids: list[UUID] = Field(..., description="Eval UUIDs to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteEvalResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    eval_id: UUID = Field(..., description="Eval UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteEvalApiResponse(BaseModel):
    """Response model for bulk delete eval endpoint."""

    results: list[DeleteEvalResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicateEvalApiRequest(BaseModel):
    """Request model for duplicate eval endpoint."""

    eval_id: UUID = Field(..., description="Eval UUID to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateEvalApiResponse(BaseModel):
    """Response model for duplicate eval endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    eval_id: UUID = Field(..., description="Newly created eval UUID")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchEvalDraftApiRequest(ScopedItem):
    """Request model for new-style eval draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, model_ids, rubric_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "departments": "departments",
        "department_ids": "departments",
        "model_ids": "models",
        "model_flag_ids": "model_flags",
        "model_flags": "model_flags",
        "model_flag_values": "model_flags",
        "model_position_ids": "model_positions",
        "model_rubric_ids": "model_rubrics",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to create a resource")
    name_id: UUID | None = Field(None, description="Existing name resource UUID")
    description: str | None = Field(None, description="Description value to create a resource")
    description_id: UUID | None = Field(None, description="Existing description resource UUID")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized eval_active flag state; resolved to a flag_ids entry server-side")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    model_ids: list[UUID] | None = Field(None, description="Model UUIDs")
    model_flag_ids: list[UUID] | None = Field(None, description="Model flag UUIDs (canonical junction-row ids)")
    model_flags: list[dict] | None = Field(
        None,
        description=(
            "Inline-create shape for model_flags junction rows: list of "
            "{model_id, flag_id} (id=null entries). Resolver upserts the "
            "junction row and merges the id into model_flag_ids."
        ),
    )
    model_flag_values: list[EvalModelFlagValue] | None = Field(
        None,
        description=(
            "Denormalized per-(model, type) selections. For each entry the "
            "server resolves (type, value) -> flag_id via search_flags, "
            "then upserts a model_flags_resource row for (model_id, flag_id) "
            "and merges its id into model_flag_ids."
        ),
    )
    model_position_ids: list[UUID] | None = Field(None, description="Model position UUIDs")
    model_rubric_ids: list[UUID] | None = Field(None, description="Model rubric UUIDs")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep inactive on the draft")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant draft")
    accept: bool = Field(True, description="Accept or reject dormant state. Only meaningful with idempotency_key")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    name: str | None = Field(None, description="Echoed selected name value")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    description: str | None = Field(None, description="Echoed selected description value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed eval_active flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Selected department UUIDs")
    model_ids: list[UUID] = Field(default_factory=list, description="Selected model UUIDs")
    model_flag_ids: list[UUID] = Field(default_factory=list, description="Selected model flag UUIDs")
    model_flag_values: list[EvalModelFlagValue] = Field(
        default_factory=list,
        description="Denormalized (model_id, type, value) echo derived from model_flag_ids",
    )
    model_position_ids: list[UUID] = Field(default_factory=list, description="Selected model position UUIDs")
    model_rubric_ids: list[UUID] = Field(default_factory=list, description="Selected model rubric UUIDs")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


class PatchEvalDraftApiResponse(BaseModel):
    """Response model for new-style eval draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    idempotency_key: UUID | None = Field(None, description="Operation key echoed back for client correlation")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportEvalApiResponse(BaseModel):
    """Response model for export eval endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsEvalApiRequest(BaseModel):
    """Request model for eval generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsEvalListItem(BaseModel):
    """Single generation group in the eval generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsEvalApiResponse(BaseModel):
    """Response model for eval generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsEvalListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemEvalApiRequest(BaseModel):
    """Request model for eval problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemEvalApiResponse(BaseModel):
    """Response model for eval problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
