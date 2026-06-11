"""C2 regression — tool ``args_drafts`` persist on create AND update.

``Tool.tsx`` sends ``args_drafts`` (the unified Arguments step card) on
create/update, but before the cross-repo hunt batch only the ``/tool/draft``
model accepted it — so new tools were created with zero arguments and edits
were discarded.

These tests exercise the shared ``resolve_arg_drafts`` black box (now used by
draft + create + update) with deps-as-params: the arg/output/position
``create_*`` resource tools are monkeypatched to id-minting stubs (no DB), so
the test asserts the resolver creates each arg + nested output + position and
returns the merged id triple. A model test confirms the create/update items
now accept the field at all.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

import app.infra.tool.arg_drafts as arg_drafts_mod
from app.infra.tool.arg_drafts import resolve_arg_drafts
from app.infra.tool.types import ToolArgDraftValue, ToolArgOutputDraftValue

pytestmark = pytest.mark.asyncio


class _Row:
    def __init__(self, _id):
        self.id = _id


def _stub_creators(monkeypatch):
    """Patch the resource creators to id-minting stubs; record call counts."""
    calls = {"arg": 0, "output": 0, "position": []}

    async def fake_create_arg(conn, *, name, field_type, redis, **kwargs):
        calls["arg"] += 1
        return _Row(uuid4())

    async def fake_create_args_output(conn, *, args_id, name, redis, **kwargs):
        calls["output"] += 1
        return _Row(uuid4())

    async def fake_create_arg_position(conn, *, args_id, value, redis, **kwargs):
        calls["position"].append(value)
        return _Row(uuid4())

    monkeypatch.setattr(arg_drafts_mod, "create_arg", fake_create_arg)
    monkeypatch.setattr(arg_drafts_mod, "create_args_output", fake_create_args_output)
    monkeypatch.setattr(arg_drafts_mod, "create_arg_position", fake_create_arg_position)
    return calls


async def test_resolve_arg_drafts_creates_args_outputs_positions(monkeypatch):
    calls = _stub_creators(monkeypatch)

    drafts = [
        ToolArgDraftValue(
            name="city",
            field_type="string",
            outputs=[ToolArgOutputDraftValue(name="weather", template="{{ city }}")],
        ),
        ToolArgDraftValue(name="units", field_type="string"),
    ]

    arg_ids, output_ids, pos_ids = await resolve_arg_drafts(
        object(),  # conn unused by the stubs
        None,  # redis
        drafts,
    )

    # Two args created → two arg ids + two positions (index 0, 1).
    assert calls["arg"] == 2
    assert len(arg_ids) == 2
    assert calls["position"] == [0, 1]
    assert len(pos_ids) == 2
    # One nested output created.
    assert calls["output"] == 1
    assert len(output_ids) == 1
    # Resolver back-fills each draft's id in place.
    assert all(d.id is not None for d in drafts)


async def test_resolve_arg_drafts_relinks_saved_rows(monkeypatch):
    """Saved rows (id present) are re-linked, not recreated."""
    calls = _stub_creators(monkeypatch)
    saved_arg = uuid4()

    drafts = [ToolArgDraftValue(id=saved_arg, name="city", field_type="string")]

    arg_ids, _output_ids, pos_ids = await resolve_arg_drafts(object(), None, drafts)

    assert calls["arg"] == 0  # not recreated
    assert arg_ids == [saved_arg]
    assert calls["position"] == [0]  # positions are always (re)created


async def test_create_and_update_tool_items_accept_args_drafts():
    """CreateToolItem / UpdateToolItem must accept args_drafts — the field
    didn't exist on these models before, so the client payload was dropped."""
    from app.infra.tool.types import CreateToolItem, UpdateToolItem

    draft = ToolArgDraftValue(name="city", field_type="string")

    create_item = CreateToolItem(name="weather", args_drafts=[draft])
    assert create_item.args_drafts is not None
    assert create_item.args_drafts[0].name == "city"

    update_item = UpdateToolItem(id=uuid4(), args_drafts=[draft])
    assert update_item.args_drafts is not None
    assert update_item.args_drafts[0].name == "city"
