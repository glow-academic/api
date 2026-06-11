"""Handcrafted types for tool artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.infra.shared_types import MAX_BULK_ITEMS, MAX_TEXT_FIELD_LEN
from app.tools.entries.tool_drafts.types import GetToolDraftResponse


class ToolFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'tool_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon")
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


class ToolInstructionResource(BaseModel):
    """Instruction resource for a tool."""

    id: UUID | None = Field(None, description="Instruction resource identifier")
    template: str | None = Field(None, description="Instruction template body")
    name: str | None = Field(None, description="Instruction display name (when present)")
    generated: bool | None = Field(None, description="Whether the instruction was AI-generated")
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


class ToolDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether the department was AI-generated")
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
    instructions: SectionFilter | None = Field(None, description="Filter options for instructions")
    departments: SectionFilter | None = Field(None, description="Filter options for departments")


class GetToolApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    tool_exists: bool | None = Field(None, description="Whether the tool exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Group identifier for the tool")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    tool_id: UUID | None = Field(None, description="Tool identifier")
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    args_show_ai_generate: bool | None = Field(None, description="Show AI generate for args step")
    permissions_show_ai_generate: bool | None = Field(None, description="Show AI generate for permissions step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")

    names: list[ToolNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ToolDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[ToolFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    args: list[ToolArgResource] | None = Field(None, description="Argument resources")
    arg_positions: list[ToolArgPositionResource] | None = Field(None, description="Argument position resources")
    args_outputs: list[ToolArgOutputResource] | None = Field(None, description="Argument output resources")
    permissions: list[ToolPermissionResource] | None = Field(None, description="Permission resources")
    instructions: list[ToolInstructionResource] | None = Field(None, description="Instruction resources (single-select)")
    departments: list[ToolDepartmentResource] | None = Field(None, description="Department resources")


class ListToolApiTool(BaseModel):
    id: UUID | None = Field(None, description="Tool artifact UUID (canonical id; mirrors tool_id)")
    tool_id: UUID | None = Field(None, description="Tool unique identifier")
    name: str | None = Field(None, description="Display name of the tool")
    description: str | None = Field(None, description="Tool description text")
    active: bool | None = Field(None, description="Whether this tool is currently active")
    is_inactive: bool | None = Field(None, description="Whether this tool is inactive (derived from tool_active flag)")
    flag_ids: list[UUID] | None = Field(None, description="Currently selected flag option UUIDs")
    permission_ids: list[UUID] = Field(default_factory=list, description="Permission resource UUIDs assigned to this tool")
    agent_ids: list[UUID] = Field(default_factory=list, description="Agent artifact UUIDs that reference this tool")
    department_ids: list[UUID] = Field(default_factory=list, description="Department resource UUIDs assigned to this tool")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    # Soft-call ledger snapshot — set when this tool has a pending op
    # in ``soft_calls_mv``. Client renders ghost/pending styling when set.
    pending_status: str | None = Field(None, description="Latest soft_calls_mv status: 'pending' / 'accepted' / 'rejected'")
    pending_operation: str | None = Field(None, description="Operation type ('create'|'update'|'delete'|'duplicate') of the pending op")
    pending_call_id: UUID | None = Field(None, description="call_id (idempotency key for ack) of the pending op")


class ListToolApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    tools: list[ListToolApiTool] | None = Field(None, description="List of tool entries")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    creatable_filter: ListFilterSection | None = Field(None, description="Creatable filter options")
    agent_filter: ListFilterSection | None = Field(None, description="Filter options for agents that reference these tools")
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    permissions_filter: ListFilterSection | None = Field(None, description="Filter options for permissions in list UI")
    total_count: int | None = Field(None, description="Total number of tools")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


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


class ToolArgOutputDraftValue(BaseModel):
    """Output-template draft value for an inline-creatable args_outputs row.

    id null → server creates an args_outputs_resource row scoped to the
    enclosing arg's resolved id. id set → row is re-linked unchanged
    (saved rows are immutable on this surface).
    """

    id: UUID | None = Field(None, description="Existing args_outputs_resource id when re-linking")
    name: str = Field(..., description="Output name")
    template: str = Field("", description="Jinja template — variables drawn from the arg's name and any other selected args")


class ToolArgDraftValue(BaseModel):
    """Unified per-arg draft value for the Arguments step card.

    Each entry maps 1:1 to one row of the Arguments list. Position is the
    *index* of the entry — the resolver creates/finds an arg_positions_resource
    row matching (args_id, value=index). Outputs nest under their owning arg.
    Saved rows (id set) stay immutable; the client surfaces them as chips and
    cloning into a fresh draft to edit (Roles pattern).
    """

    id: UUID | None = Field(None, description="Existing args_resource id when re-linking")
    name: str = Field(..., description="Argument name")
    field_type: str = Field("string", description="Argument type (string, number, boolean, array)")
    description: str = Field("", description="Argument description")
    required: bool = Field(False, description="Whether the argument is required")
    default_value: str = Field("", description="Default value")
    outputs: list[ToolArgOutputDraftValue] = Field(default_factory=list, description="Per-arg jinja output templates")


class CreateToolItem(ScopedItem):
    """Single tool item for create — no tool_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Dual-mode: name — REQUIRED FOR CREATE (or pass `tool_id`)
    name_id: UUID | None = Field(None, description="REQUIRED FOR CREATE (or pass `name`): UUID of an existing name resource")
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="REQUIRED FOR CREATE (or pass `name_id`): display name text (creates new resource)")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="UUID of an existing description resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description text value (creates new resource if description_id not provided)")
    # ID-only fields
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    arg_positions_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    args_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    args_outputs_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    args_drafts: list[ToolArgDraftValue] | None = Field(
        None,
        description="Unified per-arg drafts (Arguments step card). When present, the server resolver creates/links each arg + nested outputs + position and fills in args_ids/args_outputs_ids/arg_positions_ids. Mirrors the /tool/draft contract.",
    )
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")
    instruction_id: UUID | None = Field(None, description="Response template instruction resource UUID")
    tool_ids: list[UUID] | None = Field(None, description="Related tool identifiers")

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
        "instruction_id": "instructions",
        "tool_ids": "tools",
    }


class CreateToolApiRequest(BaseModel):
    """Request model for bulk create tool endpoint."""

    tools: list[CreateToolItem] = Field(..., max_length=MAX_BULK_ITEMS, description="List of tools to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateToolApiResponse(BaseModel):
    """Response model for bulk create tool endpoint."""

    results: list[ToolResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # Hydrated rows for the created tools — same shape as ``/tool/search``
    # returns. Lets the client's ghost rail materialize the new row from
    # the audit ``.completed`` payload without a ``router.refresh()``.
    tools: list[ListToolApiTool] | None = Field(
        None, description="Hydrated rows for the created tools (same shape as `/tool/search` returns)"
    )


# ========== Update Endpoint Types ==========


class UpdateToolItem(ScopedItem):
    """Single tool item for update — tool_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    id: UUID = Field(..., description="Target tool identifier to update")
    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description text value")
    # ID-only fields
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    arg_positions_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    args_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    args_outputs_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    args_drafts: list[ToolArgDraftValue] | None = Field(
        None,
        description="Unified per-arg drafts (Arguments step card). When present, the server resolver creates/links each arg + nested outputs + position and fills in args_ids/args_outputs_ids/arg_positions_ids. Mirrors the /tool/draft contract.",
    )
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")
    instruction_id: UUID | None = Field(None, description="Response template instruction resource UUID")
    tool_ids: list[UUID] | None = Field(None, description="Related tool identifiers")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateToolItem.RESOURCE_TYPE_MAP


class UpdateToolPatch(UpdateToolItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateToolItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved tool id per matched row",
    )


class UpdateToolApiRequest(BaseModel):
    """Request model for bulk update tool endpoint.

    Three body shapes:
      - First call (explicit): ``tools`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/tool/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    tools: list[UpdateToolItem] | None = Field(
        None, description="List of tools to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteToolApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every tool matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateToolPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_creatable: list[str] | None = Field(None, description="Filter by creatable flag (no-op for row filtering today; accepted for forward compatibility)")
    filter_agent_ids: list[UUID] | None = Field(None, description="Filter by agent UUIDs that reference these tools (no-op for row filtering today; accepted for forward compatibility)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")
    agent_search: str | None = Field(None, description="Search text for agent facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateToolApiResponse(BaseModel):
    """Response model for bulk update tool endpoint."""

    results: list[ToolResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # Hydrated rows for the updated tools — same shape as ``/tool/search``
    # returns. Lets the client's ghost rail update the live card from the
    # audit ``.completed`` payload without a ``router.refresh()``.
    tools: list[ListToolApiTool] | None = Field(
        None, description="Hydrated rows for the updated tools (same shape as `/tool/search` returns)"
    )


class SaveToolFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class DeleteToolApiRequest(BaseModel):
    """Request model for bulk delete tool endpoint.

    Three body shapes:
      - First call (explicit): ``tool_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/tool/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    tool_ids: list[UUID] | None = Field(
        None, description="List of tool IDs to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchToolApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every tool matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /tool/search). Only meaningful when
    # ``all=true``; the validator does not enforce that today — the
    # impl simply ignores them when ``tool_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_creatable: list[str] | None = Field(None, description="Filter by creatable flag (no-op for row filtering today; accepted for forward compatibility)")
    filter_agent_ids: list[UUID] | None = Field(None, description="Filter by agent UUIDs that reference these tools (no-op for row filtering today; accepted for forward compatibility)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")
    agent_search: str | None = Field(None, description="Search text for agent facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteToolResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    # Relaxed to optional so all-matching soft-skipped not-found rows
    # (where the input id didn't resolve to an actual artifact) can be
    # reported in the response without raising. Explicit-ids path
    # always populates this with a real UUID.
    tool_id: UUID | None = Field(None, description="Deleted tool identifier (None when soft-skipped without resolution)")
    message: str = Field(..., description="Result message")


class DeleteToolApiResponse(BaseModel):
    """Response model for bulk delete tool endpoint."""

    results: list[DeleteToolResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateToolApiRequest(BaseModel):
    tool_id: UUID = Field(..., description="Tool identifier to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateToolApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    tool_id: UUID = Field(..., description="New duplicated tool identifier")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # Single-element list — kept as list for shape consistency with
    # create/update so the client's ghost rail can read
    # ``output.tools`` uniformly.
    tools: list[ListToolApiTool] | None = Field(
        None, description="Hydrated row for the duplicated tool (same shape as `/tool/search` returns)"
    )


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
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")

    # Match / ID-backed fields
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized tool_active flag state; resolved to a flag_ids entry server-side")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    arg_ids: list[UUID] | None = Field(None, description="Argument identifiers")
    args: list[CreateArgInput] | None = Field(None, description="Arguments to create inline")
    arg_position_ids: list[UUID] | None = Field(None, description="Argument position identifiers")
    arg_positions: list[CreateArgPositionInput] | None = Field(None, description="Argument positions to create inline")
    args_output_ids: list[UUID] | None = Field(None, description="Argument output identifiers")
    args_outputs_ids: list[UUID] | None = Field(None, description="Legacy alias for argument output identifiers")
    args_outputs: list[CreateArgsOutputInput] | None = Field(None, description="Argument outputs to create inline")
    args_drafts: list[ToolArgDraftValue] | None = Field(None, description="Unified per-arg drafts for the Arguments step card. When present, takes precedence over the flat arg_ids/arg_position_ids/args_output_ids triple.")
    instruction_id: UUID | None = Field(None, description="Instruction resource identifier")
    instruction_ids: list[UUID] | None = Field(None, description="Instruction resource identifiers")
    permission_ids: list[UUID] | None = Field(None, description="Permission identifiers")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers to preserve")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack semantics")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept or reject acknowledgement when idempotency_key is supplied")

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
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed tool_active flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Department identifiers")
    arg_ids: list[UUID] = Field(..., description="Argument identifiers")
    arg_position_ids: list[UUID] = Field(..., description="Argument position identifiers")
    args_output_ids: list[UUID] = Field(..., description="Argument output identifiers")
    args_outputs_ids: list[UUID] = Field(..., description="Legacy alias for argument output identifiers")
    args_drafts: list[ToolArgDraftValue] = Field(default_factory=list, description="Echoed unified per-arg drafts after resolution (ids filled in, outputs nested)")
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


class GetToolDraftsApiRequest(BaseModel):
    """Request model for the tool drafts list endpoint.

    Mirrors ``GenerationsToolApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GetToolDraftsApiResponse(BaseModel):
    """Response model for tool drafts list endpoint."""

    entries: list[GetToolDraftResponse] | None = Field(None, description="List of tool draft entries")


# ========== Export Endpoint Types ==========


class ExportToolApiRequest(BaseModel):
    """Request model for tool export."""

    tool_id: UUID | None = Field(None, description="Tool identifier to export")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")
    soft: bool = Field(False, description="Stage the export dormant (active=False); ack with accept activates it")
    accept: bool | None = Field(None, description="Ack: True promotes the staged export, False rejects. Only meaningful with idempotency_key")


class ExportToolApiResponse(BaseModel):
    """Response model for export tool endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export CSV")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with `accept` to promote/reject the staged export.")


class FileDownloadToolApiRequest(BaseModel):
    """Request model for tool file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadToolApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


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
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemToolApiResponse(BaseModel):
    """Response model for tool problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# Preview Types — server-side Jinja render for the Arguments step card
# =============================================================================


class ToolPreviewArg(BaseModel):
    """Per-arg shape for preview rendering."""

    name: str = Field(..., description="Argument name (used as the Jinja variable)")
    field_type: str = Field("string", description="Argument type — drives mock-value coercion")
    default_value: str = Field("", description="Fallback if mock value isn't provided")


class ToolPreviewOutput(BaseModel):
    """Per-output shape for preview rendering."""

    name: str = Field(..., description="Output name (echoed in the response)")
    template: str = Field("", description="Jinja template body")


class PreviewToolApiRequest(BaseModel):
    """Render a tool's outputs against mock arg values."""

    args: list[ToolPreviewArg] = Field(default_factory=list, description="Args available as Jinja variables")
    outputs: list[ToolPreviewOutput] = Field(default_factory=list, description="Output templates to render")
    mock: dict[str, str] = Field(default_factory=dict, description="Mock values keyed by arg name")


class ToolPreviewOutputResult(BaseModel):
    """Per-output preview result."""

    name: str = Field(..., description="Output name (echoes the request)")
    compiled: str | None = Field(None, description="Rendered template string when successful")
    error: str | None = Field(None, description="Jinja error message when rendering or parsing failed")


class ToolPreviewArgHint(BaseModel):
    """Per-arg type/usage hint inferred from the templates."""

    name: str = Field(..., description="Argument name")
    used: bool = Field(False, description="Whether any template references this arg")
    filters: list[str] = Field(default_factory=list, description="Jinja filters applied to this arg across templates")


class PreviewToolApiResponse(BaseModel):
    """Response for the tool preview endpoint."""

    outputs: list[ToolPreviewOutputResult] = Field(default_factory=list, description="Rendered output blocks")
    type_hints: list[ToolPreviewArgHint] = Field(default_factory=list, description="Per-arg usage/filter hints")
    undeclared: list[str] = Field(default_factory=list, description="Variable names referenced by templates but not declared in args")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadToolApiRequest(BaseModel):
    """Request model for tool text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadToolApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadToolApiRequest(BaseModel):
    """Request model for tool call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadToolApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
