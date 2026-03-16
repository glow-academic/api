"""Handcrafted types for rubric artifact endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.rubric.create import CreateRubricItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.rubric_drafts.types import GetRubricDraftResponse


class RubricFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Display label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Selected flag option UUID")
    show: bool = Field(True, description="Whether to show this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class RubricNameSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected name resource")
    resources: list[Any] | None = Field(None, description="Available name resources")


class RubricDescriptionSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected description resource")
    resources: list[Any] | None = Field(None, description="Available description resources")


class RubricFlagSection(BaseResourceSection):
    current: list[RubricFlagConfig] | None = Field(None, description="Currently selected flag configs")
    resources: list[RubricFlagConfig] | None = Field(None, description="Available flag configs")


class RubricDepartmentSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected departments")
    resources: list[Any] | None = Field(None, description="Available departments")


class RubricPointsSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected points resource")
    resources: list[Any] | None = Field(None, description="Available points resources")


class RubricStandardGroupsSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected standard groups")
    resources: list[Any] | None = Field(None, description="Available standard groups")


class RubricStandardsSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected standards")
    resources: list[Any] | None = Field(None, description="Available standards")


class GetRubricApiRequest(BaseModel):
    rubric_id: UUID | None = Field(None, description="Rubric UUID to retrieve")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")


class GetRubricApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current user")
    rubric_exists: bool | None = Field(None, description="Whether the rubric exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Associated group UUID")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic step")
    content_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for content step")

    names: RubricNameSection | None = Field(None, description="Name section with resource and options")
    descriptions: RubricDescriptionSection | None = Field(None, description="Description section with resource and options")
    flags: RubricFlagSection | None = Field(None, description="Flag section with selections and options")
    departments: RubricDepartmentSection | None = Field(None, description="Department section with selections and options")
    points: RubricPointsSection | None = Field(None, description="Points section with resource and options")
    standard_groups: RubricStandardGroupsSection | None = Field(None, description="Standard groups section")
    standards: RubricStandardsSection | None = Field(None, description="Standards section")


class GetRubricDraftsApiResponse(BaseModel):
    """Response model for rubric drafts list endpoint."""

    entries: list[GetRubricDraftResponse] | None = Field(None, description="List of rubric draft entries")


# ========== Shared Create/Update Types ==========


class RubricFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class RubricResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    rubric_id: UUID | None = Field(None, description="Rubric UUID")
    message: str = Field(..., description="Human-readable result message")
    errors: list[RubricFieldError] | None = Field(None, description="List of per-field errors")


# ========== Create Endpoint Types ==========


class CreateRubricApiRequest(BaseModel):
    """Request model for bulk create rubric endpoint."""

    rubrics: list[CreateRubricItem] = Field(..., description="List of rubrics to create")


class CreateRubricApiResponse(BaseModel):
    """Response model for bulk create rubric endpoint."""

    results: list[RubricResultItem] = Field(..., description="List of operation results")


# ========== Update Endpoint Types ==========


class UpdateRubricItem(BaseModel):
    """Single rubric item for update — rubric_id required, all fields optional."""

    rubric_id: UUID = Field(..., description="Rubric UUID to update")  # Required — which rubric to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    active_flag_id: UUID | None = Field(None, description="Active flag option UUID")
    active_flag: bool | None = Field(None, description="Active flag boolean value")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # ID-only fields
    point_ids: list[UUID] | None = Field(None, description="Point UUIDs")
    standard_group_ids: list[UUID] | None = Field(None, description="Standard group UUIDs")
    standard_ids: list[UUID] | None = Field(None, description="Standard UUIDs")


class UpdateRubricApiRequest(BaseModel):
    """Request model for bulk update rubric endpoint."""

    rubrics: list[UpdateRubricItem] = Field(..., description="List of rubrics to update")


class UpdateRubricApiResponse(BaseModel):
    """Response model for bulk update rubric endpoint."""

    results: list[RubricResultItem] = Field(..., description="List of operation results")


class SaveRubricFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class DeleteRubricApiRequest(BaseModel):
    """Request model for bulk delete rubric endpoint."""

    rubric_ids: list[UUID] = Field(..., description="Rubric UUIDs to delete")


class DeleteRubricResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    rubric_id: UUID = Field(..., description="Rubric UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteRubricApiResponse(BaseModel):
    """Response model for bulk delete rubric endpoint."""

    results: list[DeleteRubricResult] = Field(..., description="List of operation results")


class DuplicateRubricApiRequest(BaseModel):
    rubric_id: UUID = Field(..., description="Rubric UUID to duplicate")


class DuplicateRubricApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation succeeded")
    rubric_id: UUID = Field(..., description="Newly created rubric UUID")
    message: str = Field(..., description="Human-readable result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchRubricDraftApiRequest(BaseModel):
    """Request model for new-style rubric draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, point_ids, standard_group_ids, standard_ids

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
    flag_id: UUID | None = Field(None, description="Flag option UUID")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    point_ids: list[UUID] | None = Field(None, description="Point UUIDs")
    standard_group_ids: list[UUID] | None = Field(None, description="Standard group UUIDs")
    standard_ids: list[UUID] | None = Field(None, description="Standard UUIDs")


class RubricDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    flag_id: UUID | None = Field(None, description="Selected flag option UUID")
    department_ids: list[UUID] = Field(..., description="Selected department UUIDs")
    point_ids: list[UUID] = Field(..., description="Selected point UUIDs")
    standard_group_ids: list[UUID] = Field(..., description="Selected standard group UUIDs")
    standard_ids: list[UUID] = Field(..., description="Selected standard UUIDs")


class PatchRubricDraftApiResponse(BaseModel):
    """Response model for new-style rubric draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    new_version: int = Field(..., description="New draft version number after patch")
    message: str = Field(..., description="Human-readable result message")
    form_state: RubricDraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportRubricApiResponse(BaseModel):
    """Response model for export rubric endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# ========== List Endpoint Types ==========


class ListRubricApiRubric(BaseModel):
    rubric_id: UUID | None = Field(None, description="Rubric UUID")
    name: str | None = Field(None, description="Rubric name")
    description: str | None = Field(None, description="Rubric description")
    points: int | None = Field(None, description="Total points")
    pass_points: int | None = Field(None, description="Points required to pass")
    pass_percentage: int | None = Field(None, description="Percentage required to pass")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    simulation_ids: list[str] | None = Field(None, description="Associated simulation IDs")
    active_simulation_count: int | None = Field(None, description="Number of active simulations using this rubric")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    standard_group_ids: list[UUID] | None = Field(None, description="Associated standard group UUIDs")


class ListRubricApiStandardGroup(BaseModel):
    standard_group_id: UUID | None = Field(None, description="Standard group UUID")
    rubric_id: UUID | None = Field(None, description="Parent rubric UUID")
    name: str | None = Field(None, description="Standard group name")
    description: str | None = Field(None, description="Standard group description")
    points: int | None = Field(None, description="Total points for this group")
    pass_points: int | None = Field(None, description="Points required to pass this group")


class ListRubricApiStandard(BaseModel):
    standard_id: UUID | None = Field(None, description="Standard UUID")
    standard_group_id: UUID | None = Field(None, description="Parent standard group UUID")
    name: str | None = Field(None, description="Standard name")
    description: str | None = Field(None, description="Standard description")
    points: int | None = Field(None, description="Points for this standard")


class ListRubricApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current user")
    rubrics: list[ListRubricApiRubric] | None = Field(None, description="List of rubrics")
    standard_groups: list[ListRubricApiStandardGroup] | None = Field(None, description="List of standard groups")
    standards: list[ListRubricApiStandard] | None = Field(None, description="List of standards")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments in list UI")
    simulation_filter: ListFilterSection | None = Field(None, description="Filter options for simulations in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")
