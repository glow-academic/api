"""Handcrafted types for tool artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import BaseResourceSection, ListFilterSection
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


class ToolNameSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected name resource")
    resources: list | None = Field(None, description="Available name resources")


class ToolDescriptionSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected description resource")
    resources: list | None = Field(None, description="Available description resources")


class ToolFlagSection(BaseResourceSection):
    current: ToolFlagConfig | None = Field(None, description="Currently active flag config")
    resources: list[ToolFlagConfig] | None = Field(None, description="Available flag configs")


class ToolArgSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned arguments")
    resources: list | None = Field(None, description="Available arguments")


class ToolArgOutputSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned argument outputs")
    resources: list | None = Field(None, description="Available argument outputs")


class ToolArgPositionSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned argument positions")
    resources: list | None = Field(None, description="Available argument positions")


class ToolPermissionSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned permissions")
    resources: list | None = Field(None, description="Available permissions")


class GetToolApiRequest(BaseModel):
    tool_id: UUID | None = Field(None, description="Tool unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")


class GetToolApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    tool_exists: bool | None = Field(None, description="Whether the tool exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group identifier for the tool")

    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    args_show_ai_generate: bool | None = Field(None, description="Show AI generate for args step")
    arg_positions_show_ai_generate: bool | None = Field(None, description="Show AI generate for arg positions step")
    args_outputs_show_ai_generate: bool | None = Field(None, description="Show AI generate for args outputs step")

    names: ToolNameSection | None = Field(None, description="Name section with resources")
    descriptions: ToolDescriptionSection | None = Field(None, description="Description section with resources")
    flags: ToolFlagSection | None = Field(None, description="Flag section with configs")
    args: ToolArgSection | None = Field(None, description="Argument section with resources")
    arg_positions: ToolArgPositionSection | None = Field(None, description="Argument position section")
    args_outputs: ToolArgOutputSection | None = Field(None, description="Argument output section")
    permissions: ToolPermissionSection | None = Field(None, description="Permission section with resources")


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
    agent_filter: ListFilterSection | None = Field(None, description="Agent filter options")
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


class CreateToolApiResponse(BaseModel):
    """Response model for bulk create tool endpoint."""

    results: list[ToolResultItem] = Field(..., description="List of operation results")


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


class UpdateToolApiResponse(BaseModel):
    """Response model for bulk update tool endpoint."""

    results: list[ToolResultItem] = Field(..., description="List of operation results")


class SaveToolFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class DeleteToolApiRequest(BaseModel):
    """Request model for bulk delete tool endpoint."""

    tool_ids: list[UUID] = Field(..., description="List of tool IDs to delete")


class DeleteToolResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    tool_id: UUID = Field(..., description="Deleted tool identifier")
    message: str = Field(..., description="Result message")


class DeleteToolApiResponse(BaseModel):
    """Response model for bulk delete tool endpoint."""

    results: list[DeleteToolResult] = Field(..., description="List of deletion results")


class DuplicateToolApiRequest(BaseModel):
    tool_id: UUID = Field(..., description="Tool identifier to duplicate")


class DuplicateToolApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    tool_id: UUID = Field(..., description="New duplicated tool identifier")
    message: str = Field(..., description="Result message")


class PatchToolDraftApiRequest(ScopedItem):
    """Request model for new-style tool draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, arg_ids, arg_position_ids, args_output_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    expected_version: int = Field(0, description="Expected draft version for concurrency")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    arg_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    arg_position_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    args_output_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "department_ids": "departments",
        "arg_ids": "args",
        "arg_position_ids": "arg_positions",
        "args_output_ids": "args_outputs",
        "permission_ids": "permissions",
    }


class ToolDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    flag_ids: list[UUID] = Field(..., description="Flag option identifiers")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    arg_ids: list[UUID] = Field(..., description="Argument identifiers")
    arg_position_ids: list[UUID] = Field(..., description="Argument position identifiers")
    args_output_ids: list[UUID] = Field(..., description="Argument output identifiers")
    permission_ids: list[UUID] = Field(..., description="Permission identifiers")


class PatchToolDraftApiResponse(BaseModel):
    """Response model for new-style tool draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: ToolDraftFormState | None = Field(None, description="Server-authoritative form state")


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
