"""Tests for canonical scenario section assembly."""

from types import SimpleNamespace
from uuid import uuid4

from app.infra.common_context import CommonContext
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.runs_context import RunsContext
from app.infra.scenario.sections import build_scenario_get_result
from app.infra.tool_graph import ArtifactToolScores, SettingsToolGraph
from app.infra.types import ArtifactContext, ResourcePair


def test_build_scenario_get_result_builds_canonical_response():
    parameter_id = uuid4()
    field_id = uuid4()
    group_id = uuid4()

    common = CommonContext(
        profile=ProfileIdentityContext(
            profiles_id=uuid4(),
            name="Operator",
            role="superadmin",
            role_name="Super Admin",
            role_description="All access",
            role_artifacts=["scenario"],
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

    scenario = ArtifactContext(
        artifact_id=uuid4(),
        active=True,
        group_id=group_id,
        draft_version=3,
        resources={
            "names": ResourcePair(
                selected=[SimpleNamespace(id=uuid4(), name="Triage", generated=False)],
                suggestions=[],
            ),
            "descriptions": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(),
                        description="Triage scenario",
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "problem_statements": ResourcePair(selected=[], suggestions=[]),
            "flags": ResourcePair(selected=[], suggestions=[]),
            "departments": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=uuid4(),
                        name="Nursing",
                        description="Nursing",
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "personas": ResourcePair(selected=[], suggestions=[]),
            "documents": ResourcePair(selected=[], suggestions=[]),
            "parameters": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=parameter_id,
                        name="Mode",
                        description="Mode parameter",
                        document_parameter=False,
                        persona_parameter=False,
                        scenario_parameter=True,
                        video_parameter=False,
                    )
                ],
                suggestions=[],
            ),
            "parameter_fields": ResourcePair(
                selected=[
                    SimpleNamespace(
                        id=field_id,
                        parameter_id=parameter_id,
                        generated=False,
                    )
                ],
                suggestions=[],
            ),
            "objectives": ResourcePair(selected=[], suggestions=[]),
            "images": ResourcePair(selected=[], suggestions=[]),
            "videos": ResourcePair(selected=[], suggestions=[]),
            "questions": ResourcePair(selected=[], suggestions=[]),
            "options": ResourcePair(selected=[], suggestions=[]),
        },
        entries={"files": [], "images": [], "videos": []},
    )

    result = build_scenario_get_result(
        common=common,
        scenario=scenario,
        scores=ArtifactToolScores(best={}, has_any={}),
        perms=None,
        group_id=group_id,
    )

    assert result.actor_name == "Operator"
    assert result.scenario_exists is True
    assert result.draft_version == 3
    assert result.group_id == group_id
    assert result.names.resource is not None
    assert result.names.resource.name == "Triage"
    assert result.departments.current[0].name == "Nursing"
    assert result.parameters.current[0].parameter_id == parameter_id
    assert result.parameter_fields.current[0].field_id == field_id
    assert result.resolved_parameter_ids == [str(parameter_id)]
