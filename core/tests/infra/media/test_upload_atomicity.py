"""Integrity tests for the media upload chain (E2).

``media_upload_impl`` writes a file to disk and then builds the
uploads -> resource -> entry -> junction (+ optional run bridge) chain. The
hazard: asyncpg autocommits each statement, so a mid-chain failure used to
leave committed sub-rows AND an orphaned on-disk file (the paid provider call
already happened). The fix wraps the DB chain in ``conn.transaction()`` and
unlinks any staged file if the transaction rolls back.

These exercise the real ``pool.acquire() -> conn.transaction()`` path plus the
real filesystem (redirected to a tmp dir) so both the DB rollback AND the file
cleanup are verified for real.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.asyncio


async def _make_session(conn) -> UUID:
    row = await conn.fetchrow(
        "INSERT INTO sessions_entry (active, generated) VALUES (true, true) "
        "RETURNING id"
    )
    return row["id"]


def _redirect_folders(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    """Point the upload module's folder constants at a tmp dir."""
    import app.infra.media.upload as up

    image_folder = tmp_path / "image"
    audio_folder = tmp_path / "audio"
    video_folder = tmp_path / "video"
    for f in (image_folder, audio_folder, video_folder, tmp_path):
        f.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(up, "IMAGE_FOLDER", image_folder)
    monkeypatch.setattr(up, "AUDIO_FOLDER", audio_folder)
    monkeypatch.setattr(up, "VIDEO_FOLDER", video_folder)
    monkeypatch.setattr(up, "UPLOAD_FOLDER", tmp_path)
    # ``_FOLDERS`` is read inside the impl; rebuild it to the redirected paths.
    monkeypatch.setattr(
        up, "_FOLDERS",
        {"audio": audio_folder, "image": image_folder, "video": video_folder},
    )
    return {"image": image_folder, "tmp": tmp_path}


async def test_media_upload_success_writes_file_and_consistent_rows(
    pool, redis_client, monkeypatch, tmp_path
):
    """Happy path: file lands on disk and the row's file_path points at it."""
    import app.infra.media.upload as up

    folders = _redirect_folders(monkeypatch, tmp_path)

    async with pool.acquire() as conn:
        session_id = await _make_session(conn)

    result = await up.media_upload_impl(
        pool,
        redis_client,
        modality="image",
        session_id=session_id,
        file_bytes=b"\x89PNG fake bytes",
        filename="pic.png",
        content_type="image/png",
        name="My Pic",
    )

    # File exists and matches the committed row's file_path.
    on_disk = folders["tmp"] / result.file_path
    assert on_disk.exists(), f"expected file at {on_disk}"
    assert on_disk.read_bytes() == b"\x89PNG fake bytes"
    assert result.file_path.startswith("image/")

    # All rows committed and consistent.
    async with pool.acquire() as conn:
        up_row = await conn.fetchrow(
            "SELECT file_path, active FROM uploads_entry WHERE id = $1",
            result.upload_id,
        )
        assert up_row is not None
        assert up_row["file_path"] == result.file_path
        res_row = await conn.fetchrow(
            "SELECT id FROM images_resource WHERE id = $1", result.resource_id
        )
        assert res_row is not None
        ent_row = await conn.fetchrow(
            "SELECT id FROM images_entry WHERE id = $1", result.entry_id
        )
        assert ent_row is not None
        jct_row = await conn.fetchrow(
            "SELECT upload_id, image_id FROM image_uploads_entry WHERE id = $1",
            result.junction_id,
        )
        assert jct_row is not None
        assert jct_row["upload_id"] == result.upload_id
        assert jct_row["image_id"] == result.entry_id


async def test_media_upload_midchain_failure_rolls_back_and_unlinks(
    pool, redis_client, monkeypatch, tmp_path
):
    """A junction write that raises leaves NO rows and NO orphaned file."""
    import app.infra.media.upload as up

    folders = _redirect_folders(monkeypatch, tmp_path)

    async with pool.acquire() as conn:
        session_id = await _make_session(conn)

    # Capture the upload id the chain mints so we can assert it never committed.
    minted: dict[str, UUID] = {}
    real_create_upload = up.create_upload

    async def spy_create_upload(*args, **kwargs):
        row = await real_create_upload(*args, **kwargs)
        minted.setdefault("upload_id", row.id)
        return row

    monkeypatch.setattr(up, "create_upload", spy_create_upload)

    # Make the LAST sub-write (the junction) blow up — by then the upload,
    # resource and entry rows have all been written within the txn and the
    # file has been staged to disk.
    async def boom(*args, **kwargs):
        raise RuntimeError("simulated junction write failure")

    monkeypatch.setattr(up, "create_image_upload", boom)

    with pytest.raises(RuntimeError, match="simulated junction"):
        await up.media_upload_impl(
            pool,
            redis_client,
            modality="image",
            session_id=session_id,
            file_bytes=b"orphan candidate",
            filename="x.png",
            content_type="image/png",
            name="Doomed",
        )

    # The DB transaction rolled back: the upload row never committed.
    assert "upload_id" in minted, "create_upload should have run before the failure"
    async with pool.acquire() as conn:
        up_row = await conn.fetchrow(
            "SELECT id FROM uploads_entry WHERE id = $1", minted["upload_id"]
        )
        assert up_row is None, "rolled-back upload row must not be committed"
        # No image resource/entry for this session leaked either.
        leaked = await conn.fetchrow(
            "SELECT count(*) AS n FROM images_entry WHERE session_id = $1",
            session_id,
        )
        assert leaked["n"] == 0

    # The staged file was unlinked — no orphaned blob in the image folder.
    leftover = list(folders["image"].glob("*"))
    assert leftover == [], f"expected no orphaned files, found {leftover}"


async def test_media_upload_run_attribution_failure_unlinks_both_files(
    pool, redis_client, monkeypatch, tmp_path
):
    """A failure in the run-bridge branch unlinks the media AND text blobs."""
    import app.infra.media.upload as up

    folders = _redirect_folders(monkeypatch, tmp_path)

    async with pool.acquire() as conn:
        session_id = await _make_session(conn)
    run_id = uuid4()

    # Fail at the run-message write — by then the media blob AND the text
    # summary blob have both been staged to disk (and tracked for cleanup)
    # and the text uploads_entry row is in-flight within the txn. This avoids
    # needing a full real run/group scaffold while still exercising the
    # two-file rollback path.
    async def boom(*args, **kwargs):
        raise RuntimeError("simulated run-message failure")

    monkeypatch.setattr(up, "create_run_message", boom)

    with pytest.raises(RuntimeError, match="simulated run-message"):
        await up.media_upload_impl(
            pool,
            redis_client,
            modality="image",
            session_id=session_id,
            file_bytes=b"img bytes",
            filename="g.png",
            content_type="image/png",
            name="RunGen",
            run_id=run_id,
            attribute_to_run=True,
        )

    # Both the image blob and the text-summary blob were unlinked.
    img_leftover = list(folders["image"].glob("*"))
    assert img_leftover == [], f"image folder should be empty, found {img_leftover}"
    txt_leftover = [
        p for p in folders["tmp"].glob("*")
        if p.is_file()
    ]
    assert txt_leftover == [], f"upload folder should have no orphan text blob, found {txt_leftover}"
