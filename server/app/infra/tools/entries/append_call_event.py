"""Append an output event to an existing call receipt."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


def append_call_event(
    call_id: UUID,
    event: str,
    data: dict[str, Any],
    upload_folder: Path,
) -> None:
    """Append an output event to the call receipt at {upload_folder}/call/{call_id}.json.

    Each appended event is added to the "events" array with a timestamp.
    If the file does not exist, this is a no-op.
    """
    path = upload_folder / "call" / f"{call_id}.json"
    if not path.exists():
        return

    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt.setdefault("events", []).append({
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    })
    path.write_text(json.dumps(receipt, indent=2, default=str), encoding="utf-8")
