"""Integration tests for infra.persona_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.persona.context import (
    PERSONA_FLAG_TYPES,
    _merge_junction_ids,
    resolve_persona_context,
)
from app.infra.types import ResourcePair
from app.tools.artifacts.persona.create import create_persona
from app.tools.artifacts.persona.update import update_persona


def _artifact_stub(**overrides):
    defaults = {
        "name_ids": [],
        "description_ids": [],
        "color_ids": [],
        "icon_ids": [],
        "instruction_ids": [],
        "flag_ids": [],
        "department_ids": [],
        "parameter_field_ids": [],
        "example_ids": [],
        "voice_ids": [],
    }
    defaults.update(overrides)
    return type("ArtifactStub", (), defaults)()


def _draft_stub(**overrides):
    defaults = {
        "name_ids": [],
        "description_ids": [],
        "color_ids": [],
        "icon_ids": [],
        "instruction_ids": [],
        "flag_ids": [],
        "department_ids": [],
        "parameter_field_ids": [],
        "example_ids": [],
        "voice_ids": [],
    }
    defaults.update(overrides)
    return type("DraftStub", (), defaults)()


class TestMergeJunctionIds:
    def test_artifact_only(self):
        name_id = uuid4()
        dept_id = uuid4()

        result = _merge_junction_ids(
            _artifact_stub(name_ids=[name_id], department_ids=[dept_id]),
            None,
        )

        assert result.name_ids == [name_id]
        assert result.department_ids == [dept_id]

    def test_draft_overrides_single_select(self):
        published_name = uuid4()
        draft_name = uuid4()

        result = _merge_junction_ids(
            _artifact_stub(name_ids=[published_name]),
            _draft_stub(name_ids=[draft_name]),
        )

        assert result.name_ids == [draft_name]

    def test_draft_overrides_multi_select(self):
        pub_dept1, pub_dept2 = uuid4(), uuid4()
        draft_dept = uuid4()

        result = _merge_junction_ids(
            _artifact_stub(department_ids=[pub_dept1, pub_dept2]),
            _draft_stub(department_ids=[draft_dept]),
        )

        assert result.department_ids == [draft_dept]

    def test_draft_empty_keeps_published(self):
        name_id = uuid4()

        result = _merge_junction_ids(
            _artifact_stub(name_ids=[name_id]),
            _draft_stub(name_ids=[]),
        )

        assert result.name_ids == [name_id]

    def test_no_artifact_no_draft(self):
        result = _merge_junction_ids(None, None)

        assert result.name_ids == []
        assert result.department_ids == []
        assert result.example_ids == []


@pytest.mark.asyncio
class TestResolvePersonaContext:
    async def test_create_mode_no_artifact_returns_empty_selected_resources(
        self, pool, redis_client
    ):
        group_id = uuid4()

        result = await resolve_persona_context(
            pool,
            redis_client,
            persona_id=None,
            group_id=group_id,
            descriptions_search="definitely-no-match",
        )

        assert result.artifact_id is None
        assert result.group_id == group_id
        assert result.draft_version is None
        assert result.entries == {}
        for pair in result.resources.values():
            assert isinstance(pair, ResourcePair)
            assert isinstance(pair.selected, list)
            assert isinstance(pair.suggestions, list)
        assert result.resources["names"].selected == []
        assert result.resources["descriptions"].selected == []

    async def test_existing_persona_hydrates_published_resources(
        self, pool, redis_client, persona_context_factory
    ):
        fixture = await persona_context_factory()

        result = await resolve_persona_context(
            pool,
            redis_client,
            persona_id=fixture.persona_id,
            group_id=fixture.group_id,
            descriptions_search="no-match-for-selected-check",
        )

        assert result.artifact_id == fixture.persona_id
        assert result.active is True
        assert result.draft_version is None
        assert [item.id for item in result.resources["names"].selected] == [
            fixture.published_name_id
        ]
        assert [item.name for item in result.resources["names"].selected] == [
            fixture.published_name
        ]
        assert [item.id for item in result.resources["descriptions"].selected] == [
            fixture.selected_description_id
        ]
        assert [
            item.description for item in result.resources["descriptions"].selected
        ] == [fixture.selected_description]

    async def test_draft_overrides_published_name(
        self, pool, redis_client, persona_context_factory
    ):
        fixture = await persona_context_factory()

        result = await resolve_persona_context(
            pool,
            redis_client,
            persona_id=fixture.persona_id,
            group_id=fixture.group_id,
            draft_id=fixture.draft_id,
            descriptions_search="no-match-for-draft-check",
        )

        assert result.draft_version == 3
        assert [item.id for item in result.resources["names"].selected] == [
            fixture.draft_name_id
        ]
        assert [item.name for item in result.resources["names"].selected] == [
            fixture.draft_name
        ]

    async def test_selected_and_suggestions_are_separate(
        self, pool, redis_client, persona_context_factory
    ):
        fixture = await persona_context_factory()

        result = await resolve_persona_context(
            pool,
            redis_client,
            persona_id=fixture.persona_id,
            group_id=fixture.group_id,
            descriptions_search=fixture.suggestion_description,
        )

        assert [item.id for item in result.resources["descriptions"].selected] == [
            fixture.selected_description_id
        ]
        suggestion_ids = [
            item.id for item in result.resources["descriptions"].suggestions
        ]
        assert fixture.suggestion_description_id in suggestion_ids
        assert fixture.selected_description_id not in suggestion_ids

    async def test_inactive_artifact_returns_inactive_context(self, pool, redis_client):
        async with pool.acquire() as conn:
            persona = await create_persona(conn)
            await update_persona(conn, persona.id, active=False)

        result = await resolve_persona_context(
            pool,
            redis_client,
            persona_id=persona.id,
            group_id=uuid4(),
        )

        assert result.active is False

    async def test_flag_suggestions_are_filtered_to_persona_types(
        self, pool, redis_client, persona_context_factory
    ):
        fixture = await persona_context_factory()

        result = await resolve_persona_context(
            pool,
            redis_client,
            persona_id=fixture.persona_id,
            group_id=fixture.group_id,
            descriptions_search="no-match-for-flag-test",
        )

        suggestion_types = {
            getattr(flag, "type", None)
            for flag in result.resources["flags"].suggestions
        }
        suggestion_ids = {flag.id for flag in result.resources["flags"].suggestions}

        assert suggestion_types <= PERSONA_FLAG_TYPES
        assert fixture.scenario_flag_id not in suggestion_ids
