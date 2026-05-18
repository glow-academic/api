"""Tests for generation media context helpers."""

from app.infra.generation.media_context import (
    MediaItem,
    has_media_sentinels,
    post_process_media_sentinels,
    wrap_media_entries,
)


class TestMediaItem:
    def test_media_property_emits_sentinel(self):
        item = MediaItem({"files_id": "file-1", "name": "Image"}, "image")
        assert item.media == "[[image:file-1]]"

    def test_media_property_returns_empty_without_files_id(self):
        item = MediaItem({"name": "No file"}, "image")
        assert item.media == ""

    def test_proxies_attribute_and_item_access(self):
        item = MediaItem({"files_id": "file-2", "name": "Doc"}, "file")
        assert item.name == "Doc"
        assert item["name"] == "Doc"
        assert "name" in item

    def test_missing_attribute_raises_attribute_error(self):
        item = MediaItem({"files_id": "file-3"}, "audio")
        try:
            _ = item.name
        except AttributeError as exc:
            assert "MediaItem has no attribute 'name'" == str(exc)
        else:
            raise AssertionError("Expected AttributeError")


class TestWrapMediaEntries:
    def test_wraps_only_supported_media_entry_lists(self):
        context = {
            "artifacts": {
                "agent": {
                    "generate": {
                        "entries": {
                            "images": [{"files_id": "img-1", "name": "Image 1"}],
                            "messages": [{"id": "msg-1"}],
                        }
                    }
                }
            }
        }

        result = wrap_media_entries(context)

        assert isinstance(
            result["artifacts"]["agent"]["generate"]["entries"]["images"][0], MediaItem
        )
        assert result["artifacts"]["agent"]["generate"]["entries"]["messages"] == [
            {"id": "msg-1"}
        ]

    def test_ignores_missing_or_invalid_artifact_shapes(self):
        assert wrap_media_entries({}) == {}
        assert wrap_media_entries({"artifacts": []}) == {"artifacts": []}


class TestPostProcessMediaSentinels:
    def test_returns_single_text_block_without_sentinels(self):
        assert post_process_media_sentinels("hello") == [
            {"type": "text", "text": "hello"}
        ]

    def test_returns_empty_for_blank_text_without_sentinels(self):
        assert post_process_media_sentinels("   ") == []

    def test_splits_text_and_media_blocks(self):
        assert post_process_media_sentinels(
            "Before [[image:file-1]] after [[audio:file-2]] end"
        ) == [
            {"type": "text", "text": "Before"},
            {"type": "image", "files_id": "file-1"},
            {"type": "text", "text": "after"},
            {"type": "audio", "files_id": "file-2"},
            {"type": "text", "text": "end"},
        ]

    def test_filters_media_by_supported_modalities(self):
        assert post_process_media_sentinels(
            "Before [[image:file-1]] after [[audio:file-2]]",
            agent_input_modalities={"audio"},
        ) == [
            {"type": "text", "text": "Before"},
            {"type": "text", "text": "after"},
            {"type": "audio", "files_id": "file-2"},
        ]

    def test_detects_media_sentinels(self):
        assert has_media_sentinels("A [[file:file-1]] B") is True
        assert has_media_sentinels("A plain string") is False
