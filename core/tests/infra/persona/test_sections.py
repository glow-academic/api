"""Tests for persona sections — pure response assembly logic."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.infra.persona.sections import build_persona_get_result

pytestmark = pytest.mark.asyncio

_DEPT_ID = uuid4()
_GROUP_ID = uuid4()


class _FakeResource:
    """Minimal resource with id/name fields for testing."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self):
        return self.__dict__.copy()


class _ResourceBucket:
    def __init__(self, selected=None, suggestions=None):
        self.selected = selected or []
        self.suggestions = suggestions or []


@dataclass
class _FakeProfile:
    profiles_id: UUID = field(default_factory=uuid4)
    name: str = "Test User"
    role: str = "admin"
    department_ids: list = field(default_factory=list)
    group_id: UUID = field(default_factory=uuid4)
    session_id: UUID = None
    role_level: int = 1
    role_permissions: list = field(default_factory=lambda: [("persona", "create"), ("persona", "update"), ("persona", "delete"), ("persona", "duplicate"), ("persona", "draft")])


@dataclass
class _FakeCommonContext:
    profile: _FakeProfile = field(default_factory=_FakeProfile)
    tool_graph: object = None


@dataclass
class _FakeToolScore:
    agent_id: UUID = None
    tool_id: UUID = None


@dataclass
class _FakeToolScores:
    best: dict = field(default_factory=dict)
    has_any: dict = field(default_factory=dict)


@dataclass
class _FakePerms:
    exists: bool = True
    department_ids: list = field(default_factory=list)
    active_scenario_count: int = 0


def _make_persona_context(artifact_id=None, draft_version=None):
    """Build a minimal ArtifactContext-like object for persona."""

    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.artifact_id = artifact_id
    ctx.active = True
    ctx.group_id = _GROUP_ID
    ctx.draft_version = draft_version

    # Build resources dict with all needed buckets
    resources = {}
    for key in [
        "names",
        "descriptions",
        "colors",
        "icons",
        "instructions",
        "flags",
        "departments",
        "parameter_fields",
        "examples",
        "parameters",
        "voices",
        "fields",
    ]:
        resources[key] = _ResourceBucket()

    ctx.resources = resources
    return ctx


class TestBuildPersonaGetResult:
    async def test_returns_response_with_no_selected_resources(self):
        """When no resources are selected, response should still be valid."""
        common = _FakeCommonContext()
        persona = _make_persona_context()
        scores = _FakeToolScores()
        perms = _FakePerms()

        result = build_persona_get_result(
            common=common,
            persona=persona,
            scores=scores,
            perms=perms,
            group_id=_GROUP_ID,
        )

        assert result.actor_name == "Test User"
        assert result.persona_exists is False
        assert result.group_id == _GROUP_ID

    async def test_can_edit_reflects_permissions(self):
        """Admin with matching departments and no active scenarios should be able to edit."""
        profile = _FakeProfile(role="superadmin", department_ids=[_DEPT_ID], role_level=0)
        common = _FakeCommonContext(profile=profile)
        persona = _make_persona_context(artifact_id=uuid4())
        scores = _FakeToolScores()
        perms = _FakePerms(department_ids=[_DEPT_ID], active_scenario_count=0)

        result = build_persona_get_result(
            common=common,
            persona=persona,
            scores=scores,
            perms=perms,
            group_id=_GROUP_ID,
        )

        assert result.can_edit is True
        assert result.disabled_reason is None
        assert result.persona_exists is True

    async def test_cannot_edit_when_active_scenarios(self):
        """When persona is linked to active scenarios, editing should be blocked."""
        profile = _FakeProfile(role="admin", department_ids=[_DEPT_ID])
        common = _FakeCommonContext(profile=profile)
        persona = _make_persona_context(artifact_id=uuid4())
        scores = _FakeToolScores()
        perms = _FakePerms(
            department_ids=[_DEPT_ID], active_scenario_count=2
        )

        result = build_persona_get_result(
            common=common,
            persona=persona,
            scores=scores,
            perms=perms,
            group_id=_GROUP_ID,
        )

        assert result.can_edit is False
        assert result.disabled_reason is not None

    async def test_draft_version_passed_through(self):
        """Draft version from persona context should appear in result."""
        common = _FakeCommonContext()
        persona = _make_persona_context(draft_version=5)
        scores = _FakeToolScores()
        perms = _FakePerms()

        result = build_persona_get_result(
            common=common,
            persona=persona,
            scores=scores,
            perms=perms,
            group_id=_GROUP_ID,
        )

        assert result.draft_version == 5

    async def test_show_flags_map_respects_tool_scores(self):
        """When tool scores indicate tools exist, show flags should reflect it."""
        common = _FakeCommonContext()
        persona = _make_persona_context()
        scores = _FakeToolScores(
            has_any={"names": True, "colors": True, "icons": True, "instructions": True}
        )
        perms = _FakePerms()

        result = build_persona_get_result(
            common=common,
            persona=persona,
            scores=scores,
            perms=perms,
            group_id=_GROUP_ID,
        )

        # names show is True always for persona
        assert result.names.show is True
        # descriptions always shown
        assert result.descriptions.show is True
