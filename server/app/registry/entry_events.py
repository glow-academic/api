"""Registry-driven entry generation event types.

Builds Pydantic models from ENTRY_SCHEMAS via create_model().
Single source of truth for socket events + tool output typing.
"""

from pydantic import BaseModel, create_model

from app.registry.entry_schemas import ENTRY_SCHEMAS
from app.registry.resource_events import TYPE_MAP


class EntryGenerationBase(BaseModel):
    """Base fields shared by all entry generation events."""

    artifact_type: str = ""
    entry_type: str = ""
    entry_id: str | None = None
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


def _build_entry_events(
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
        fields["entry_type"] = (str, name)
        cls_name = "".join(w.title() for w in name.split("_")) + "GenerationEvent"
        events[name] = create_model(cls_name, __base__=base, **fields)  # type: ignore[call-overload]
    return events


ENTRY_EVENTS: dict[str, type[EntryGenerationBase]] = _build_entry_events(
    ENTRY_SCHEMAS, EntryGenerationBase
)
