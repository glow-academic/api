"""C6-A regression: calls_mv must exclude soft / rejected calls.

calls_mv filtered its JOINED uploads (call_uploads_entry.active,
uploads_entry.active) but NOT its own calls_entry.active, and its only WHERE
predicate (c.run_id IS NOT NULL) is vacuous (run_id is NOT NULL). calls/create
writes `active = not soft`, so un-acked / rejected soft-calls (active = false)
plus their upload file_path / mime_type leaked into this hot read. Every
sibling upload MV (audios/files/images/videos/texts_mv) filters its own
`active = true`; this mirrors that and the D1 attempt_analysis_mv fix.

Modular: builds a real run via the standard create chain, then writes one
active + one soft call (each linked to an upload), refreshes the MV, and asserts
only the active call surfaces and the soft call's upload file_path / mime_type
do not leak — both from the MV directly and via the bypass-MV inline definition
path (get_calls bypass_mv=True), which inlines the MV body and so must also
carry the filter.
"""

import pytest

from app.tools.entries.call_uploads.create import create_call_upload
from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.get import get_calls
from app.tools.entries.calls.refresh import refresh_calls_internal
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


def _created(result):
    return result[0] if isinstance(result, tuple) else result


def _call_id(created):
    return (
        getattr(created, "call_id", None)
        or getattr(created, "id", None)
        or getattr(created, "call", None)
    )


async def _call_with_upload(conn, redis_client, session_id, run_id, *, soft):
    """Create a call (active iff not soft) linked to an upload.

    Returns (call_id, file_path) — CreateUploadResponse only carries the id, so
    we thread back the file_path we wrote (it is the leak-sensitive field).
    """
    created = _created(
        await create_call(
            conn, redis_client, run_id=run_id, session_id=session_id, soft=soft
        )
    )
    call_id = _call_id(created)
    tag = "soft" if soft else "live"
    file_path = f"/secret/{tag}.bin"
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session_id,
        file_path=file_path,
        mime_type=f"application/x-{tag}",
        size=42,
    )
    await create_call_upload(
        conn,
        redis_client,
        call_id=call_id,
        upload_id=upload.id,
        session_id=session_id,
    )
    return call_id, file_path


async def test_mv_excludes_soft_call_and_its_upload(
    conn, redis_client, session_id, run_id
):
    live_id, live_path = await _call_with_upload(
        conn, redis_client, session_id, run_id, soft=False
    )
    soft_id, soft_path = await _call_with_upload(
        conn, redis_client, session_id, run_id, soft=True
    )

    await refresh_calls_internal(conn)

    rows = await conn.fetch(
        "SELECT call_id, file_path, mime_type FROM calls_mv WHERE call_id = ANY($1)",
        [live_id, soft_id],
    )
    ids = {r["call_id"] for r in rows}
    assert live_id in ids
    assert soft_id not in ids

    # The soft call's upload data must not leak through the MV.
    leaked_paths = {r["file_path"] for r in rows}
    assert soft_path not in leaked_paths
    assert live_path in leaked_paths


async def test_bypass_mv_inline_definition_also_excludes_soft_call(
    conn, redis_client, session_id, run_id
):
    """The bypass-MV path inlines the MV definition, so it must filter too."""
    live_id, _ = await _call_with_upload(
        conn, redis_client, session_id, run_id, soft=False
    )
    soft_id, soft_path = await _call_with_upload(
        conn, redis_client, session_id, run_id, soft=True
    )

    # bypass_mv inlines the live MV definition; bypass_cache avoids any
    # write-back masking the filter.
    items = await get_calls(
        conn, [live_id, soft_id], redis_client, bypass_mv=True, bypass_cache=True
    )
    ids = {i.id for i in items}
    assert live_id in ids
    assert soft_id not in ids
    assert soft_path not in {i.file_path for i in items}
