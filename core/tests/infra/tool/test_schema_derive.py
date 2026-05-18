"""derive_schema_for_permissions — covers each path a handler can take.

Uses a local INFRA_OPS monkey-patch so tests run without depending on
any specific artifact's current signature.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel, Field

from app.infra.tool import schema_derive
from app.infra.tool.schema_derive import (
    PermissionSchema,
    derive_schema_for_permissions,
)


# ---------------------------------------------------------------------------
# Synthetic handlers that stand in for real INFRA_OPS callables
# ---------------------------------------------------------------------------


async def _kwargs_path_strict(
    pool,
    redis,
    *,
    search: str | None = None,
    page_size: int = 20,
    page_offset: int = 0,
    active: bool = True,
    profile_id: UUID | None = None,     # ctx — should be excluded
    session_id: UUID | None = None,     # ctx — should be excluded
):
    return {}


async def _kwargs_path_varkw(
    pool,
    redis,
    *,
    search: str | None = None,
    profile_id: UUID | None = None,
    **_kwargs,                            # accepts anything — can't statically validate
):
    return {}


class _CreateItem(BaseModel):
    name: str = Field(...)
    description: str | None = None
    department_ids: list[UUID] | None = None


# ---------------------------------------------------------------------------
# Fixtures — stitch the synthetic handlers into INFRA_OPS
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fake_infra_ops(monkeypatch):
    """Register synthetic handlers + item classes for the tests."""

    fake_ops = {
        ("thing", "search"): ("irrelevant", "irrelevant"),
        ("thing", "broad_search"): ("irrelevant", "irrelevant"),
        ("thing", "create"): ("irrelevant", "irrelevant"),
    }

    def fake_resolve_callable(artifact, operation, ops):
        return {
            ("thing", "search"): _kwargs_path_strict,
            ("thing", "broad_search"): _kwargs_path_varkw,
            ("thing", "create"): None,   # structured path — no direct callable
        }.get((artifact, operation))

    def fake_resolve_item_class(artifact, operation):
        return {
            ("thing", "create"): _CreateItem,
        }.get((artifact, operation))

    monkeypatch.setattr(schema_derive, "INFRA_OPS", fake_ops)
    monkeypatch.setattr(schema_derive, "resolve_callable", fake_resolve_callable)
    monkeypatch.setattr(schema_derive, "resolve_item_class", fake_resolve_item_class)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_kwargs_path_exposes_signature_keywords_minus_ctx():
    schema = derive_schema_for_permissions([("thing", "search")])

    assert len(schema.per_permission) == 1
    s = schema.per_permission[0]
    assert s.handler_keyword_params == {"search", "page_size", "page_offset", "active"}
    # ctx not exposed, pool/redis not exposed
    assert "profile_id" not in s.handler_keyword_params
    assert "session_id" not in s.handler_keyword_params
    assert "pool" not in s.handler_keyword_params


def test_routing_outputs_are_always_valid():
    schema = derive_schema_for_permissions([("thing", "search")])
    assert "artifact" in schema.valid_output_keys
    assert "operation" in schema.valid_output_keys


def test_structured_path_exposes_item_class_fields():
    schema = derive_schema_for_permissions([("thing", "create")])

    s = schema.per_permission[0]
    assert s.item_class_fields == {"name", "description", "department_ids"}
    # handler callable returned None — so keyword_params should be empty
    assert s.handler_keyword_params == frozenset()


def test_varkw_handler_short_circuits_validation():
    schema = derive_schema_for_permissions([("thing", "broad_search")])

    assert schema.has_var_kwargs_handler
    # Any output name passes in default (non-strict) mode.
    assert schema.validate_output_keys(["whatever", "pageoffsetttt"]) == []
    # Strict mode validates against the declared signature.
    invalid = schema.validate_output_keys(["whatever"], strict=True)
    assert invalid == ["whatever"]


def test_validate_flags_unknown_output_keys():
    schema = derive_schema_for_permissions([("thing", "search")])
    invalid = schema.validate_output_keys(["search", "page", "page_size"])
    assert invalid == ["page"]      # page is unknown; page_size/search are valid


def test_validate_passes_when_all_outputs_are_valid():
    schema = derive_schema_for_permissions([("thing", "search")])
    assert schema.validate_output_keys(["search", "page_offset", "page_size"]) == []


def test_multi_permission_union_covers_all_paths():
    schema = derive_schema_for_permissions([
        ("thing", "search"),
        ("thing", "create"),
    ])
    valid = schema.valid_output_keys
    assert {"search", "page_offset", "active"}.issubset(valid)      # from kwargs-path
    assert {"name", "description", "department_ids"}.issubset(valid)  # from item class
    assert {"artifact", "operation"}.issubset(valid)                  # routing


def test_field_coverage_maps_fields_to_permissions_that_accept_them():
    schema = derive_schema_for_permissions([
        ("thing", "search"),
        ("thing", "create"),
    ])
    cov = schema.field_coverage()
    assert cov["search"] == frozenset({("thing", "search")})
    assert cov["name"] == frozenset({("thing", "create")})


def test_unknown_permission_is_empty_surface_not_error():
    """A tool with an (artifact, operation) that isn't in INFRA_OPS should
    produce an empty surface, not raise. Tools are still deployable during
    migrations; seed validation catches the dead permission separately."""
    schema = derive_schema_for_permissions([("not_in_ops", "something")])
    s = schema.per_permission[0]
    assert s.handler_keyword_params == frozenset()
    assert s.item_class_fields == frozenset()
    assert not s.accepts_var_kwargs
