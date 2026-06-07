"""Regression: scenario create/update resolves persona/document artifact IDs to resource IDs.

Clients (and ``/persona/search`` / ``/document/search``) surface *artifact* IDs,
but ``scenario_personas_junction.personas_id`` and
``scenario_documents_junction.documents_id`` are FK'd to ``personas_resource`` /
``documents_resource`` (the denormalized snapshot each artifact owns via its own
self-junction), and the scenario read side hydrates them back through the
``*_resource`` getters. Before the fix ``resolve_scenario_values`` passed the
artifact IDs straight into the junction → ForeignKeyViolationError → HTTP 500.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL).
"""

from uuid import uuid4

import pytest

from app.infra.scenario.permissions_context import resolve_scenario_values
from app.infra.scenario.types import CreateScenarioItem
from app.tools.artifacts.document.create import (
    create_document as create_document_artifact,
)
from app.tools.artifacts.persona.create import (
    create_persona as create_persona_artifact,
)
from app.tools.resources.documents.create import (
    create_document as create_document_resource,
)
from app.tools.resources.personas.create import (
    create_persona as create_persona_resource,
)

pytestmark = pytest.mark.asyncio


async def _seed_persona(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_persona_resource(
            conn, redis_client, name=f"p-{uuid4().hex[:8]}"
        )
        artifact = await create_persona_artifact(conn, persona_ids=[resource.id])
    return artifact.id, resource.id


async def _seed_document(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_document_resource(
            conn, redis_client, name=f"d-{uuid4().hex[:8]}"
        )
        artifact = await create_document_artifact(conn, document_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_persona_document_artifact_ids(pool, redis_client):
    persona_a, persona_r = await _seed_persona(pool, redis_client)
    document_a, document_r = await _seed_document(pool, redis_client)

    item = CreateScenarioItem(
        name="scenario-xref",
        persona_ids=[persona_a],
        document_ids=[document_a],
    )
    errors = await resolve_scenario_values(pool, redis_client, item, is_create=True)

    assert errors == []
    assert item.persona_ids == [persona_r] and persona_a not in item.persona_ids
    assert item.document_ids == [document_r] and document_a not in item.document_ids


async def test_unknown_scenario_cross_artifact_ids_pass_through(pool, redis_client):
    p, d = uuid4(), uuid4()
    item = CreateScenarioItem(name="scenario-xref-2", persona_ids=[p], document_ids=[d])
    errors = await resolve_scenario_values(pool, redis_client, item, is_create=True)

    assert errors == []
    assert item.persona_ids == [p]
    assert item.document_ids == [d]
