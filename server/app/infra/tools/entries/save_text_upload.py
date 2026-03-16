"""Save text content to disk as a .txt file."""

import os
from pathlib import Path
from uuid import UUID


def save_text_upload(content: str, upload_id: UUID, upload_folder: Path) -> str:
    """Write text content to {upload_folder}/text/{upload_id}.txt.

    Returns the relative file path: text/{upload_id}.txt
    """
    subfolder = upload_folder / "text"
    subfolder.mkdir(parents=True, exist_ok=True)

    filename = f"{upload_id}.txt"
    full_path = subfolder / filename

    full_path.write_text(content, encoding="utf-8")

    return os.path.join("text", filename)
