"""Tests for small websocket type resolution helpers."""

from app.infra.websocket.resolve_entry_type import resolve_entry_type
from app.infra.websocket.resolve_resource_type import resolve_resource_type


class TestResolveEntryType:
    def test_prefers_result_entry_type(self):
        assert (
            resolve_entry_type(
                {"entry_type": "top_level", "result": {"entry_type": "result_level"}}
            )
            == "result_level"
        )

    def test_falls_back_to_top_level_entry_type(self):
        assert resolve_entry_type({"entry_type": "messages"}) == "messages"

    def test_returns_none_when_no_entry_type_present(self):
        assert resolve_entry_type({"result": {}}) is None


class TestResolveResourceType:
    def test_prefers_result_resource_type(self):
        assert (
            resolve_resource_type(
                {
                    "resource_type": "top_level",
                    "result": {"resource_type": "departments"},
                }
            )
            == "departments"
        )

    def test_applies_aliases(self):
        assert resolve_resource_type({"resource_type": "fields"}) == "parameter_fields"

    def test_returns_none_when_no_resource_type_present(self):
        assert resolve_resource_type({"result": {}}) is None
