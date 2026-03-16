"""Handcrafted types for model artifact endpoints.

Section-first API following the gold-standard pattern (REFERENCE.md).
Resources: names, descriptions, values, providers, flags, departments,
modalities, temperature_levels, pricing, reasoning_levels, qualities, voices.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.model.create import CreateModelItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.model_drafts.types import GetModelDraftResponse

# =============================================================================
# Flag Config
# =============================================================================


class ModelFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Option ID to use when enabling")
    show: bool = Field(True, description="Whether to display this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this flag was AI-generated")


# =============================================================================
# GET Endpoint Types — Section-first API
# =============================================================================


class GetModelApiRequest(BaseModel):
    """Request model for get model endpoint."""

    model_id: UUID | None = Field(None, description="Model unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")


class ModelNameSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected name resource")
    resources: list[Any] | None = Field(None, description="Available name resources")


class ModelDescriptionSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected description resource")
    resources: list[Any] | None = Field(None, description="Available description resources")


class ModelValueSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected value resource")
    resources: list[Any] | None = Field(None, description="Available value resources")


class ModelProviderSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected provider resource")
    resources: list[Any] | None = Field(None, description="Available provider resources")


class ModelFlagSection(BaseResourceSection):
    current: list[ModelFlagConfig] | None = Field(None, description="Currently active flag configs")
    resources: list[ModelFlagConfig] | None = Field(None, description="Available flag configs")


class ModelDepartmentSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned departments")
    resources: list[Any] | None = Field(None, description="Available departments")


class ModelModalitySection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned modalities")
    resources: list[Any] | None = Field(None, description="Available modalities")


class ModelTemperatureLevelSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned temperature levels")
    resources: list[Any] | None = Field(None, description="Available temperature levels")


class ModelReasoningLevelSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned reasoning levels")
    resources: list[Any] | None = Field(None, description="Available reasoning levels")


class ModelPricingSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned pricing tiers")
    resources: list[Any] | None = Field(None, description="Available pricing tiers")


class ModelQualitySection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned quality levels")
    resources: list[Any] | None = Field(None, description="Available quality levels")


class ModelVoiceSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned voices")
    resources: list[Any] | None = Field(None, description="Available voices")


class GetModelApiResponse(BaseModel):
    """Section-first response for model editor."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    model_exists: bool | None = Field(None, description="Whether the model exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group identifier for the model")

    # Step-level AI generation flags
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    provider_show_ai_generate: bool | None = Field(None, description="Show AI generate for provider step")
    features_show_ai_generate: bool | None = Field(None, description="Show AI generate for features step")

    # Section-first resources
    names: ModelNameSection | None = Field(None, description="Name section with resources")
    descriptions: ModelDescriptionSection | None = Field(None, description="Description section with resources")
    values: ModelValueSection | None = Field(None, description="Value section with resources")
    providers: ModelProviderSection | None = Field(None, description="Provider section with resources")
    flags: ModelFlagSection | None = Field(None, description="Flag section with configs")
    departments: ModelDepartmentSection | None = Field(None, description="Department section with resources")
    modalities: ModelModalitySection | None = Field(None, description="Modality section with resources")
    temperature_levels: ModelTemperatureLevelSection | None = Field(None, description="Temperature level section")
    pricing: ModelPricingSection | None = Field(None, description="Pricing section with resources")
    reasoning_levels: ModelReasoningLevelSection | None = Field(None, description="Reasoning level section")
    qualities: ModelQualitySection | None = Field(None, description="Quality section with resources")
    voices: ModelVoiceSection | None = Field(None, description="Voice section with resources")


# =============================================================================
# LIST Endpoint Types
# =============================================================================


class ListModelApiModel(BaseModel):
    """Model type for list endpoint with computed permissions."""

    model_id: UUID | None = Field(None, description="Model unique identifier")
    name: str | None = Field(None, description="Display name of the model")
    description: str | None = Field(None, description="Model description text")
    provider_id: UUID | None = Field(None, description="Associated provider identifier")
    provider_name: str | None = Field(None, description="Associated provider display name")
    base_url: str | None = Field(None, description="Base URL for the model API")
    department_ids: list[str] | None = Field(None, description="Associated department identifiers")
    is_inactive: bool | None = Field(None, description="Whether the model is inactive")
    active: bool | None = Field(None, description="Whether the model is currently active")
    image_model: bool | None = Field(None, description="Whether this is an image model")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")


class ListModelApiResponse(BaseModel):
    """Response model for list model endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    models: list[ListModelApiModel] | None = Field(None, description="List of model entries")
    provider_filter: ListFilterSection | None = Field(None, description="Provider filter options")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    agent_filter: ListFilterSection | None = Field(None, description="Agent filter options")
    total_count: int | None = Field(None, description="Total number of models")


# =============================================================================
# Shared Create/Update Types
# =============================================================================


class ModelFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ModelResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    model_id: UUID | None = Field(None, description="Model unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ModelFieldError] | None = Field(None, description="List of field-level errors")


# =============================================================================
# Create Endpoint Types
# =============================================================================


class CreateModelApiRequest(BaseModel):
    """Request model for bulk create model endpoint."""

    models: list[CreateModelItem] = Field(..., description="List of models to create")


class CreateModelApiResponse(BaseModel):
    """Response model for bulk create model endpoint."""

    results: list[ModelResultItem] = Field(..., description="List of operation results")


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateModelItem(BaseModel):
    """Single model item for update — model_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    model_id: UUID = Field(..., description="Target model identifier to update")
    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # ID-only fields
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    modality_ids: list[UUID] | None = Field(None, description="Modality identifiers")
    pricing_ids: list[UUID] | None = Field(None, description="Pricing tier identifiers")
    provider_ids: list[UUID] | None = Field(None, description="Provider identifiers")
    quality_ids: list[UUID] | None = Field(None, description="Quality level identifiers")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] | None = Field(None, description="Temperature level identifiers")
    value_ids: list[UUID] | None = Field(None, description="Value resource identifiers")
    voice_ids: list[UUID] | None = Field(None, description="Voice identifiers")
    model_ids: list[UUID] | None = Field(None, description="Related model identifiers")


class UpdateModelApiRequest(BaseModel):
    """Request model for bulk update model endpoint."""

    models: list[UpdateModelItem] = Field(..., description="List of models to update")


class UpdateModelApiResponse(BaseModel):
    """Response model for bulk update model endpoint."""

    results: list[ModelResultItem] = Field(..., description="List of operation results")


class SaveModelFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


# =============================================================================
# DELETE Endpoint Types (unchanged)
# =============================================================================


class DeleteModelApiRequest(BaseModel):
    """Request model for bulk delete model endpoint."""

    model_ids: list[UUID] = Field(..., description="List of model IDs to delete")


class DeleteModelResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    model_id: UUID = Field(..., description="Deleted model identifier")
    message: str = Field(..., description="Result message")


class DeleteModelApiResponse(BaseModel):
    """Response model for bulk delete model endpoint."""

    results: list[DeleteModelResult] = Field(..., description="List of deletion results")


# =============================================================================
# DUPLICATE Endpoint Types (unchanged)
# =============================================================================


class DuplicateModelApiRequest(BaseModel):
    """Request model for duplicate model endpoint."""

    model_id: UUID = Field(..., description="Model identifier to duplicate")


class DuplicateModelApiResponse(BaseModel):
    """Response model for duplicate model endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    model_id: UUID = Field(..., description="New duplicated model identifier")
    message: str = Field(..., description="Result message")


# =============================================================================
# DRAFT Endpoint Types (composable infra)
# =============================================================================


class PatchModelDraftApiRequest(BaseModel):
    """Request model for new-style model draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, modality_ids, pricing_ids, provider_ids,
        quality_ids, reasoning_level_ids, temperature_level_ids, value_ids, voice_ids

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
    modality_ids: list[UUID] | None = Field(None, description="Modality identifiers")
    pricing_ids: list[UUID] | None = Field(None, description="Pricing tier identifiers")
    provider_ids: list[UUID] | None = Field(None, description="Provider identifiers")
    quality_ids: list[UUID] | None = Field(None, description="Quality level identifiers")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] | None = Field(None, description="Temperature level identifiers")
    value_ids: list[UUID] | None = Field(None, description="Value resource identifiers")
    voice_ids: list[UUID] | None = Field(None, description="Voice identifiers")


class ModelDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    flag_ids: list[UUID] = Field(..., description="Flag option identifiers")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    modality_ids: list[UUID] = Field(..., description="Modality identifiers")
    pricing_ids: list[UUID] = Field(..., description="Pricing tier identifiers")
    provider_ids: list[UUID] = Field(..., description="Provider identifiers")
    quality_ids: list[UUID] = Field(..., description="Quality level identifiers")
    reasoning_level_ids: list[UUID] = Field(..., description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] = Field(..., description="Temperature level identifiers")
    value_ids: list[UUID] = Field(..., description="Value resource identifiers")
    voice_ids: list[UUID] = Field(..., description="Voice identifiers")


class PatchModelDraftApiResponse(BaseModel):
    """Response model for new-style model draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: ModelDraftFormState | None = Field(None, description="Server-authoritative form state")


class GetModelDraftsApiResponse(BaseModel):
    """Response model for model drafts list endpoint."""

    entries: list[GetModelDraftResponse] | None = Field(None, description="List of model draft entries")


# ========== Export Endpoint Types ==========


class ExportModelApiRequest(BaseModel):
    """Request model for model export."""

    model_id: UUID | None = Field(None, description="Model identifier to export")


class ExportModelApiResponse(BaseModel):
    """Response model for export model endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")
