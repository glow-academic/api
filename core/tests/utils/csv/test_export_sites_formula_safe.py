"""Class guardrail (G1): every CSV export site must use FormulaSafeWriter.

This is the regression lock for the formula-injection sweep — it fails if any
export module reintroduces a raw ``csv.writer(...)`` (which produces formula-
injectable output) instead of the formula-safe wrapper. It also pins the four
families called out in the bug report (profile/roster, activity, chat,
leaderboard) so they can never silently drop the protection.
"""

from pathlib import Path

import pytest

# core/app — walk every module that writes CSV.
_APP_DIR = Path(__file__).resolve().parents[3] / "app"


def _csv_writing_modules() -> list[Path]:
    """All app modules that emit CSV (call csv.writer / FormulaSafeWriter)."""
    out: list[Path] = []
    for path in _APP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "csv.writer(" in text or "FormulaSafeWriter(" in text:
            # The shared helper itself is allowed to reference csv.writer.
            if path.name == "formula_safe.py":
                continue
            out.append(path)
    return out


def test_some_export_sites_are_discovered() -> None:
    # Sanity: the sweep found the export family (guards against a broken walk).
    mods = _csv_writing_modules()
    assert len(mods) >= 20, f"expected many CSV export sites, found {len(mods)}"


@pytest.mark.parametrize(
    "module",
    _csv_writing_modules(),
    ids=lambda p: str(p.relative_to(_APP_DIR)),
)
def test_export_site_uses_formula_safe_writer(module: Path) -> None:
    text = module.read_text(encoding="utf-8")
    assert (
        "csv.writer(" not in text
    ), f"{module} uses raw csv.writer (formula-injectable); use FormulaSafeWriter"
    assert "FormulaSafeWriter(" in text
    assert "from app.utils.csv.formula_safe import FormulaSafeWriter" in text


@pytest.mark.parametrize(
    "relpath",
    [
        "infra/profile/export.py",  # admin roster (headline G1 site)
        "infra/activity/export.py",  # problem-report free-text messages
        "infra/attempt/chat/export.py",  # chat export
        "infra/leaderboard/export.py",  # leaderboard export
    ],
)
def test_named_high_risk_families_protected(relpath: str) -> None:
    text = (_APP_DIR / relpath).read_text(encoding="utf-8")
    assert "csv.writer(" not in text
    assert "FormulaSafeWriter(" in text
