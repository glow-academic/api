"""Code formatting helpers for registry generation."""

from __future__ import annotations

import subprocess
from pathlib import Path


def format_frozenset_literal(values: list[str], indent: int = 8) -> str:
    """Format a frozenset literal for code generation."""
    if not values:
        return "frozenset()"
    if len(values) <= 3:
        items = ", ".join(f'"{v}"' for v in sorted(values))
        return f"frozenset({{{items}}})"
    pad = " " * indent
    lines = [f'{pad}"{v}",' for v in sorted(values)]
    return (
        "frozenset(\n"
        + " " * indent
        + "{\n"
        + "\n".join(lines)
        + "\n"
        + pad
        + "}\n"
        + " " * (indent - 4)
        + ")"
    )


def format_dict_of_frozensets(
    var_name: str,
    type_hint: str,
    data: dict[str, list[str]],
    comment: str | None = None,
) -> str:
    """Format a dict[str, frozenset[str]] as Python source."""
    parts = []
    if comment:
        parts.append(f"# {comment}")
    parts.append(f"{var_name}: {type_hint} = {{")

    for key in sorted(data.keys()):
        values = sorted(data[key])
        if len(values) <= 3:
            items_str = ", ".join(f'"{v}"' for v in values)
            parts.append(f'    "{key}": frozenset({{{items_str}}}),')
        else:
            parts.append(f'    "{key}": frozenset(')
            parts.append("        {")
            for v in values:
                parts.append(f'            "{v}",')
            parts.append("        }")
            parts.append("    ),")

    parts.append("}")
    return "\n".join(parts)


def format_dict_of_dicts(
    var_name: str,
    type_hint: str,
    data: dict[str, dict[str, str]],
    comment: str | None = None,
) -> str:
    """Format a dict[str, dict[str, str]] as Python source."""
    parts = []
    if comment:
        parts.append(f"# {comment}")
    parts.append(f"{var_name}: {type_hint} = {{")

    for key in sorted(data.keys()):
        inner = data[key]
        if not inner:
            parts.append(f'    "{key}": {{}},')
        else:
            parts.append(f'    "{key}": {{')
            for k, v in inner.items():
                parts.append(f'        "{k}": "{v}",')
            parts.append("    },")

    parts.append("}")
    return "\n".join(parts)


def format_dict_of_strings(
    var_name: str,
    type_hint: str,
    data: dict[str, str],
    comment: str | None = None,
) -> str:
    """Format a dict[str, str] as Python source."""
    parts = []
    if comment:
        parts.append(f"# {comment}")
    parts.append(f"{var_name}: {type_hint} = {{")
    for key in sorted(data.keys()):
        parts.append(f'    "{key}": "{data[key]}",')
    parts.append("}")
    return "\n".join(parts)


def write_registry_file(path: Path, content: str, ruff_format: bool = True) -> None:
    """Write a registry file and optionally format with ruff."""
    path.write_text(content + "\n")
    if ruff_format:
        try:
            subprocess.run(
                ["ruff", "format", str(path)],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # ruff not available or format failed — file is still valid
