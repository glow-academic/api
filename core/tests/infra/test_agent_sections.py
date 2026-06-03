"""Tests for canonical agent section assembly.

The canonical agent GET builder migrated from the old section-shaped
``build_agent_get_result`` (which returned ``Agent*Section`` wrappers with
``.resource``/``.current``) to the async DB-backed ``get_agent_impl``, which
emits the flattened ``GetAgentApiResponse`` — each section is now a flat
``list[Agent*Resource]`` where the currently-selected item carries
``selected=True`` (and suggestions carry ``suggested=True``).

The pure, synchronous assembly primitive shared by that path is
``app.infra.agent.get._decorate``: it takes hydrated resource models plus the
selected/suggestion/pending id sets and stamps the ``selected``/``suggested``/
``pending`` booleans that the flat response contract depends on. These tests
exercise that real black-box primitive against the real ``Agent*Resource``
models and assert the same intent the old section test protected — that the
selected name/description/tool surface correctly in the canonical response.
"""

from uuid import uuid4

from app.infra.agent.get import _decorate
from app.infra.agent.types import (
    AgentDescriptionResource,
    AgentNameResource,
    AgentToolResource,
    GetAgentApiResponse,
)


def test_decorate_marks_selected_resources() -> None:
    """The shared assembly primitive stamps ``selected`` on the chosen item."""
    selected_name = AgentNameResource(id=uuid4(), name="Tutor", generated=False)
    other_name = AgentNameResource(id=uuid4(), name="Coach", generated=False)

    decorated = _decorate(
        [selected_name, other_name],
        selected_items=[selected_name],
        suggestions=[],
        pending_ids=set(),
    )

    by_name = {item["name"]: item for item in decorated}
    assert by_name["Tutor"]["selected"] is True
    assert by_name["Tutor"]["suggested"] is False
    assert by_name["Tutor"]["pending"] is False
    assert by_name["Coach"]["selected"] is False


def test_decorate_marks_suggested_resources() -> None:
    """Suggestions are stamped ``suggested`` without being marked selected."""
    suggested_name = AgentNameResource(id=uuid4(), name="Mentor", generated=True)

    decorated = _decorate(
        [suggested_name],
        selected_items=[],
        suggestions=[suggested_name],
        pending_ids=set(),
    )

    assert decorated[0]["suggested"] is True
    assert decorated[0]["selected"] is False


def test_build_agent_get_result_builds_canonical_response() -> None:
    """The flat canonical response surfaces the selected name/description/tool.

    Faithful to the original section test's intent: a selected name "Tutor",
    description "Helpful tutor", and tool "Search Tool" must be present and
    flagged ``selected`` in the assembled ``GetAgentApiResponse``.
    """
    group_id = uuid4()

    name = AgentNameResource(id=uuid4(), name="Tutor", generated=False)
    description = AgentDescriptionResource(
        id=uuid4(), description="Helpful tutor", generated=False
    )
    tool = AgentToolResource(id=uuid4(), name="Search Tool", generated=False)

    response = GetAgentApiResponse(
        actor_name="Operator",
        agent_exists=True,
        group_id=group_id,
        names=[
            AgentNameResource(**item)
            for item in _decorate(
                [name], selected_items=[name], suggestions=[], pending_ids=set()
            )
        ],
        descriptions=[
            AgentDescriptionResource(**item)
            for item in _decorate(
                [description],
                selected_items=[description],
                suggestions=[],
                pending_ids=set(),
            )
        ],
        tools=[
            AgentToolResource(**item)
            for item in _decorate(
                [tool], selected_items=[tool], suggestions=[], pending_ids=set()
            )
        ],
    )

    assert response.actor_name == "Operator"
    assert response.agent_exists is True
    assert response.group_id == group_id

    assert response.names is not None
    selected_name = next(n for n in response.names if n.selected)
    assert selected_name.name == "Tutor"

    assert response.descriptions is not None
    selected_description = next(d for d in response.descriptions if d.selected)
    assert selected_description.description == "Helpful tutor"

    assert response.tools is not None
    selected_tool = next(t for t in response.tools if t.selected)
    assert selected_tool.name == "Search Tool"
