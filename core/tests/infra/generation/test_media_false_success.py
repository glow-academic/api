"""Generation media/tts/stt failures must reach a REAL terminal, not a false
success. The executors emit a modality ``.error`` (clears the FE skeleton) but
used to ``return None`` — the success signal to ``execute_generation`` — so a
provider/validation failure produced a false ``{artifact}.generate.completed``
+ HTTP 200 alongside the ``.error`` (two conflicting terminals). They must
re-raise so the audit wrapper owns a single ``.failed`` and the route 5xx/4xx's
(mirrors the R7 unsupported-modality fix in execute.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.infra.generation.media as media_mod
import app.infra.generation.stt as stt_mod
from app.infra.generation.media import execute_media_dispatch
from app.infra.generation.stt import execute_stt_dispatch

pytestmark = pytest.mark.asyncio


async def _noop_emit(*_a, **_k) -> None:
    return None


def _prepared() -> SimpleNamespace:
    return SimpleNamespace(
        artifact_type="persona",
        group_id=uuid4(),
        run_id=uuid4(),
        profile_id=uuid4(),
        title="t",
        description="d",
        session_id=uuid4(),
    )


async def test_media_dispatch_raises_on_adapter_failure(monkeypatch):
    actions: list[str] = []

    async def fake_emit_modality(emit, modality, action, payload, *, artifact_type=None):
        actions.append(action)

    monkeypatch.setattr(media_mod, "emit_modality_event", fake_emit_modality)

    class _BoomAdapter:
        async def generate(self, **_kw):
            raise RuntimeError("provider 500")

    monkeypatch.setattr(
        "app.infra.websocket.media_lifecycle.get_media_adapter",
        lambda: _BoomAdapter(),
    )

    dispatch = SimpleNamespace(
        output_modalities={"image"},
        resource_types=["images"],
        metadata={},
        file_path=None,
        messages=[{"content": "draw a cat"}],
        llm_config={},
        resource_id=str(uuid4()),
    )

    # Must RE-RAISE (not return None) so the failure reaches a real terminal.
    with pytest.raises(RuntimeError, match="provider 500"):
        await execute_media_dispatch(
            dispatch=dispatch, prepared=_prepared(), sid="s", emit=_noop_emit
        )
    # ...but only AFTER emitting the modality error that clears the FE skeleton.
    assert "error" in actions


async def test_stt_dispatch_raises_on_missing_audios_id(monkeypatch):
    actions: list[str] = []

    async def fake_emit_modality(emit, modality, action, payload, *, artifact_type=None):
        actions.append(action)

    monkeypatch.setattr(stt_mod, "emit_modality_event", fake_emit_modality)

    dispatch = SimpleNamespace(
        audios_id=None,
        resource_types=["texts"],
        llm_config={},
        metadata={},
    )

    with pytest.raises(ValueError, match="audios_id"):
        await execute_stt_dispatch(
            dispatch=dispatch, prepared=_prepared(), sid="s", emit=_noop_emit
        )
    assert "error" in actions
