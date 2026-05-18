"""Module 11 — Prompt and instruction seed definitions.

Reads .jinja files from database/seeds/prompts/ and creates
prompts_resource + instructions_resource entries with deterministic IDs.

System prompts: {slug}.system.jinja → prompts_resource
Instructions:   {slug}.instructions.jinja → instructions_resource
"""

from pathlib import Path

from database.seeds.ids import sid

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Agent name → file slug mapping
# Most are just lowercase-hyphenated; defaults to lower().replace(" ", "-").
_AGENT_SLUG_MAP: dict[str, str] = {}


def _slug(agent_name: str) -> str:
    """Convert agent name to file slug."""
    return _AGENT_SLUG_MAP.get(agent_name, agent_name.lower().replace(" ", "-"))


def _read(filename: str) -> str | None:
    """Read a prompt file, returning None if it doesn't exist."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


# ---------------------------------------------------------------------------
# Build prompt and instruction data from .jinja files
# ---------------------------------------------------------------------------

# All agent names that should have prompts
AGENT_NAMES = [
    "Activity", "Agent", "Attempt Chat", "Attempt Grade", "Attempt Realtime",
    "Auth", "Benchmark", "Chat", "Cohort", "Composer",
    "Dashboard", "Department", "Document", "Eval",
    "Field", "Group", "Health", "Home",
    "Invocation", "Leaderboard", "Model", "Parameter",
    "Persona", "Practice", "Pricing", "Profile",
    "Provider", "Record", "Reports", "Rubric",
    "Scenario", "Session", "Setting", "Simulation",
    "Test", "Test Grade", "Tool", "Transcribe",
]

# Build prompt dicts
prompts = []
instructions = []

for name in AGENT_NAMES:
    slug = _slug(name)

    system_content = _read(f"{slug}.system.jinja")
    if system_content is not None:
        prompts.append(dict(
            id=sid(f"prompt/{slug}"),
            name=f"{name} System Prompt",
            description=f"System prompt for the {name} agent",
            system_prompt=system_content,
        ))

    instruction_content = _read(f"{slug}.instructions.jinja")
    if instruction_content is not None:
        instructions.append(dict(
            id=sid(f"instruction/{slug}"),
            template=instruction_content,
        ))


# ---------------------------------------------------------------------------
# Exported ID helpers for agents.py
# ---------------------------------------------------------------------------

def prompt_id(agent_name: str):
    """Get the deterministic prompt ID for an agent, or None if no file."""
    slug = _slug(agent_name)
    if (PROMPTS_DIR / f"{slug}.system.jinja").exists():
        return sid(f"prompt/{slug}")
    return None


def instruction_id(agent_name: str):
    """Get the deterministic instruction ID for an agent, or None if no file."""
    slug = _slug(agent_name)
    if (PROMPTS_DIR / f"{slug}.instructions.jinja").exists():
        return sid(f"instruction/{slug}")
    return None
