from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.rubric_drafts.types import GetRubricDraftResponse


class RubricNameResource(BaseModel):
    """Name resource for rubric."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class RubricDescriptionResource(BaseModel):
    """Description resource for rubric."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class RubricFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'rubric_active', 'simulation_rubric', 'video_rubric')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class RubricDepartmentResource(BaseModel):
    """Department resource for rubric."""

    department_id: UUID | None = Field(None, description="Department identifier")
    id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    department_ids: list[UUID] = Field(default_factory=list, description="Associated department identifiers")
    setting_ids: list[UUID] = Field(default_factory=list, description="Associated setting identifiers")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class RubricPointResource(BaseModel):
    """Point resource for rubric."""

    id: UUID | None = Field(None, description="Unique identifier")
    value: int | None = Field(None, description="Point value")
    type: str | None = Field(None, description="Point type")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class RubricStandardGroupResource(BaseModel):
    """Standard group resource for rubric."""

    id: UUID | None = Field(None, description="Unique identifier")
    standard_group_id: UUID | None = Field(None, description="Standard group identifier")
    name: str | None = Field(None, description="Standard group name")
    short_name: str | None = Field(None, description="Standard group short name")
    description: str | None = Field(None, description="Standard group description")
    points: int | None = Field(None, description="Total points for this group")
    pass_points: int | None = Field(None, description="Pass points for this group")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class RubricStandardResource(BaseModel):
    """Standard resource for rubric."""

    id: UUID | None = Field(None, description="Unique identifier")
    standard_id: UUID | None = Field(None, description="Standard identifier")
    standard_group_id: UUID | None = Field(None, description="Parent standard group identifier")
    name: str | None = Field(None, description="Standard name")
    description: str | None = Field(None, description="Standard description")
    points: int | None = Field(None, description="Points for this standard")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(
        None,
        description="Reserved for compatibility with shared filter parsing",
    )


class GetRubricApiRequest(BaseModel):
    """Request model for get rubric endpoint."""

    id: UUID | None = Field(None, description="Rubric UUID to retrieve")
    rubric_id: UUID | None = Field(None, description="Legacy rubric UUID to retrieve")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    points: SectionFilter | None = Field(None, description="Filter options for points section")
    standard_groups: SectionFilter | None = Field(None, description="Filter options for standard groups section")
    standards: SectionFilter | None = Field(None, description="Filter options for standards section")


class GetRubricApiResponse(BaseModel):
    """Canonical flat composed response for the rubric editor."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    rubric_exists: bool | None = Field(None, description="Whether the rubric exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Associated group UUID")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    show_ai_generate: bool | None = Field(None, description="Whether any section supports AI generation")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for the basic step")
    content_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for the content step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[RubricNameResource] | None = Field(None, description="Name resources")
    descriptions: list[RubricDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[RubricFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[RubricDepartmentResource] | None = Field(None, description="Department resources")
    points: list[RubricPointResource] | None = Field(None, description="Point resources")
    standard_groups: list[RubricStandardGroupResource] | None = Field(None, description="Standard group resources")
    standards: list[RubricStandardResource] | None = Field(None, description="Standard resources")


class GetRubricDraftsApiRequest(BaseModel):
    """Request model for the rubric drafts list endpoint.

    Mirrors ``GenerationsRubricApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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


class CreateRubricItem(ScopedItem):
    """Single rubric item for create — no rubric_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_ids": "flags",
        "active": "flags",
        "simulation_rubric": "flags",
        "video_rubric": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "pass_points_id": "points",
        "pass_points": "points",
        "standard_group_ids": "standard_groups",
        "standard_ids": "standards",
    }

    id: UUID | None = Field(None, description="Optional pre-assigned UUID for the new rubric")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="REQUIRED FOR CREATE (or pass `name`): UUID of an existing name resource")
    name: str | None = Field(None, description="REQUIRED FOR CREATE (or pass `name_id`): display name text (creates new resource if name_id not provided)")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of an existing description resource")
    description: str | None = Field(None, description="Rubric description text (creates new resource if description_id not provided)")
    # Canonical flag state — ids of selected flag-resource rows spanning
    # rubric_active, simulation_rubric, video_rubric. Denormalized booleans
    # below are resolved to flag_ids entries server-side.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized rubric_active flag state; resolved to a flag_ids entry server-side")
    simulation_rubric: bool | None = Field(None, description="Denormalized simulation_rubric flag state; resolved to a flag_ids entry server-side")
    video_rubric: bool | None = Field(None, description="Denormalized video_rubric flag state; resolved to a flag_ids entry server-side")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Pass points — dual-mode (value or ID). `pass_points` resolves to a
    # pass-type Points resource and is junctioned as `pass_points_id`. Total
    # is derived server-side from standard groups; not writeable.
    pass_points_id: UUID | None = Field(None, description="Pass-type Points resource UUID")
    pass_points: int | None = Field(None, description="Pass points value (resolves to a pass-type Points resource)")
    standard_group_ids: list[UUID] | None = Field(None, description="Standard group UUIDs")
    standard_ids: list[UUID] | None = Field(None, description="Standard UUIDs")


class CreateRubricApiRequest(BaseModel):
    """Request model for bulk create rubric endpoint."""

    rubrics: list[CreateRubricItem] = Field(..., description="List of rubrics to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateRubricApiResponse(BaseModel):
    """Response model for bulk create rubric endpoint."""

    results: list[RubricResultItem] = Field(..., description="List of operation results")
    # Hydrated rows for the freshly-created rubrics — same shape as
    # ``/rubric/search`` returns. Lets the client's ghost rail
    # materialize the new rows directly from the audit ``.completed``
    # payload, no ``router.refresh()`` needed. Skipped on soft writes
    # (the dormant artifact isn't fully active until ack-accept).
    rubrics: list["ListRubricApiRubric"] | None = Field(None, description="Hydrated rubric rows for the rubrics just created (omitted on soft writes)")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateRubricItem(ScopedItem):
    """Single rubric item for update — rubric_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateRubricItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="Rubric UUID to update")  # Required — which rubric to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Canonical flag state — ids of selected flag-resource rows spanning
    # rubric_active, simulation_rubric, video_rubric. Denormalized booleans
    # below are resolved to flag_ids entries server-side.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized rubric_active flag state; resolved to a flag_ids entry server-side")
    simulation_rubric: bool | None = Field(None, description="Denormalized simulation_rubric flag state; resolved to a flag_ids entry server-side")
    video_rubric: bool | None = Field(None, description="Denormalized video_rubric flag state; resolved to a flag_ids entry server-side")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Pass points — dual-mode (value or ID). Total is derived server-side.
    pass_points_id: UUID | None = Field(None, description="Pass-type Points resource UUID")
    pass_points: int | None = Field(None, description="Pass points value (resolves to a pass-type Points resource)")
    standard_group_ids: list[UUID] | None = Field(None, description="Standard group UUIDs")
    standard_ids: list[UUID] | None = Field(None, description="Standard UUIDs")


class UpdateRubricPatch(UpdateRubricItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateRubricItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved rubric id per matched row",
    )


class UpdateRubricApiRequest(BaseModel):
    """Request model for bulk update rubric endpoint.

    Three body shapes:
      - First call (explicit): ``rubrics`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/rubric/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    rubrics: list[UpdateRubricItem] | None = Field(
        None, description="List of rubrics to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteRubricApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every rubric matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateRubricPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    # Filter fields (same shape as /rubric/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``rubrics`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    simulation_search: str | None = Field(None, description="Search text for simulation facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateRubricApiResponse(BaseModel):
    """Response model for bulk update rubric endpoint."""

    results: list[RubricResultItem] = Field(..., description="List of operation results")
    # Hydrated rows for the updated rubrics — same shape as
    # ``/rubric/search`` returns. Lets the client's ghost rail refresh
    # the changed rows directly from the audit ``.completed`` payload.
    # Skipped on soft writes.
    rubrics: list["ListRubricApiRubric"] | None = Field(None, description="Hydrated rubric rows for the rubrics just updated (omitted on soft writes)")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveRubricFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class DeleteRubricApiRequest(BaseModel):
    """Request model for bulk delete rubric endpoint.

    Three body shapes:
      - First call (explicit): ``rubric_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/rubric/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    rubric_ids: list[UUID] | None = Field(
        None, description="Rubric UUIDs to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchRubricApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every rubric matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /rubric/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``rubric_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    simulation_search: str | None = Field(None, description="Search text for simulation facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool | None = Field(None, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteRubricResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    # Relaxed to optional — under all-matching, soft-skipped rows that
    # didn't resolve to an actual artifact may report a None id. The
    # explicit-ids path always populates this.
    rubric_id: UUID | None = Field(None, description="Rubric UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteRubricApiResponse(BaseModel):
    """Response model for bulk delete rubric endpoint."""

    results: list[DeleteRubricResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateRubricApiRequest(BaseModel):
    rubric_id: UUID = Field(..., description="Rubric UUID to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateRubricApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation succeeded")
    rubric_id: UUID = Field(..., description="Newly created rubric UUID")
    message: str = Field(..., description="Human-readable result message")
    # Hydrated row for the freshly-duplicated rubric — kept as a list
    # for shape consistency with create/update responses (single
    # element). Skipped on soft writes.
    rubrics: list["ListRubricApiRubric"] | None = Field(None, description="Hydrated rubric row for the duplicate (single-element list; omitted on soft writes)")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Draft Endpoint Types (composable infra) ==========


class RubricStandardDraftValue(BaseModel):
    """Value-object for authoring a standard inline from the rubric grid.

    The grid editor sends these instead of (or alongside) standard_ids. Entries
    without an `id` are created server-side; entries with an `id` are trusted
    as-is. Append-only: updates are modeled as create-new-id, old rows become
    orphans and stop appearing in the draft once the client drops them.
    """

    id: UUID | None = Field(None, description="Existing standard UUID, if any")
    name: str = Field(..., description="Level name (column header)")
    description: str = Field("", description="Cell description text")
    points: int = Field(..., description="Implied points from column index")
    standard_group_id: UUID = Field(..., description="Parent standard group UUID (row)")


class RubricStandardGroupDraftValue(BaseModel):
    """Value-object for authoring a standard group inline from the rubric editor.

    Entries without `id` are created server-side; resulting IDs merge into
    standard_group_ids. Group-level `points`/`pass_points` drive the grid's
    column count and passing threshold per row.
    """

    id: UUID | None = Field(None, description="Existing standard group UUID, if any")
    name: str = Field(..., description="Group display name")
    description: str = Field("", description="Group description")
    points: int = Field(0, description="Max points for this group (drives grid columns)")
    pass_points: int = Field(0, description="Passing threshold for this group")


class PatchRubricDraftApiRequest(ScopedItem):
    """Request model for new-style rubric draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
      - standards/standard_ids (grid editor sends value objects; flat IDs also
        accepted for the legacy picker)
    ID-only for non-creatable resources:
      - flag_id, department_ids, point_ids, standard_group_ids

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
        "pass_points_id": "points",
        "pass_points": "points",
        "standard_group_ids": "standard_groups",
        "standard_groups": "standard_groups",
        "standard_ids": "standards",
        "standards": "standards",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to create a resource")
    name_id: UUID | None = Field(None, description="Existing name resource UUID")
    description: str | None = Field(None, description="Description value to create a resource")
    description_id: UUID | None = Field(None, description="Existing description resource UUID")

    # Canonical flag state — ids of the selected flag-resource rows (may span
    # multiple flag types: rubric_active, simulation_rubric, video_rubric).
    flag_ids: list[UUID] | None = Field(
        None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value"
    )
    # Denormalized per-type booleans; resolved to flag_ids entries server-side.
    active: bool | None = Field(None, description="Denormalized rubric_active flag state")
    simulation_rubric: bool | None = Field(None, description="Denormalized simulation_rubric flag state")
    video_rubric: bool | None = Field(None, description="Denormalized video_rubric flag state")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    # Pass points — dual-mode. Total is computed server-side from standard groups
    # and returned on reads; not writeable.
    pass_points_id: UUID | None = Field(None, description="Pass-type Points resource UUID")
    pass_points: int | None = Field(None, description="Pass points value (resolves to a pass-type Points resource)")
    standard_group_ids: list[UUID] | None = Field(None, description="Standard group UUIDs")
    standard_groups: list[RubricStandardGroupDraftValue] | None = Field(
        None,
        description="Inline-created standard groups. Entries without id are created; resulting IDs merge into standard_group_ids.",
    )
    standard_ids: list[UUID] | None = Field(None, description="Standard UUIDs")
    standards: list[RubricStandardDraftValue] | None = Field(
        None,
        description="Grid-editor standards. Entries without id are created; resulting IDs merge into standard_ids.",
    )
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    accept: bool | None = Field(None, description="Accept or reject dormant state")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    name: str | None = Field(None, description="Echoed name value")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    description: str | None = Field(None, description="Echoed description value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed rubric_active flag state")
    simulation_rubric: bool | None = Field(None, description="Echoed simulation_rubric flag state")
    video_rubric: bool | None = Field(None, description="Echoed video_rubric flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Selected department UUIDs")
    # Pass points (normalized + denormalized). Total points are computed
    # server-side from standard groups and exposed on reads alongside.
    pass_points_id: UUID | None = Field(None, description="Pass-type Points resource UUID")
    pass_points: int | None = Field(None, description="Denormalized pass points value")
    total_points_id: UUID | None = Field(None, description="Total-type Points resource UUID (computed)")
    total_points: int | None = Field(None, description="Denormalized total points value (sum of standard groups)")
    standard_group_ids: list[UUID] = Field(default_factory=list, description="Selected standard group UUIDs")
    standard_groups: list[RubricStandardGroupDraftValue] = Field(
        default_factory=list,
        description="Resolved inline-created standard groups (all ids filled in).",
    )
    standard_ids: list[UUID] = Field(default_factory=list, description="Selected standard UUIDs")
    standards: list[RubricStandardDraftValue] = Field(
        default_factory=list,
        description="Resolved grid-editor standards (all ids filled in).",
    )
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


RubricDraftFormState = DraftFormState


class PatchRubricDraftApiResponse(BaseModel):
    """Response model for new-style rubric draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for this draft operation")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportRubricApiResponse(BaseModel):
    """Response model for export rubric endpoint.

    File modality: the server writes the rendered PDF to disk, registers
    it as a ``files_resource`` row joined to an ``uploads_entry``, and
    returns the ``file_id``. Same shape as every other artifact's export
    — only the upload's ``mime_type`` differs (``application/pdf`` here,
    ``text/csv`` elsewhere).
    """

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of rows in the export (rubric standards)")


class FileDownloadRubricApiRequest(BaseModel):
    """Request model for rubric file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadRubricApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


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
    eval_ids: list[UUID] = Field(default_factory=list, description="Eval artifact UUIDs that reference this rubric (via model_rubrics_resource)")
    is_inactive: bool | None = Field(None, description="Whether the rubric is inactive")
    pending_status: str | None = Field(None, description="Pending soft_calls_entry status (e.g. 'pending')")
    pending_operation: str | None = Field(None, description="Pending operation (create/update/delete/duplicate)")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for ack")


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
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    eval_filter: ListFilterSection | None = Field(None, description="Filter options for evals in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsRubricApiRequest(BaseModel):
    """Request model for rubric generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsRubricListItem(BaseModel):
    """Single generation group in the rubric generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsRubricApiResponse(BaseModel):
    """Response model for rubric generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsRubricListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemRubricApiRequest(BaseModel):
    """Request model for rubric problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemRubricApiResponse(BaseModel):
    """Response model for rubric problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadRubricApiRequest(BaseModel):
    """Request model for rubric text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadRubricApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadRubricApiRequest(BaseModel):
    """Request model for rubric call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadRubricApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# Resolve forward refs to ``ListRubricApiRubric`` on the create / update
# / duplicate response models — those models reference it via string
# because they're declared above the list-endpoint types section.
CreateRubricApiResponse.model_rebuild()
UpdateRubricApiResponse.model_rebuild()
DuplicateRubricApiResponse.model_rebuild()
