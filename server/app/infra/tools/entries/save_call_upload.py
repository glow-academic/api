"""Save a structured call receipt to disk as a .json file."""

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID


def save_call_upload(
    payload: dict[str, Any],
    upload_id: UUID,
    upload_folder: Path,
) -> str:
    """Write a call receipt to {upload_folder}/call/{upload_id}.json.

    Expects a payload dict from build_call_payload().

    Returns the relative file path: call/{upload_id}.json
    """
    subfolder = upload_folder / "call"
    subfolder.mkdir(parents=True, exist_ok=True)

    filename = f"{upload_id}.json"
    full_path = subfolder / filename

    full_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    return os.path.join("call", filename)
