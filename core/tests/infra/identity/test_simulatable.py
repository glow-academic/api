"""Tests for infra.identity.simulatable."""

from app.infra.identity.simulatable import SIMULATABLE_ROLES


def test_superadmin_can_simulate_all_roles():
    assert SIMULATABLE_ROLES["Super Administrator"] == {
        "Super Administrator",
        "Administrator",
        "Instructional Staff",
        "GTA",
        "UTA",
        "Guest",
        "Benchmark",
    }


def test_admin_cannot_simulate_superadmin():
    assert "Super Administrator" not in SIMULATABLE_ROLES["Administrator"]
    assert SIMULATABLE_ROLES["Administrator"] == {
        "Instructional Staff",
        "GTA",
        "UTA",
        "Guest",
    }


def test_instructional_only_covers_lesser_roles():
    assert SIMULATABLE_ROLES["Instructional Staff"] == {"GTA", "UTA", "Guest"}
