"""Tests for pure websocket pipeline helpers."""

from app.infra.websocket.pipeline_helpers import aggregate_tool_results


class TestAggregateToolResults:
    def test_collects_resource_and_entry_actions(self):
        resource_actions, entry_actions = aggregate_tool_results(
            [
                {
                    "resource_type": "names",
                    "resource_id": "resource-1",
                    "entry_type": "messages",
                    "entry_id": "entry-1",
                },
                {
                    "result": {
                        "resource_type": "documents",
                        "resource_id": "resource-2",
                        "entry_type": "uploads",
                        "entry_id": "entry-2",
                    }
                },
            ]
        )

        assert resource_actions == {
            "names": {"resource_id": "resource-1"},
            "documents": {"resource_id": "resource-2"},
        }
        assert entry_actions == {
            "messages": [{"entry_id": "entry-1"}],
            "uploads": [{"entry_id": "entry-2"}],
        }

    def test_skips_non_dict_items_and_missing_ids(self):
        resource_actions, entry_actions = aggregate_tool_results(
            [
                "not-a-dict",
                {"resource_type": "names"},
                {"entry_type": "messages"},
                {"result": "not-a-dict"},
            ]
        )

        assert resource_actions == {}
        assert entry_actions == {}

    def test_accumulates_multiple_entries_for_same_type(self):
        _, entry_actions = aggregate_tool_results(
            [
                {"entry_type": "messages", "entry_id": "entry-1"},
                {"result": {"entry_type": "messages", "entry_id": "entry-2"}},
            ]
        )

        assert entry_actions == {
            "messages": [{"entry_id": "entry-1"}, {"entry_id": "entry-2"}]
        }
