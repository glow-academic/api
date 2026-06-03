"""Tests for canonical cohort section assembly.

The canonical cohort GET builder migrated from the old section-shaped
``build_cohort_get_result`` (which returned ``Cohort*Section`` wrappers with
``.resource``/``.current``) to the async DB-backed ``get_cohort_impl``, which
emits the flattened ``GetCohortApiResponse`` — each section is now a flat
``list[Cohort*Resource]`` where the currently-selected item carries
``selected=True`` (and suggestions carry ``suggested=True``).

``build_cohort_get_result`` has no remaining callers in ``app/`` and still
constructs the stale ``Cohort*Section`` shape; it is dead, superseded code
(the same situation PR #77 found for the agent ``build_agent_get_result``).

The pure, synchronous assembly primitive shared by the live path is
``app.infra.cohort.get._with_flags``: it takes hydrated resource models plus
the selected/suggested/pending id sets and a transform, validates each row
into the target ``Cohort*Resource`` model, and stamps the ``selected``/
``suggested``/``pending`` booleans that the flat response contract depends on.
These tests exercise that real black-box primitive against the real
``Cohort*Resource`` models and assert the same intent the old section test
protected — that the selected name/description/department/simulation/profile
surface correctly in the canonical response.
"""

from types import SimpleNamespace
from uuid import uuid4

from app.infra.cohort.get import _with_flags
from app.infra.cohort.types import (
    CohortDepartment,
    CohortDescriptionResource,
    CohortNameResource,
    CohortProfile,
    CohortSimulation,
    GetCohortApiResponse,
)

# Default per-section filter: include the section, no selected/suggested
# narrowing. Mirrors the ``effective_filters`` fallback ``get_cohort_impl``
# builds from ``_legacy_section_filter()`` for an unfiltered fetch.
_ALL_INCLUDED = {"include": True}


def test_with_flags_marks_selected_resources() -> None:
    """The shared assembly primitive stamps ``selected`` on the chosen item."""
    selected = SimpleNamespace(id=uuid4(), name="Fall Cohort", generated=False)
    other = SimpleNamespace(id=uuid4(), name="Spring Cohort", generated=False)

    rows = _with_flags(
        items=[selected, other],
        selected_ids={selected.id},
        suggested_ids=set(),
        pending_ids=set(),
        model_cls=CohortNameResource,
        transform=lambda item: {
            "id": item.id,
            "name": item.name,
            "generated": item.generated,
        },
        section="names",
        filters={"names": _ALL_INCLUDED},
    )

    by_name = {row.name: row for row in rows}
    assert by_name["Fall Cohort"].selected is True
    assert by_name["Fall Cohort"].suggested is False
    assert by_name["Fall Cohort"].pending is False
    assert by_name["Spring Cohort"].selected is False


def test_with_flags_marks_suggested_resources() -> None:
    """Suggestions are stamped ``suggested`` without being marked selected."""
    suggested = SimpleNamespace(id=uuid4(), name="AI Cohort", generated=True)

    rows = _with_flags(
        items=[suggested],
        selected_ids=set(),
        suggested_ids={suggested.id},
        pending_ids=set(),
        model_cls=CohortNameResource,
        transform=lambda item: {
            "id": item.id,
            "name": item.name,
            "generated": item.generated,
        },
        section="names",
        filters={"names": _ALL_INCLUDED},
    )

    assert rows[0].suggested is True
    assert rows[0].selected is False


def test_build_cohort_get_result_builds_canonical_response() -> None:
    """The flat canonical response surfaces the selected resources.

    Faithful to the original section test's intent: a selected name
    "Fall Cohort", description "Learner group", department "Ops",
    simulation "Simulation A" and profile "Jane" must be present and
    flagged ``selected`` in the assembled ``GetCohortApiResponse``.
    """
    group_id = uuid4()

    name = SimpleNamespace(id=uuid4(), name="Fall Cohort", generated=False)
    description = SimpleNamespace(
        id=uuid4(), description="Learner group", generated=False
    )
    department = SimpleNamespace(
        id=uuid4(), name="Ops", description="Ops", generated=False
    )
    simulation = SimpleNamespace(
        id=uuid4(), name="Simulation A", description="Desc", generated=False
    )
    profile = SimpleNamespace(
        id=uuid4(), name="Jane", description="Desc", generated=False, mcp=False
    )

    names = _with_flags(
        items=[name],
        selected_ids={name.id},
        suggested_ids=set(),
        pending_ids=set(),
        model_cls=CohortNameResource,
        transform=lambda item: {
            "id": item.id,
            "name": item.name,
            "generated": item.generated,
        },
        section="names",
        filters={"names": _ALL_INCLUDED},
    )
    descriptions = _with_flags(
        items=[description],
        selected_ids={description.id},
        suggested_ids=set(),
        pending_ids=set(),
        model_cls=CohortDescriptionResource,
        transform=lambda item: {
            "id": item.id,
            "description": item.description,
            "generated": item.generated,
        },
        section="descriptions",
        filters={"descriptions": _ALL_INCLUDED},
    )
    departments = _with_flags(
        items=[department],
        selected_ids={department.id},
        suggested_ids=set(),
        pending_ids=set(),
        model_cls=CohortDepartment,
        transform=lambda item: {
            "department_id": item.id,
            "name": item.name,
            "description": item.description,
            "generated": item.generated,
        },
        section="departments",
        filters={"departments": _ALL_INCLUDED},
    )
    simulations = _with_flags(
        items=[simulation],
        selected_ids={simulation.id},
        suggested_ids=set(),
        pending_ids=set(),
        model_cls=CohortSimulation,
        transform=lambda item: {
            "simulation_id": item.id,
            "name": item.name,
            "description": item.description,
            "generated": item.generated,
        },
        section="simulations",
        filters={"simulations": _ALL_INCLUDED},
    )
    profiles = _with_flags(
        items=[profile],
        selected_ids={profile.id},
        suggested_ids=set(),
        pending_ids=set(),
        model_cls=CohortProfile,
        transform=lambda item: {
            "profile_id": item.id,
            "name": item.name,
            "description": item.description,
            "generated": item.generated,
            "mcp": item.mcp,
        },
        section="profiles",
        filters={"profiles": _ALL_INCLUDED},
    )

    response = GetCohortApiResponse(
        actor_name="Operator",
        cohort_exists=True,
        group_id=group_id,
        names=names,
        descriptions=descriptions,
        departments=departments,
        simulations=simulations,
        profiles=profiles,
    )

    assert response.actor_name == "Operator"
    assert response.cohort_exists is True
    assert response.group_id == group_id

    assert response.names is not None
    selected_name = next(n for n in response.names if n.selected)
    assert selected_name.name == "Fall Cohort"

    assert response.descriptions is not None
    selected_description = next(d for d in response.descriptions if d.selected)
    assert selected_description.description == "Learner group"

    assert response.departments is not None
    selected_department = next(d for d in response.departments if d.selected)
    assert selected_department.name == "Ops"

    assert response.simulations is not None
    selected_simulation = next(s for s in response.simulations if s.selected)
    assert selected_simulation.name == "Simulation A"

    assert response.profiles is not None
    selected_profile = next(p for p in response.profiles if p.selected)
    assert selected_profile.name == "Jane"
