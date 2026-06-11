"""Cross-repo hunt batch (bug A) — the 8 client-emitted WS command events
that had NO ``sio.on`` handler are now registered and route to the right impl.

The client's WS command channel (``lib/transport/commands-ws.ts``) maps
``/x/y`` → ``emit x.y`` and waits for ``{event}.completed`` / ``{event}.failed``
or a socket ack, timing out after 30s. python-socketio sends NO ack for an
*unhandled* event — so every one of these 8 events was a guaranteed 30s hang
with the op never running.

This test asserts each event is registered in the sio handler registry and
resolves to its canonical handler module.
"""

from __future__ import annotations

import pytest

import app.ws  # noqa: F401  (importing registers every artifact's handlers)
from app.infra.globals import sio

# event -> canonical handler module
EXPECTED = {
    "attempt.chat_complete": "app.ws.attempt.chat.complete",
    "attempt.chat_create": "app.ws.attempt.chat.create",
    "attempt.chat_mute": "app.ws.attempt.chat.mute",
    "test.draft": "app.ws.test.draft",
    "test.grade": "app.ws.test.grade",
    "test.invocation_create": "app.ws.test.invocation.create",
    "test.invocation_run": "app.ws.test.invocation.run",
    "test.next": "app.ws.test.next",
}


@pytest.mark.parametrize("event", list(EXPECTED))
def test_event_is_registered(event: str) -> None:
    assert event in sio.handlers["/"], (
        f"{event} must be registered in the sio handler registry — an "
        f"unhandled event yields no ack and a 30s client hang"
    )


@pytest.mark.parametrize("event,module", list(EXPECTED.items()))
def test_event_resolves_to_canonical_handler(event: str, module: str) -> None:
    handler = sio.handlers["/"][event]
    original = getattr(handler, "__wrapped__", handler)
    assert original.__module__ == module, (
        f"{event} should resolve to {module}, got {original.__module__}"
    )


@pytest.mark.asyncio
async def test_chat_mute_routes_and_enqueues(monkeypatch) -> None:
    """The fire-and-forget mute handler resolves the live session, enforces
    owner-only access, and enqueues a ``mic.set_muted`` control frame — the
    routing the client's mic toggle relies on (and the ack that ends the hang)."""
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    import app.ws.attempt.chat.mute as mute_mod

    profile_id = uuid4()
    chat_id = uuid4()

    async def fake_identity(sid):
        return SimpleNamespace(profile_id=profile_id, session_id=uuid4())

    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    session = SimpleNamespace(profile_id=str(profile_id), inbound_queue=queue)

    monkeypatch.setattr(mute_mod, "resolve_socket_identity", fake_identity)
    monkeypatch.setattr(mute_mod, "get_session_by_chat_id", lambda cid: session)

    await mute_mod.attempt_chat_mute("sid-1", {"chat_id": str(chat_id), "muted": True})

    assert queue.qsize() == 1
    msg = queue.get_nowait()
    assert msg == {"type": "mic.set_muted", "muted": True}


@pytest.mark.asyncio
async def test_chat_mute_rejects_non_owner(monkeypatch) -> None:
    """A socket that is not the live session owner must not mutate mic state."""
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    import app.ws.attempt.chat.mute as mute_mod

    async def fake_identity(sid):
        return SimpleNamespace(profile_id=uuid4(), session_id=uuid4())

    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    session = SimpleNamespace(profile_id=str(uuid4()), inbound_queue=queue)

    monkeypatch.setattr(mute_mod, "resolve_socket_identity", fake_identity)
    monkeypatch.setattr(mute_mod, "get_session_by_chat_id", lambda cid: session)

    await mute_mod.attempt_chat_mute("sid-1", {"chat_id": str(uuid4()), "muted": True})

    assert queue.qsize() == 0
