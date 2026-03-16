"""Read a text file with UTF-8 fallback to latin-1."""


def read_text_file(full_path: str) -> str:
    """Read a text file with UTF-8 fallback to latin-1."""
    try:
        with open(full_path, encoding="utf-8") as file:  # noqa: PTH123
            return file.read().strip()
    except UnicodeDecodeError:
        try:
            with open(full_path, encoding="latin-1") as file:  # noqa: PTH123
                return file.read().strip()
        except Exception as e:  # pragma: no cover - surfaced to caller
            raise ValueError(f"Error reading text file {full_path}: {str(e)}") from e
    except Exception as e:  # pragma: no cover - surfaced to caller
        raise ValueError(f"Error reading file {full_path}: {str(e)}") from e
