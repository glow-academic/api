"""canonical_tool_signature — sketch-level coverage.

Verifies the shape we'd emit for representative (verb, permissions)
cases, not the full seed registry. If these shapes look right, the next
step is wiring up a regenerator that writes tools.py rows.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel, Field

from app.infra.tool import canonical_signature, schema_derive
from app.infra.tool.canonical_signature import canonical_tool_signature


# --- Synthetic handlers + item classes ---------------------------------


async def _persona_search(
    pool,
    redis,
    *,
    search: str | None = None,
    page_size: int = 20,
    page_offset: int = 0,
    profile_id: UUID | None = None,
):
    return {}


async def _scenario_search(
    pool,
    redis,
    *,
    search: str | None = None,
    page_size: int = 20,
    page_offset: int = 0,
    profile_id: UUID | None = None,
):
    return {}


async def _persona_get(
    pool,
    redis,
    *,
    persona_id: UUID,
    profile_id: UUID | None = None,
):
    return {}


class _PersonaCreateItem(BaseModel):
    name: str = Field(...)
    description: str | None = None
    color: str = Field(...)


class _ScenarioCreateItem(BaseModel):
    name: str = Field(...)
    description: str | None = None
    icon: str = Field(...)


class _PersonaUpdateItem(BaseModel):
    id: UUID = Field(...)
    name: str | None = None
    description: str | None = None


# --- Fixture ----------------------------------------------------------


@pytest.fixture(autouse=True)
def _fake_registry(monkeypatch):
    fake_ops = {
        ("persona", "search"): ("_", "_"),
        ("scenario", "search"): ("_", "_"),
        ("persona", "get"): ("_", "_"),
        ("persona", "create"): ("_", "_"),
        ("scenario", "create"): ("_", "_"),
        ("persona", "update"): ("_", "_"),
    }

    def fake_resolve_callable(artifact, operation, ops):
        return {
            ("persona", "search"): _persona_search,
            ("scenario", "search"): _scenario_search,
            ("persona", "get"): _persona_get,
        }.get((artifact, operation))

    def fake_resolve_item_class(artifact, operation):
        return {
            ("persona", "create"): _PersonaCreateItem,
            ("scenario", "create"): _ScenarioCreateItem,
            ("persona", "update"): _PersonaUpdateItem,
        }.get((artifact, operation))

    for mod in (schema_derive, canonical_signature):
        monkeypatch.setattr(mod, "INFRA_OPS", fake_ops, raising=False)
        monkeypatch.setattr(mod, "resolve_callable", fake_resolve_callable, raising=False)
        monkeypatch.setattr(mod, "resolve_item_class", fake_resolve_item_class, raising=False)


# --- Tests ------------------------------------------------------------


def test_single_permission_search_collapses_both_routing_dimensions():
    shape = canonical_tool_signature("search", [("persona", "search")])
    assert shape.artifact_routing == "hardcoded:persona"
    assert shape.operation_routing == "hardcoded:search"
    # Kwargs path — expose handler's params (minus ctx) as args.
    assert set(shape.args) == {"search", "page_size", "page_offset"}
    # All handler params have defaults, so nothing is required.
    assert shape.required_args == ()


def test_single_permission_get_surfaces_required_id():
    shape = canonical_tool_signature("get", [("persona", "get")])
    assert shape.artifact_routing == "hardcoded:persona"
    assert shape.operation_routing == "hardcoded:get"
    assert shape.args == ("persona_id",)
    assert shape.required_args == ("persona_id",)


def test_cross_cutting_search_passes_through_artifact_collapses_operation():
    """Search-Content-style tool: many artifacts, shared operation.
    artifact → passthrough, operation → hardcoded:search."""
    shape = canonical_tool_signature(
        "search",
        [("persona", "search"), ("scenario", "search")],
    )
    assert shape.artifact_routing == "passthrough"
    assert shape.operation_routing == "hardcoded:search"
    # Only params accepted by BOTH handlers land in `args`.
    assert set(shape.args) == {"search", "page_size", "page_offset"}


def test_cross_cutting_create_intersects_required_fields():
    """Create-Content over persona + scenario.
    Both require `name`; `color` only persona, `icon` only scenario —
    neither can be required, but both surface in `partial_coverage`."""
    shape = canonical_tool_signature(
        "create",
        [("persona", "create"), ("scenario", "create")],
    )
    assert shape.artifact_routing == "passthrough"
    assert shape.operation_routing == "hardcoded:create"
    assert "name" in shape.args
    assert "name" in shape.required_args
    # Artifact-specific required fields aren't forced on the LLM.
    assert "color" not in shape.required_args
    assert "icon" not in shape.required_args
    # …but they're surfaced so the caller can decide.
    assert set(shape.partial_coverage) == {"color", "icon"}


def test_cross_cutting_update_has_id_required_when_all_share_it():
    """Only persona update is in this shape — id is required."""
    shape = canonical_tool_signature("update", [("persona", "update")])
    assert shape.artifact_routing == "hardcoded:persona"
    assert shape.operation_routing == "hardcoded:update"
    assert "id" in shape.required_args


def test_empty_permissions_raises():
    with pytest.raises(ValueError):
        canonical_tool_signature("search", [])


# --- validate_tool_outputs ---------------------------------------------

from app.infra.tool.canonical_signature import validate_tool_outputs


def test_validate_clean_when_declared_matches_canonical():
    """Persona Update declaring id + name + description — all fields valid,
    ``id`` is required and present, no partial-coverage outputs."""
    findings = validate_tool_outputs(
        [("persona", "update")],
        ["artifact", "operation", "id", "name", "description"],
    )
    assert findings.is_clean()
    assert findings.to_warnings() == []


def test_validate_catches_missing_required_field():
    """Persona Update without ``id`` — handler would reject at runtime."""
    findings = validate_tool_outputs(
        [("persona", "update")],
        ["artifact", "operation", "name"],
    )
    assert findings.missing_required == ("id",)
    # ``name`` is valid for this item class, ``artifact``/``operation`` are routing.
    assert findings.unknown_outputs == ()


def test_validate_catches_unknown_output():
    """Declared name no handler accepts."""
    findings = validate_tool_outputs(
        [("persona", "get")],
        ["artifact", "operation", "persona_id", "bogus_field"],
    )
    assert findings.unknown_outputs == ("bogus_field",)
    # ``persona_id`` is the required kwarg for this handler — present, so clean there.
    assert findings.missing_required == ()


def test_validate_flags_partial_coverage_declared():
    """Create Content: ``color`` is only accepted by persona, not scenario.
    It's legitimately declared (cross-cutting tool wants color for persona calls)
    but we flag it so the caller knows it's not universal."""
    findings = validate_tool_outputs(
        [("persona", "create"), ("scenario", "create")],
        ["artifact", "operation", "name", "color", "icon"],
    )
    # Both permissions require `name` — it's declared, so required is clean.
    assert findings.missing_required == ()
    assert findings.unknown_outputs == ()
    assert set(findings.partial_coverage_declared) == {"color", "icon"}


def test_validate_empty_permissions_returns_clean():
    """No perms → nothing to validate against."""
    findings = validate_tool_outputs([], ["anything"])
    assert findings.is_clean()
