"""Tool instruction seed definitions.

Reads .jinja files from database/seeds/tool_instructions/ and creates
instructions_resource entries with deterministic IDs, then provides
instruction_id references for tools.py to use.

Each tool can have a response template that defines how the AI should
structure its output when calling that tool.

File naming: {tool-slug}.jinja where slug is the lowercase hyphenated tool name.
Empty/comment-only files are skipped (no instruction created).
"""

from pathlib import Path

from database.seeds.ids import sid

INSTRUCTIONS_DIR = Path(__file__).parent / "tool_instructions"


def _slug(tool_name: str) -> str:
    """Convert tool name to file slug."""
    return tool_name.lower().replace(" ", "-")


def _read(filename: str) -> str | None:
    """Read a template file, returning None if empty/comment-only."""
    path = INSTRUCTIONS_DIR / filename
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    # Skip files that only have a comment
    lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("{#")]
    if not lines:
        return None
    return content


def instruction_id_for_tool(tool_name: str):
    """Get the deterministic instruction ID for a tool, or None if no template."""
    slug = _slug(tool_name)
    content = _read(f"{slug}.jinja")
    if content is None:
        return None
    return sid(f"tool-instruction/{slug}")


def get_tool_instructions() -> list[dict]:
    """Build instruction dicts for all tools that have non-empty templates."""
    instructions = []
    for path in sorted(INSTRUCTIONS_DIR.glob("*.jinja")):
        slug = path.stem
        content = _read(path.name)
        if content is None:
            continue
        instructions.append(dict(
            id=sid(f"tool-instruction/{slug}"),
            template=content,
        ))
    return instructions
