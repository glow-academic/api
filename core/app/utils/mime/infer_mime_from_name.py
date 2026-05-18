"""Infer MIME type from filename extension."""

import mimetypes

# Explicit overrides where Python's mimetypes is vague or not ideal for editors/viewers.
EXT_MIME_MAP = {
    # Code/markup (editor-friendly)
    ".java": "text/x-java-source; charset=utf-8",
    ".py": "text/x-python; charset=utf-8",
    ".c": "text/x-c; charset=utf-8",
    ".h": "text/x-c; charset=utf-8",
    ".cpp": "text/x-c++src; charset=utf-8",
    ".hpp": "text/x-c++hdr; charset=utf-8",
    ".cc": "text/x-c++src; charset=utf-8",
    ".cs": "text/x-csharp; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".jsx": "text/javascript; charset=utf-8",
    ".ts": "text/typescript; charset=utf-8",
    ".tsx": "text/typescript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".cjs": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".scss": "text/x-scss; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json",
    ".yml": "application/x-yaml; charset=utf-8",
    ".yaml": "application/x-yaml; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".sh": "text/x-shellscript; charset=utf-8",
    ".bash": "text/x-shellscript; charset=utf-8",
    ".zsh": "text/x-shellscript; charset=utf-8",
    ".rb": "text/x-ruby; charset=utf-8",
    ".go": "text/x-go; charset=utf-8",
    ".rs": "text/rust; charset=utf-8",
    ".kt": "text/x-kotlin; charset=utf-8",
    ".swift": "text/x-swift; charset=utf-8",
    ".m": "text/x-objectivec; charset=utf-8",
    ".mm": "text/x-objectivec; charset=utf-8",
    ".sql": "application/sql; charset=utf-8",
    ".ipynb": "application/x-ipynb+json",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    # High-impact viewers
    ".pdf": "application/pdf",
    ".svg": "image/svg+xml",
    # Common images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    # Office docs (helpful for downloads/preview handlers)
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
}

DEFAULT_FALLBACK = "application/octet-stream"  # safer than text/plain


def infer_mime_from_name(filename: str, fallback: str = DEFAULT_FALLBACK) -> str:
    """
    Infer MIME type from filename extension using our override map,
    otherwise fall back to Python's mimetypes, then to a safe default.
    """
    if not filename:
        return fallback

    dot = filename.rfind(".")
    ext = filename[dot:].lower() if dot != -1 else ""

    # 1) Try Python's mimetypes first (best for well-known types like PDF)
    python_guess = mimetypes.guess_type(filename)[0]
    if python_guess:
        return python_guess

    # 2) Use our override map for code/editor types and special cases
    if ext in EXT_MIME_MAP:
        return EXT_MIME_MAP[ext]

    # 3) Final fallback
    return fallback
