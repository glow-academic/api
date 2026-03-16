"""artifact_entry_relation (artifact_type → entry_types).

Computed from ARTIFACT_VIEWS × VIEW_ENTRIES.
"""

from __future__ import annotations

from app.registry.artifact_views import ARTIFACT_VIEWS
from app.registry.view_entries import VIEW_ENTRIES

ARTIFACT_ENTRIES: dict[str, list[str]] = {}
for _art, _views in ARTIFACT_VIEWS.items():
    _ents: set[str] = set()
    for _v in _views:
        if _v in VIEW_ENTRIES:
            _ents.update(VIEW_ENTRIES[_v])
    if _ents:
        ARTIFACT_ENTRIES[_art] = sorted(_ents)
