"""Domain registry package — static metadata for artifacts, relations, and routes."""

from app.registry.artifact_entries import ARTIFACT_ENTRIES
from app.registry.artifact_flags import ARTIFACT_FLAGS
from app.registry.artifact_resources import ARTIFACT_RESOURCES
from app.registry.artifact_roles import ARTIFACT_ROLES
from app.registry.artifact_routes import ARTIFACT_ROUTES
from app.registry.artifact_views import ARTIFACT_VIEWS
from app.registry.artifacts import ARTIFACTS, ArtifactKind, ArtifactMeta
from app.registry.entry_events import ENTRY_EVENTS, EntryGenerationBase
from app.registry.entry_resources import ENTRY_RESOURCES
from app.registry.entry_schemas import ENTRY_SCHEMAS
from app.registry.entry_view_names import ENTRY_VIEW_NAMES
from app.registry.entry_view_schemas import ENTRY_VIEW_SCHEMAS
from app.registry.modalities import (
    ARTIFACT_MODALITIES,
    DEFAULT_OUTPUT_MODALITIES,
    ENTRY_MODALITIES,
    RESOURCE_MODALITIES,
    get_tool_output_modalities,
)
from app.registry.operations import (
    ARTIFACT_OPS,
    ENTRY_OPS,
    RESOURCE_OPS,
    resolve_callable,
)
from app.registry.resource_entries import RESOURCE_ENTRIES
from app.registry.resource_events import RESOURCE_EVENTS, ResourceGenerationBase
from app.registry.resource_output_schemas import RESOURCE_OUTPUT_SCHEMAS
from app.registry.resource_schemas import RESOURCE_SCHEMAS
from app.registry.role_artifacts import ROLE_ARTIFACTS
from app.registry.view_entries import VIEW_ENTRIES
from app.registry.view_resources import VIEW_RESOURCES

__all__ = [
    "ARTIFACT_ENTRIES",
    "ARTIFACT_FLAGS",
    "ARTIFACT_MODALITIES",
    "ARTIFACT_OPS",
    "ARTIFACT_RESOURCES",
    "ARTIFACT_ROLES",
    "ARTIFACT_ROUTES",
    "ARTIFACT_VIEWS",
    "ARTIFACTS",
    "ArtifactKind",
    "ArtifactMeta",
    "DEFAULT_OUTPUT_MODALITIES",
    "ENTRY_EVENTS",
    "ENTRY_MODALITIES",
    "ENTRY_OPS",
    "ENTRY_RESOURCES",
    "ENTRY_SCHEMAS",
    "ENTRY_VIEW_NAMES",
    "ENTRY_VIEW_SCHEMAS",
    "EntryGenerationBase",
    "RESOURCE_ENTRIES",
    "RESOURCE_EVENTS",
    "RESOURCE_MODALITIES",
    "RESOURCE_OPS",
    "RESOURCE_OUTPUT_SCHEMAS",
    "RESOURCE_SCHEMAS",
    "ResourceGenerationBase",
    "ROLE_ARTIFACTS",
    "VIEW_ENTRIES",
    "VIEW_RESOURCES",
    "get_tool_output_modalities",
    "resolve_callable",
]
