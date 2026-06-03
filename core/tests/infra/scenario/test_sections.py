"""Tests for canonical scenario section assembly."""

from types import SimpleNamespace
from uuid import uuid4

from app.infra.common_context import CommonContext
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.scenario.sections import build_scenario_get_result
from app.infra.types import ArtifactContext, ResourcePair


def test_build_scenario_get_result_builds_canonical_response() -> None:
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
            request_limit=None,
            request_limit_interval=None,
            is_active=True,
            role_level=0,
            session_id=None,
        ),
    )

    scenario = ArtifactContext(
        artifact_id=uuid4(),
        active=True,
        group_id=group_id,
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
                        parameter_id=parameter_id,
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
            "fields": ResourcePair(selected=[], suggestions=[]),
        },
        entries={"files": [], "images": [], "videos": []},
    )

    result = build_scenario_get_result(
        common=common,
        scenario=scenario,
        perms=None,
        group_id=group_id,
    )

    assert result.actor_name == "Operator"
    assert result.scenario_exists is True
    assert result.group_id == group_id
    # Flat arrays with selected/suggested flags
    assert result.names is not None
    assert len(result.names) == 1
    assert result.names[0].name == "Triage"
    assert result.names[0].selected is True
    # Departments flat list
    selected_depts = [d for d in result.departments if d.selected]
    assert len(selected_depts) == 1
    assert selected_depts[0].name == "Nursing"
    # Parameters flat list
    selected_params = [p for p in result.parameters if p.selected]
    assert len(selected_params) == 1
    assert selected_params[0].parameter_id == parameter_id
    # Parameter fields flat list
    selected_fields = [f for f in result.parameter_fields if f.selected]
    assert len(selected_fields) == 1
    assert selected_fields[0].field_id == field_id
    assert result.resolved_parameter_ids == [str(parameter_id)]
