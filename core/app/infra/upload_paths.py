"""Helpers for resolving upload paths without hard-coding global state."""

from pathlib import Path

from app.infra.globals import UPLOAD_FOLDER


def ensure_upload_subdir(subdir: str, *, upload_folder: Path = UPLOAD_FOLDER) -> Path:
    """Create and return an upload subdirectory."""
    folder = upload_folder / subdir
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def resolve_upload_path(
    relative_path: str, *, upload_folder: Path = UPLOAD_FOLDER
) -> Path:
    """Resolve a stored relative upload path against the configured upload root."""
    return upload_folder / relative_path
