"""Tests for dashboard metadata builders."""

from types import SimpleNamespace
from uuid import uuid4

from app.infra.dashboard.builders import (
    build_field_meta,
    build_parameter_meta,
    build_rubric_meta,
    build_scenario_meta,
    build_simulation_meta,
)


class TestBuildSimulationMeta:
    def test_builds_simulation_metadata(self):
        simulation_id = uuid4()
        result = build_simulation_meta(
            [
                SimpleNamespace(
                    simulation_id=simulation_id,
                    name="Simulation One",
                    description="Desc",
                    department_ids=[uuid4()],
                )
            ]
        )

        assert result == [
            {
                "simulation_id": str(simulation_id),
                "name": "Simulation One",
                "description": "Desc",
                "department_ids": result[0]["department_ids"],
                "time_limit": None,
            }
        ]


class TestBuildScenarioMeta:
    def test_builds_scenario_metadata(self):
        scenario_id = uuid4()
        assert build_scenario_meta(
            [SimpleNamespace(scenario_id=scenario_id, name="Scenario", description="D")]
        ) == [{"scenario_id": str(scenario_id), "name": "Scenario", "description": "D"}]


class TestBuildRubricMeta:
    def test_builds_rubric_metadata(self):
        rubric_id = uuid4()
        assert build_rubric_meta(
            [SimpleNamespace(rubric_id=rubric_id, name="Rubric", description="D")]
        ) == [{"rubric_id": str(rubric_id), "name": "Rubric", "description": "D"}]


class TestBuildParameterMeta:
    def test_builds_parameter_metadata(self):
        parameter_id = uuid4()
        assert build_parameter_meta(
            [
                SimpleNamespace(
                    parameter_id=parameter_id,
                    name="Parameter",
                    description="D",
                    document_parameter=True,
                    persona_parameter=False,
                )
            ]
        ) == [
            {
                "parameter_id": str(parameter_id),
                "name": "Parameter",
                "description": "D",
                "numerical": None,
                "document_parameter": True,
                "persona_parameter": False,
            }
        ]


class TestBuildFieldMeta:
    def test_builds_field_metadata_with_parameter_resolution(self):
        field_id = uuid4()
        parameter_id = uuid4()

        result = build_field_meta(
            [
                SimpleNamespace(
                    field_id=field_id,
                    name="Field",
                    description="D",
                )
            ],
            {field_id: parameter_id},
            [SimpleNamespace(parameter_id=parameter_id, name="Parameter Name")],
        )

        assert result == [
            {
                "field_id": str(field_id),
                "name": "Field",
                "description": "D",
                "parameter_id": str(parameter_id),
                "parameter_name": "Parameter Name",
            }
        ]

    def test_builds_field_metadata_without_parameter_link(self):
        field_id = uuid4()

        assert build_field_meta(
            [SimpleNamespace(field_id=field_id, name="Field", description="D")],
            {},
            [],
        ) == [
            {
                "field_id": str(field_id),
                "name": "Field",
                "description": "D",
                "parameter_id": None,
                "parameter_name": None,
            }
        ]
