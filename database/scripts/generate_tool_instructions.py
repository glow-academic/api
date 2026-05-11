"""Generate per-tool render templates for CRUD artifacts.

Emits jinja files into database/seeds/tool_instructions/ following the
persona-* canonical shape. Templates are generic over the artifact's
DraftFormState — they iterate result fields rather than hard-coding the
field list — so they work for every artifact without per-field spec.

Usage:
    python -m database.scripts.generate_tool_instructions          # dry run
    python -m database.scripts.generate_tool_instructions --write  # write files
    python -m database.scripts.generate_tool_instructions --write --force

By default only files that are essentially empty (<=1 stripped lines) are
written. Pass --force to overwrite already-filled files too — use with care.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

# ---------------------------------------------------------------------------
# Artifact spec
# ---------------------------------------------------------------------------

# (slug, Display, plural_noun)
ARTIFACTS: list[tuple[str, str, str]] = [
    ("agent", "Agent", "agents"),
    ("auth", "Auth", "auths"),
    ("cohort", "Cohort", "cohorts"),
    ("department", "Department", "departments"),
    ("document", "Document", "documents"),
    ("eval", "Eval", "evals"),
    ("field", "Field", "fields"),
    ("model", "Model", "models"),
    ("parameter", "Parameter", "parameters"),
    ("profile", "Profile", "profiles"),
    ("provider", "Provider", "providers"),
    ("rubric", "Rubric", "rubrics"),
    ("setting", "Setting", "settings"),
    ("simulation", "Simulation", "simulations"),
    ("tool", "Tool", "tools"),
    # CRUD-ish artifacts that have a subset of standard ops
    ("benchmark", "Benchmark", "benchmarks"),
    ("chat", "Chat", "chats"),
    ("invocation", "Invocation", "invocations"),
    ("test", "Test", "tests"),
]

# Operations we generate. `drafts` is skipped — every artifact already has a
# working drafts.jinja that the seed loaded.
OPERATIONS: list[str] = [
    "create",
    "delete",
    "draft",
    "duplicate",
    "export",
    "get",
    "refresh",
    "search",
    "update",
]


# ---------------------------------------------------------------------------
# Templates — $NAME and $PLURAL are substituted per artifact
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, Template] = {
    "create": Template(
        """{% if success and results %}
$NAME created successfully.
{% for r in results %}
{% if r.result and r.result.results %}
{% for item in r.result.results %}
- **{{ item.message }}**{% if item.id %} (ID: `{{ item.id }}`){% endif %}
{% endfor %}
{% endif %}
{% endfor %}
{% elif results %}
$NAME creation failed.
{% for r in results %}
- {{ r.error or r.message or 'Unknown error' }}
{% endfor %}
{% else %}
No result returned.
{% endif %}
"""
    ),
    "delete": Template(
        """{% if success %}
$NAME{{ 's' if count and count > 1 else '' }} deleted successfully.{% if count %} {{ count }} removed.{% endif %}
{% else %}
Delete failed.{% if message %} {{ message }}{% endif %}
{% endif %}
"""
    ),
    "duplicate": Template(
        """{% if success and results and results[0] and results[0].result %}
$NAME duplicated successfully.{% if results[0].result.id %} New ID: `{{ results[0].result.id }}`.{% endif %}
{% elif results and results[0] %}
Duplicate failed: {{ results[0].error or 'Unknown error' }}
{% else %}
No result returned.
{% endif %}
"""
    ),
    "export": Template(
        """{% if success and results and results[0] and results[0].result %}
{% set r = results[0].result %}
$NAME export ready.{% if r.file_name %} File: **{{ r.file_name }}**.{% endif %}{% if r.file_id %} ID: `{{ r.file_id }}`.{% endif %}
{% elif results and results[0] %}
Export failed: {{ results[0].error or 'Unknown error' }}
{% else %}
No result returned.
{% endif %}
"""
    ),
    "refresh": Template(
        """{% if success %}
$NAME list refreshed.
{% else %}
Refresh failed.{% if message %} {{ message }}{% endif %}
{% endif %}
"""
    ),
    "update": Template(
        """{% if success and results and results[0] and results[0].result %}
{% set r = results[0].result %}
$NAME updated successfully.{% if r.id %} ID: `{{ r.id }}`.{% endif %}{% if r.message %} {{ r.message }}{% endif %}
{% elif results and results[0] %}
Update failed: {{ results[0].error or 'Unknown error' }}
{% else %}
No result returned.
{% endif %}
"""
    ),
    "draft": Template(
        """{% if success and results and results[0] and results[0].result %}
{% set r = results[0].result %}
Draft saved. ID: `{{ r.draft_id }}`.{% if r.message %} {{ r.message }}{% endif %}
{% if r.form_state %}
### Form State
{% set fs = r.form_state %}
{% for key, value in fs.items() %}
{% if value is not none and value != [] and value != '' and key != 'pending_ids' %}
{% if value is string %}
- **{{ key }}:** {{ value[:120] }}{% if value|length > 120 %}…{% endif %}
{% elif value is mapping %}
- **{{ key }}:** (set)
{% elif value is iterable %}
- **{{ key }}:** {{ value | length }}
{% else %}
- **{{ key }}:** {{ value }}
{% endif %}
{% endif %}
{% endfor %}
{% endif %}
{% elif results and results[0] %}
Draft save failed: {{ results[0].error or 'Unknown error' }}
{% else %}
No result returned.
{% endif %}
"""
    ),
    "search": Template(
        """{% if success and results and results[0] and results[0].result %}
{% set r = results[0].result %}
{% set rows = r.$PLURAL if r.$PLURAL is defined else (r.results if r.results is defined else []) %}
{% if rows and rows|length > 0 %}
## $NAMES ({{ rows|length }} results{% if r.has_more %}, more available{% endif %})

{% for item in rows %}
- **{{ item.name or '(unnamed)' }}**{% if item.description %} — {{ item.description[:80] }}{% if item.description|length > 80 %}…{% endif %}{% endif %} (ID: `{{ item.id or item.${LOWER}_id }}`)
{% endfor %}

{% if r.has_more %}
Use `page_offset` to see more results.
{% endif %}
{% else %}
No $PLURAL found matching the search criteria.
{% endif %}
{% elif results and results[0] and results[0].error %}
Error searching $PLURAL: {{ results[0].error }}
{% else %}
No $LOWER search result returned.
{% endif %}
"""
    ),
    "get": Template(
        """{% if success and results and results[0] and results[0].result %}
{% set r = results[0].result %}
{% if r.draft_id %}### $NAME Draft (ID: `{{ r.draft_id }}`){% else %}### $NAME{% endif %}

{% for key, bank in r.items() %}
{% if bank is iterable and bank is not string and bank is not mapping and bank|length > 0 and key not in ['draft_id', 'idempotency_key'] %}
#### {{ key | replace('_', ' ') | title }}
{% for item in bank %}
{% if item is mapping %}
- `{{ item.id or item.get(key[:-1] ~ '_id', '') }}` — {{ item.name or item.value or item.label or (item.description[:60] if item.description is defined else '(unnamed)') }}{% if item.selected %} ✓{% endif %}
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
{% elif results and results[0] and results[0].error %}
Error fetching $LOWER: {{ results[0].error }}
{% else %}
No $LOWER data returned.
{% endif %}
"""
    ),
}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "seeds" / "tool_instructions"


def is_essentially_empty(path: Path) -> bool:
    """True if the file exists and has <=1 non-blank line.

    Returns False for non-existent files — the generator only fills in
    existing empty templates, it never creates new files (which could
    create dangling templates for tools that don't exist).
    """
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    stripped = [ln for ln in text.splitlines() if ln.strip()]
    return len(stripped) <= 1


def render(op: str, name: str, plural: str) -> str:
    return TEMPLATES[op].substitute(
        NAME=name,
        NAMES=name + "s" if not name.endswith("s") else name,
        PLURAL=plural,
        LOWER=name.lower(),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    written = 0
    skipped = 0
    for slug, name, plural in ARTIFACTS:
        for op in OPERATIONS:
            path = PROMPTS_DIR / f"{slug}-{op}.jinja"
            if not path.exists():
                continue  # never create new files
            if not is_essentially_empty(path) and not args.force:
                skipped += 1
                continue
            content = render(op, name, plural)
            if args.write:
                path.write_text(content, encoding="utf-8")
            written += 1

    print(f"{'wrote' if args.write else 'would write'}: {written}, skipped (already filled): {skipped}")
    if not args.write:
        print("(dry run — pass --write to apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
