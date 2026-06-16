"""Atomic file writes — write-to-temp + ``os.replace`` (report-20 AU3).

Call receipts (``{upload_folder}/call/{id}.json``) are written in multiple
phases (initial body in ``save_call_upload``, per-event appends in
``append_call_event``, the final timing update in ``run_artifact_operation_with_audit``)
and read concurrently by the idempotency replay gate. A plain
``Path.write_text`` truncates-then-writes in place, so a reader that lands
mid-write sees a partial/corrupt file → ``json.loads`` raises → the gate
fails open and RE-EXECUTES the operation (a duplicate side effect).

``os.replace`` is an atomic rename within a filesystem: a reader always sees
either the complete old file or the complete new one, never a torn write.
Writing the temp file in the SAME directory as the target guarantees the
rename stays on one filesystem (a cross-device ``replace`` would raise).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path``.

    Writes to a temp file in the target's directory, flushes + fsyncs it, then
    ``os.replace``s it into place. Creates parent dirs if missing.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        # Never leave a stray temp file behind on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
