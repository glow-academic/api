"""Tests for canonical agent section assembly."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

from app.infra.common_context import CommonContext
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.runs_context import RunsContext
from app.infra.tool_graph import ArtifactToolScores, SettingsToolGraph
from app.infra.types import ArtifactContext, ResourcePair


def _ensure_agent_type_packages() -> None:
    main_dir = (
        Path(__file__).resolve().parents[2] / "app" / "routes" / "v5" / "api" / "main"
    )
    artifact_dir = main_dir / "agent"
    if "app.routes.v5" not in sys.modules:
        package = ModuleType("app.routes.v5")
        package.__path__ = [str(main_dir)]  # type: ignore[attr-defined]
        sys.modules["app.routes.v5"] = package
    if "app.routes.v5.agent" not in sys.modules:
        package = ModuleType("app.routes.v5.agent")
        package.__path__ = [str(artifact_dir)]  # type: ignore[attr-defined]
        sys.modules["app.routes.v5.agent"] = package


def test_build_agent_get_result_builds_canonical_response():
    _ensure_agent_type_packages()
    from app.infra.agent.sections import build_agent_get_result

    group_id = uuid4()

    common = CommonContext(
        profile=ProfileIdentityContext(
            profiles_id=uuid4(),
            name="Operator",
            role="superadmin",
            role_name="Super Admin",
            role_description="All access",
            role_artifacts=["agent"],
            primary_email=None,
            emails=[],
            primary_department_id=None,
            department_ids=[],
            settings_id=None,
            requests_per_day=None,
            is_active=True,
            session_id=None,
            group_id=group_id,
        ),
        tool_graph=SettingsToolGraph(tools=[]),
        runs=RunsContext(items=[], total_count=0),
    )

    agent_ctx = ArtifactContext(
        artifact_id=uuid4(),
        active=True,
        group_id=group_id,
        draft_version=2,
        resources={
            "names": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Tutor", generated=False)],
                suggestions=[],
            ),
            "descriptions": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(),
                        description="Helpful tutor",
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "models": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="gpt-x")],
                suggestions=[],
            ),
            "prompts": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Prompt")],
                suggestions=[],
            ),
            "instructions": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Instruction")],
                suggestions=[],
            ),
            "flags": ResourcePair(selected=[], suggestions=[]),
            "departments": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Ops")],
                suggestions=[],
            ),
            "tools": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Search Tool")],
                suggestions=[],
            ),
            "temperature_levels": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Balanced")],
                suggestions=[],
            ),
            "reasoning_levels": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Deep")],
                suggestions=[],
            ),
            "voices": ResourcePair(selected=[], suggestions=[]),
            "qualities": ResourcePair(selected=[], suggestions=[]),
            "rubrics": ResourcePair(selected=[], suggestions=[]),
        },
        entries={},
    )

    result = build_agent_get_result(
        common=common,
        agent_ctx=agent_ctx,
        scores=ArtifactToolScores(best={}, has_any={}),
        perms=None,
        agent_id=agent_ctx.artifact_id,
        group_id=group_id,
    )

    assert result.actor_name == "Operator"
    assert result.agent_exists is True
    assert result.draft_version == 2
    assert result.group_id == group_id
    assert result.names.resource is not None
    assert result.names.resource.name == "Tutor"
    assert result.descriptions.resource is not None
    assert result.descriptions.resource.description == "Helpful tutor"
    assert result.tools.current is not None
    assert result.tools.current[0].name == "Search Tool"
