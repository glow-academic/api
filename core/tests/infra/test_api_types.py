"""Tests for api_types — shared API type definitions."""
import pytest
from uuid import uuid4
from app.infra.api_types import BaseResourceSection, ListFilterOption, ListFilterSection, FilterOption
pytestmark = pytest.mark.asyncio

async def test_base_resource_section_defaults():
    # BaseResourceSection is intentionally a data-only model: display logic
    # (show/required/show_ai_generate) was moved to the client, so the base
    # carries no display fields. It must still instantiate with no args.
    s = BaseResourceSection()
    assert isinstance(s, BaseResourceSection)
    assert not hasattr(s, "show")
    assert not hasattr(s, "required")
    assert not hasattr(s, "show_ai_generate")

async def test_list_filter_option_creation():
    o = ListFilterOption(id="1", name="Test", count=5)
    assert o.id == "1"
    assert o.count == 5

async def test_list_filter_section_from_sql_options():
    options = [{"value": "a", "label": "A", "count": 1}]
    section = ListFilterSection.from_sql_options(options, selected_ids=None, search=None)
    assert len(section.options) == 1
    assert section.options[0].name == "A"

async def test_filter_option():
    fo = FilterOption(value="x", label="X")
    assert fo.value == "x"
