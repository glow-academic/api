"""Tests for infra upload path helpers."""

from app.infra.upload_paths import ensure_upload_subdir, resolve_upload_path


def test_ensure_upload_subdir_creates_nested_directory(tmp_path):
    folder = ensure_upload_subdir("exports/json", upload_folder=tmp_path)

    assert folder == tmp_path / "exports/json"
    assert folder.exists()
    assert folder.is_dir()


def test_resolve_upload_path_uses_supplied_upload_root(tmp_path):
    path = resolve_upload_path("text/example.txt", upload_folder=tmp_path)

    assert path == tmp_path / "text/example.txt"
