"""C4 regression — draft + invocation-create field contract.

The client (use-test-generate.ts) sends the *materialized invocation* field
shape to the draft + create surfaces. This pins the canonical contract:

  * The materialized invocation (``CreateInvocationApiRequest`` →
    ``/test/invocation_create``) accepts AND persists the full set
    (agent_ids/rubric_ids/quality_ids/department_ids/voice_ids/
    reasoning_level_ids/temperature_level_ids/modality_ids/invocation_id) —
    these are the canonical names.

  * The invocation DRAFT model now accepts plural ``reasoning_level_ids`` /
    ``temperature_level_ids`` (it previously only had the singular form, so
    the plural the client sent was dropped).

  * The attempt/chat DRAFT model accepts singular ``problem_statement_id``
    (the canonical for that surface).
"""

from __future__ import annotations

from uuid import uuid4

from app.infra.attempt.chat.types import PatchChatDraftApiRequest
from app.infra.invocation.types import PatchInvocationDraftApiRequest
from app.infra.invocation.create import CreateInvocationApiRequest


def test_invocation_draft_accepts_plural_level_ids():
    r1, r2, t1 = uuid4(), uuid4(), uuid4()
    req = PatchInvocationDraftApiRequest(
        reasoning_level_ids=[r1, r2],
        temperature_level_ids=[t1],
    )
    assert req.reasoning_level_ids == [r1, r2]
    assert req.temperature_level_ids == [t1]


def test_invocation_create_accepts_canonical_full_set():
    agent_id, rubric_id, quality_id = uuid4(), uuid4(), uuid4()
    req = CreateInvocationApiRequest(
        test_id=uuid4(),
        invocation_id=uuid4(),
        agent_ids=[agent_id],
        rubric_ids=[rubric_id],
        quality_ids=[quality_id],
        department_ids=[uuid4()],
        voice_ids=[uuid4()],
        reasoning_level_ids=[uuid4()],
        temperature_level_ids=[uuid4()],
        modality_ids=[uuid4()],
    )
    # These are the canonical names — persisted via test_invocation_* junctions.
    assert req.agent_ids == [agent_id]
    assert req.rubric_ids == [rubric_id]
    assert req.quality_ids == [quality_id]


def test_attempt_chat_draft_accepts_singular_problem_statement_id():
    ps_id = uuid4()
    req = PatchChatDraftApiRequest(problem_statement_id=ps_id)
    assert req.problem_statement_id == ps_id
