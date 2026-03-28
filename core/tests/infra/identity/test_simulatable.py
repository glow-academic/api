"""Tests for infra.auth.simulatable."""

from app.infra.identity.simulatable import SIMULATABLE_ROLES


def test_superadmin_can_simulate_all_roles():
    assert SIMULATABLE_ROLES["superadmin"] == {
        "superadmin",
        "admin",
        "instructional",
        "member",
        "guest",
    }


def test_admin_cannot_simulate_superadmin():
    assert "superadmin" not in SIMULATABLE_ROLES["admin"]
    assert SIMULATABLE_ROLES["admin"] == {"instructional", "member", "guest"}


def test_instructional_only_covers_member_and_guest():
    assert SIMULATABLE_ROLES["instructional"] == {"member", "guest"}
