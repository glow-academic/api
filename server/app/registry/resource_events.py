"""Registry-driven resource generation event types.

Builds Pydantic models from RESOURCE_SCHEMAS via create_model().
Single source of truth for socket events + tool output typing.
"""

from pydantic import BaseModel, create_model

from app.registry.resource_schemas import RESOURCE_SCHEMAS

# Registry type string → Python (type, default)
TYPE_MAP: dict[str, tuple] = {
    "text": (str | None, None),
    "int": (int | None, None),
    "float": (float | None, None),
    "bool": (bool | None, None),
    "uuid": (str | None, None),
    "array": (list | None, None),
    "enum": (str | None, None),
    "timestamp": (str | None, None),
    "numeric": (float | None, None),
}


class ResourceGenerationBase(BaseModel):
    """Base fields shared by all resource generation events."""

    artifact_type: str = ""
    resource_type: str = ""
    resource_id: str | None = None
    group_id: str | None = None
    run_id: str | None = None
    success: bool | None = None
    message: str | None = None
    error_stage: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    arguments_delta: str | None = None
    id: str | None = None
    generated: bool | None = None


def _build_resource_events(
    schemas: dict[str, dict[str, str]],
    base: type[BaseModel],
) -> dict[str, type[BaseModel]]:
    """Build one event class per schema entry."""
    events: dict[str, type[BaseModel]] = {}
    for name, schema in schemas.items():
        fields = {
            col: TYPE_MAP[typ]
            for col, typ in schema.items()
            if col not in base.model_fields
        }
        fields["resource_type"] = (str, name)
        cls_name = "".join(w.title() for w in name.split("_")) + "GenerationEvent"
        events[name] = create_model(cls_name, __base__=base, **fields)  # type: ignore[call-overload]
    return events


RESOURCE_EVENTS: dict[str, type[ResourceGenerationBase]] = _build_resource_events(
    RESOURCE_SCHEMAS, ResourceGenerationBase
)
