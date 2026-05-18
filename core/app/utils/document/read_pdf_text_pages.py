"""Return per-page extracted text for a PDF."""

import pypdf  # type: ignore


def read_pdf_text_pages(full_path: str) -> list[str]:
    """Return per-page extracted text for a PDF at full_path."""
    texts: list[str] = []
    try:
        with open(full_path, "rb") as file:  # noqa: PTH123
            pdf_reader = pypdf.PdfReader(file)
            for page in pdf_reader.pages:
                texts.append((page.extract_text() or "").strip())
    except Exception as e:  # pragma: no cover - surfaced to caller
        raise ValueError(f"Error reading PDF file {full_path}: {str(e)}") from e
    return texts
