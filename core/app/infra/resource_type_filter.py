"""Resource-scoped item base class.

Artifact Create/Update/Draft item types inherit from ScopedItem instead
of BaseModel. This gives them a `scoped(resources)` method that returns
a copy with fields outside the given resource types nulled out.

Usage:

    class CreatePersonaItem(ScopedItem):
        name: str | None = None
        description: str | None = None
        ...

        RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
            "name": "names", "name_id": "names",
            "description": "descriptions", ...
        }

    # In the infra function:
    async def create_persona_impl(..., items, resources=None):
        if resources:
            items = [item.scoped(resources) for item in items]
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import BaseModel


class ScopedItem(BaseModel):
    """Base class for artifact items that support resource-type scoping."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {}

    def scoped(self, resources: list[str]) -> Self:
        """Return a copy with fields outside the given resources nulled out.

        Fields in RESOURCE_TYPE_MAP whose resource type is NOT in the
        resources list are set to None. Structural fields (not in the map)
        are always preserved.
        """
        if not resources or not self.RESOURCE_TYPE_MAP:
            return self

        resources_set = set(resources)
        overrides: dict[str, None] = {}

        for field_name, resource_type in self.RESOURCE_TYPE_MAP.items():
            if resource_type not in resources_set:
                if getattr(self, field_name, None) is not None:
                    overrides[field_name] = None

        if not overrides:
            return self

        return self.model_copy(update=overrides)
