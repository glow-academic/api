"""Tests for canonical cohort section assembly."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

from app.infra.common_context import CommonContext
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.runs_context import RunsContext
from app.infra.tool_graph import ArtifactToolScores, SettingsToolGraph
from app.infra.types import ArtifactContext, ResourcePair


def _ensure_cohort_type_packages() -> None:
    main_dir = (
        Path(__file__).resolve().parents[2] / "app" / "routes" / "v5" / "api" / "main"
    )
    artifact_dir = main_dir / "cohort"
    if "app.routes.v5" not in sys.modules:
        package = ModuleType("app.routes.v5")
        package.__path__ = [str(main_dir)]  # type: ignore[attr-defined]
        sys.modules["app.routes.v5"] = package
    if "app.routes.v5.cohort" not in sys.modules:
        package = ModuleType("app.routes.v5.cohort")
        package.__path__ = [str(artifact_dir)]  # type: ignore[attr-defined]
        sys.modules["app.routes.v5.cohort"] = package


def test_build_cohort_get_result_builds_canonical_response():
    _ensure_cohort_type_packages()
    from app.infra.cohort.sections import build_cohort_get_result

    group_id = uuid4()

    common = CommonContext(
        profile=ProfileIdentityContext(
            profiles_id=uuid4(),
            name="Operator",
            role="superadmin",
            role_name="Super Admin",
            role_description="All access",
            role_artifacts=["cohort"],
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

    cohort = ArtifactContext(
        artifact_id=uuid4(),
        active=True,
        group_id=group_id,
        draft_version=4,
        resources={
            "names": ResourcePair(
                selected=[
                    SimpleNamespace(id=uuid4(), name="Fall Cohort", generated=False)
                ],
                suggestions=[],
            ),
            "descriptions": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(),
                        description="Learner group",
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "flags": ResourcePair(selected=[], suggestions=[]),
            "departments": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(), name="Ops", description="Ops", generated=False
                    )
                ],
                suggestions=[],
            ),
            "simulations": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(),
                        name="Simulation A",
                        description="Desc",
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "simulation_positions": ResourcePair(selected=[], suggestions=[]),
            "simulation_availability": ResourcePair(selected=[], suggestions=[]),
            "profiles": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(),
                        name="Jane",
                        description="Desc",
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "profile_personas": ResourcePair(selected=[], suggestions=[]),
            "personas": ResourcePair(selected=[], suggestions=[]),
        },
        entries={},
    )

    result = build_cohort_get_result(
        common=common,
        cohort=cohort,
        scores=ArtifactToolScores(best={}, has_any={}),
        perms=None,
        cohort_id=cohort.artifact_id,
        group_id=group_id,
    )

    assert result.actor_name == "Operator"
    assert result.cohort_exists is True
    assert result.draft_version == 4
    assert result.group_id == group_id
    assert result.names.resource is not None
    assert result.names.resource.name == "Fall Cohort"
    assert result.departments.current[0].name == "Ops"
    assert result.simulations.current[0].name == "Simulation A"
    assert result.profiles.current[0].name == "Jane"
