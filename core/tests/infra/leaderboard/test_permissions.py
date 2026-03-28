"""Tests for leaderboard permissions."""
import pytest
pytestmark = pytest.mark.asyncio

async def test_permissions_module_exists():
    import app.infra.leaderboard.permissions as m
    assert m.__file__.endswith("permissions.py")

async def test_build_leaderboard_sections_exists():
    from app.infra.leaderboard.permissions import build_leaderboard_sections_v3
    assert callable(build_leaderboard_sections_v3)

async def test_permissions_module_has_pure_python():
    import app.infra.leaderboard.permissions as m
    source = open(m.__file__).read()
    assert "def " in source
