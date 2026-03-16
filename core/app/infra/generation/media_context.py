"""Media-aware Jinja context wrappers and sentinel post-processing.

Provides `.media` on the 6 canonical media entry types (texts, calls, audios,
images, videos, files).  When a Jinja template references ``{{ item.media }}``,
a sentinel token ``[[<modality>:<files_id>]]`` is emitted.  After rendering,
``post_process_media_sentinels`` splits the rendered string at sentinel
boundaries and produces a multi-part ``content`` list suitable for LLM APIs.

The 6 media modalities and their sentinel types:

    texts  → [[text:<files_id>]]
    calls  → [[call:<files_id>]]
    audios → [[audio:<files_id>]]
    images → [[image:<files_id>]]
    videos → [[video:<files_id>]]
    files  → [[file:<files_id>]]

Resolution of files_id → actual content is handled externally.
"""

from __future__ import annotations

import re
from typing import Any

# The 6 canonical media entry types → modality name
MEDIA_ENTRY_TYPES: dict[str, str] = {
    "texts": "text",
    "calls": "call",
    "audios": "audio",
    "images": "image",
    "videos": "video",
    "files": "file",
}

# Sentinel pattern: [[modality:files_id]]
_SENTINEL_RE = re.compile(r"\[\[(text|call|audio|image|video|file):([^\]]+)\]\]")


class MediaItem:
    """Dict wrapper that adds a ``.media`` property for sentinel emission.

    Proxies all normal dict access so ``{{ item.field }}`` still works in Jinja.
    Only the 6 canonical media entry types should be wrapped with this class.
    """

    __slots__ = ("_data", "_modality")

    def __init__(self, data: dict[str, Any], modality: str) -> None:
        self._data = data
        self._modality = modality

    @property
    def media(self) -> str:
        """Emit a sentinel token for post-processing.

        Returns empty string if no files_id is present (graceful no-op).
        """
        files_id = self._data.get("files_id")
        if not files_id:
            return ""
        return f"[[{self._modality}:{files_id}]]"

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"MediaItem has no attribute '{name}'")

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self) -> Any:
        return iter(self._data)

    def __repr__(self) -> str:
        return f"MediaItem({self._modality}, {self._data!r})"


def wrap_media_entries(context: dict[str, Any]) -> dict[str, Any]:
    """Walk the Jinja context and wrap media entry lists with MediaItem.

    Looks for the 6 canonical entry types anywhere under ``entries`` keys
    in the context tree.  Modifies in place and returns the context.

    Expected structure:
        context["artifacts"][artifact_name][operation]["entries"][entry_type] = [...]
    """
    artifacts = context.get("artifacts")
    if not isinstance(artifacts, dict):
        return context

    for _artifact_name, ops in artifacts.items():
        if not isinstance(ops, dict):
            continue
        for _op_name, op_data in ops.items():
            if not isinstance(op_data, dict):
                continue

            entries = op_data.get("entries")
            if not isinstance(entries, dict):
                continue

            for entry_type, modality in MEDIA_ENTRY_TYPES.items():
                items = entries.get(entry_type)
                if isinstance(items, list):
                    entries[entry_type] = [
                        MediaItem(item, modality) if isinstance(item, dict) else item
                        for item in items
                    ]

    return context


def post_process_media_sentinels(
    rendered: str,
    agent_input_modalities: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Split rendered text at media sentinels into multi-part content blocks.

    Args:
        rendered: The rendered Jinja template string (may contain sentinels).
        agent_input_modalities: Set of modalities the agent's model supports
            as input.  If a sentinel's modality is not in this set, it is
            silently stripped.  If None, all sentinels are resolved.

    Returns:
        A list of content blocks.  If no sentinels are found, returns a
        single text block.  Otherwise returns interleaved text and media
        blocks.

        Text blocks:  {"type": "text", "text": "..."}
        Media blocks: {"type": "<modality>", "files_id": "<id>"}

        Media blocks carry the ``files_id`` for the caller to resolve
        into actual content (base64, URL, etc.) via the external upload
        mechanism.
    """
    if not _SENTINEL_RE.search(rendered):
        # Fast path — no sentinels, return as-is
        return [{"type": "text", "text": rendered}] if rendered.strip() else []

    blocks: list[dict[str, Any]] = []
    last_end = 0

    for match in _SENTINEL_RE.finditer(rendered):
        modality = match.group(1)
        files_id = match.group(2)

        # Text before this sentinel
        text_before = rendered[last_end : match.start()]
        if text_before.strip():
            blocks.append({"type": "text", "text": text_before.strip()})

        # Only include media block if agent supports this input modality
        if agent_input_modalities is None or modality in agent_input_modalities:
            blocks.append({"type": modality, "files_id": files_id})

        last_end = match.end()

    # Text after last sentinel
    text_after = rendered[last_end:]
    if text_after.strip():
        blocks.append({"type": "text", "text": text_after.strip()})

    return blocks


def has_media_sentinels(rendered: str) -> bool:
    """Check if a rendered string contains any media sentinels."""
    return bool(_SENTINEL_RE.search(rendered))
