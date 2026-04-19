"""Handcrafted types for tool artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.tool_drafts.types import GetToolDraftResponse


class ToolFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Option ID to use when enabling")
    show: bool = Field(True, description="Whether to display this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this flag was AI-generated")

    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ToolNameResource(BaseModel):
    id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Tool display name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ToolDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Tool description")
    generated: bool | None = Field(None, description="Whether the description was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ToolArgResource(BaseModel):
    id: UUID | None = Field(None, description="Argument resource identifier")
    name: str | None = Field(None, description="Argument name")
    description: str | None = Field(None, description="Argument description")
    field_type: str | None = Field(None, description="Argument field type")
    required: bool | None = Field(None, description="Whether the argument is required")
    default_value: str | None = Field(None, description="Argument default value")
    generated: bool | None = Field(None, description="Whether the argument was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ToolArgPositionResource(BaseModel):
    id: UUID | None = Field(None, description="Argument position resource identifier")
    args_id: UUID | None = Field(None, description="Associated argument identifier")
    value: int | None = Field(None, description="Position value")
    generated: bool | None = Field(None, description="Whether the argument position was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ToolArgOutputResource(BaseModel):
    id: UUID | None = Field(None, description="Argument output resource identifier")
    args_id: UUID | None = Field(None, description="Associated argument identifier")
    name: str | None = Field(None, description="Output template name")
    template: str | None = Field(None, description="Output template body")
    generated: bool | None = Field(None, description="Whether the output template was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ToolPermissionResource(BaseModel):
    id: UUID | None = Field(None, description="Permission resource identifier")
    artifact: str | None = Field(None, description="Permission artifact type")
    operation: str | None = Field(None, description="Permission operation")
    name: str | None = Field(None, description="Permission display name")
    description: str | None = Field(None, description="Permission description")
    generated: bool | None = Field(None, description="Whether the permission was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SectionFilter(BaseModel):
    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")


class GetToolApiRequest(BaseModel):
    id: UUID | None = Field(None, description="Tool unique identifier")
    tool_id: UUID | None = Field(None, description="Legacy alias for tool unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions")
    flags: SectionFilter | None = Field(None, description="Filter options for flags")
    args: SectionFilter | None = Field(None, description="Filter options for args")
    arg_positions: SectionFilter | None = Field(None, description="Filter options for arg positions")
    args_outputs: SectionFilter | None = Field(None, description="Filter options for arg outputs")
    permissions: SectionFilter | None = Field(None, description="Filter options for permissions")


class GetToolApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    tool_exists: bool | None = Field(None, description="Whether the tool exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Group identifier for the tool")
    tool_id: UUID | None = Field(None, description="Tool identifier")
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    args_show_ai_generate: bool | None = Field(None, description="Show AI generate for args step")
    permissions_show_ai_generate: bool | None = Field(None, description="Show AI generate for permissions step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")

    names: list[ToolNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ToolDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[ToolFlagConfig] | None = Field(None, description="Flag configs")
    args: list[ToolArgResource] | None = Field(None, description="Argument resources")
    arg_positions: list[ToolArgPositionResource] | None = Field(None, description="Argument position resources")
    args_outputs: list[ToolArgOutputResource] | None = Field(None, description="Argument output resources")
    permissions: list[ToolPermissionResource] | None = Field(None, description="Permission resources")


class ListToolApiTool(BaseModel):
    tool_id: UUID | None = Field(None, description="Tool unique identifier")
    name: str | None = Field(None, description="Display name of the tool")
    description: str | None = Field(None, description="Tool description text")
    active: bool | None = Field(None, description="Whether this tool is currently active")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")


class ListToolApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    tools: list[ListToolApiTool] | None = Field(None, description="List of tool entries")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    creatable_filter: ListFilterSection | None = Field(None, description="Creatable filter options")
    total_count: int | None = Field(None, description="Total number of tools")


class ToolFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ToolResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    tool_id: UUID | None = Field(None, description="Tool unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ToolFieldError] | None = Field(None, description="List of field-level errors")


# ========== Create Endpoint Types ==========


class CreateToolItem(ScopedItem):
    """Single tool item for create — no tool_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # ID-only fields
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    arg_positions_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    args_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    args_outputs_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")
    instruction_id: UUID | None = Field(None, description="Response template instruction resource UUID")
    tool_ids: list[UUID] | None = Field(None, description="Related tool identifiers")
    # Value-based fields for CSV import (match-by-name resolution)
    active_flag: bool | None = Field(None, description="Whether this tool is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource UUID")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "department_ids": "departments",
        "flag_ids": "flags",
        "arg_positions_ids": "arg_positions",
        "args_ids": "args",
        "args_outputs_ids": "args_outputs",
        "permission_ids": "permissions",
        "tool_ids": "tools",
        "active_flag": "flags",
        "active_flag_id": "flags",
    }


class CreateToolApiRequest(BaseModel):
    """Request model for bulk create tool endpoint."""

    tools: list[CreateToolItem] = Field(..., description="List of tools to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateToolApiResponse(BaseModel):
    """Response model for bulk create tool endpoint."""

    results: list[ToolResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateToolItem(ScopedItem):
    """Single tool item for update — tool_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    tool_id: UUID = Field(..., description="Target tool identifier to update")
    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # ID-only fields
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    arg_positions_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    args_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    args_outputs_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")
    tool_ids: list[UUID] | None = Field(None, description="Related tool identifiers")
    # Value-based fields for CSV import (match-by-name resolution)
    active_flag: bool | None = Field(None, description="Whether this tool is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource UUID")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateToolItem.RESOURCE_TYPE_MAP


class UpdateToolApiRequest(BaseModel):
    """Request model for bulk update tool endpoint."""

    tools: list[UpdateToolItem] = Field(..., description="List of tools to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateToolApiResponse(BaseModel):
    """Response model for bulk update tool endpoint."""

    results: list[ToolResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveToolFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class DeleteToolApiRequest(BaseModel):
    """Request model for bulk delete tool endpoint."""

    tool_ids: list[UUID] = Field(..., description="List of tool IDs to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteToolResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    tool_id: UUID = Field(..., description="Deleted tool identifier")
    message: str = Field(..., description="Result message")


class DeleteToolApiResponse(BaseModel):
    """Response model for bulk delete tool endpoint."""

    results: list[DeleteToolResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateToolApiRequest(BaseModel):
    tool_id: UUID = Field(..., description="Tool identifier to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateToolApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    tool_id: UUID = Field(..., description="New duplicated tool identifier")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class CreateArgInput(BaseModel):
    """Inline arg creation input."""
    name: str = Field(..., description="Argument name")
    field_type: str = Field(..., description="Argument type (string, number, boolean, array)")
    description: str = Field("", description="Argument description")
    required: bool = Field(False, description="Whether the argument is required")
    default_value: str = Field("", description="Default value")


class CreateArgPositionInput(BaseModel):
    """Inline arg position creation input."""
    args_id: UUID = Field(..., description="Argument resource ID this position belongs to")
    value: int = Field(..., description="Position value")


class CreateArgsOutputInput(BaseModel):
    """Inline args output creation input."""
    args_id: UUID = Field(..., description="Argument resource ID this output belongs to")
    name: str = Field(..., description="Output name")
    template: str = Field("", description="Output template")


class PatchToolDraftApiRequest(ScopedItem):
    """Request model for canonical tool draft endpoint."""

    draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft ID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")

    # Match / ID-backed fields
    active_flag: bool | None = Field(None, description="Whether the tool is active")
    active_flag_id: UUID | None = Field(None, description="Tool active flag identifier")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    arg_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    args: list[CreateArgInput] | None = Field(None, description="Arguments to create inline")
    arg_position_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    arg_positions: list[CreateArgPositionInput] | None = Field(None, description="Argument positions to create inline")
    args_output_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    args_outputs_ids: list[UUID] | None = Field(None, description="Legacy alias for argument output identifiers")
    args_outputs: list[CreateArgsOutputInput] | None = Field(None, description="Argument outputs to create inline")
    instruction_id: UUID | None = Field(None, description="Instruction resource identifier")
    instruction_ids: list[UUID] | None = Field(None, description="Instruction resource identifiers")
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers to preserve")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack semantics")
    accept: bool = Field(True, description="Accept or reject acknowledgement when idempotency_key is supplied")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "active_flag": "flags",
        "active_flag_id": "flags",
        "flag_ids": "flags",
        "department_ids": "departments",
        "arg_ids": "args",
        "arg_position_ids": "arg_positions",
        "args_output_ids": "args_outputs",
        "args_outputs_ids": "args_outputs",
        "instruction_id": "instructions",
        "instruction_ids": "instructions",
        "permission_ids": "permissions",
    }


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    name: str | None = Field(None, description="Resolved name value")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    description: str | None = Field(None, description="Resolved description value")
    active_flag_id: UUID | None = Field(None, description="Flag option identifier")
    flag_ids: list[UUID] = Field(..., description="Flag option identifiers")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    arg_ids: list[UUID] = Field(..., description="Argument identifiers")
    arg_position_ids: list[UUID] = Field(..., description="Argument position identifiers")
    args_output_ids: list[UUID] = Field(..., description="Argument output identifiers")
    args_outputs_ids: list[UUID] = Field(..., description="Legacy alias for argument output identifiers")
    instruction_id: UUID | None = Field(None, description="Instruction resource identifier")
    instruction_ids: list[UUID] = Field(default_factory=list, description="Instruction resource identifiers")
    permission_ids: list[UUID] = Field(..., description="Permission identifiers")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


ToolDraftFormState = DraftFormState


class PatchToolDraftApiResponse(BaseModel):
    """Response model for new-style tool draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    idempotency_key: UUID | None = Field(None, description="Operation key echoed back for client correlation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


class GetToolDraftsApiResponse(BaseModel):
    """Response model for tool drafts list endpoint."""

    entries: list[GetToolDraftResponse] | None = Field(None, description="List of tool draft entries")


# ========== Export Endpoint Types ==========


class ExportToolApiRequest(BaseModel):
    """Request model for tool export."""

    tool_id: UUID | None = Field(None, description="Tool identifier to export")


class ExportToolApiResponse(BaseModel):
    """Response model for export tool endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsToolApiRequest(BaseModel):
    """Request model for tool generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsToolListItem(BaseModel):
    """Single generation group in the tool generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsToolApiResponse(BaseModel):
    """Response model for tool generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsToolListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemToolApiRequest(BaseModel):
    """Request model for tool problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemToolApiResponse(BaseModel):
    """Response model for tool problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
