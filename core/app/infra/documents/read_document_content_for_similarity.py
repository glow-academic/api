"""Read textual content from a document for similarity scoring."""

from pathlib import Path

import pypdf  # type: ignore

from app.infra.globals import UPLOAD_FOLDER
from app.infra.upload_paths import resolve_upload_path


def read_document_content_for_similarity(
    file_path: str, *, upload_folder: Path = UPLOAD_FOLDER
) -> str:
    """Read textual content from a document under UPLOAD_FOLDER for similarity scoring.

    - PDFs: extract per-page text via pypdf
    - Text files: read with UTF-8, fallback to latin-1
    """
    full_path = resolve_upload_path(file_path, upload_folder=upload_folder)
    content = ""
    if file_path.lower().endswith(".pdf"):
        try:
            with full_path.open("rb") as fh:
                reader = pypdf.PdfReader(fh)
                for page in reader.pages:
                    content += (page.extract_text() or "") + "\n"
        except Exception:
            return ""
    else:
        try:
            with full_path.open(encoding="utf-8") as fh:
                content = fh.read()
        except UnicodeDecodeError:
            try:
                with full_path.open(encoding="latin-1") as fh:
                    content = fh.read()
            except Exception:
                return ""
        except Exception:
            return ""

    return content.strip()
