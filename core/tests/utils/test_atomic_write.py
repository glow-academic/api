"""report-20 AU3: ``atomic_write_text`` must replace a file in one atomic step
so a concurrent reader never sees a torn/partial write, and must leave no temp
residue (and never clobber the prior file when the write itself fails).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.utils.atomic_write import atomic_write_text


def _temp_residue(d: Path) -> list[str]:
    return [p.name for p in d.iterdir() if p.name.startswith(".") and p.name.endswith(".tmp")]


def test_writes_and_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "call" / "receipt.json"
    atomic_write_text(target, json.dumps({"v": 1}))
    assert json.loads(target.read_text()) == {"v": 1}

    # Overwrite — full replacement, no merge/append.
    atomic_write_text(target, json.dumps({"v": 2, "extra": True}))
    assert json.loads(target.read_text()) == {"v": 2, "extra": True}


def test_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c.json"
    atomic_write_text(target, "hello")
    assert target.read_text() == "hello"


def test_no_temp_residue_on_success(tmp_path: Path) -> None:
    target = tmp_path / "r.json"
    atomic_write_text(target, "x")
    assert _temp_residue(tmp_path) == []


def test_failure_preserves_prior_file_and_cleans_temp(tmp_path: Path) -> None:
    target = tmp_path / "r.json"
    atomic_write_text(target, "good")

    # Force the write to blow up AFTER the temp file is created (non-encodable
    # surrogate triggers a UnicodeEncodeError inside the temp write).
    with pytest.raises(UnicodeEncodeError):
        atomic_write_text(target, "\udc80")

    # The original file is untouched — os.replace never ran.
    assert target.read_text() == "good"
    # And no temp file was left behind.
    assert _temp_residue(tmp_path) == []
