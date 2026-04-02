"""Deploy config loader — reads glow-deploy.yaml and resolves env vars.

Resolves ${VAR:-default} patterns from the environment.
Used by the seed runner to determine what providers, models, and auth to seed.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml


def _resolve_env_vars(value: str) -> str:
    """Resolve ${VAR:-default} patterns in a string."""
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(3) if match.group(3) is not None else ""
        return os.environ.get(var_name, default)

    return re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(:-(.*?))?\}', _replace, value)


def _resolve_dict(d: dict) -> dict:
    """Recursively resolve env vars in a dict."""
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _resolve_dict(v)
        elif isinstance(v, list):
            result[k] = [
                _resolve_dict(i) if isinstance(i, dict)
                else _resolve_env_vars(i) if isinstance(i, str)
                else i
                for i in v
            ]
        else:
            result[k] = v
    return result


def load_deploy_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and resolve glow-deploy.yaml.

    Searches for glow-deploy.local.yaml first (local dev override),
    then falls back to glow-deploy.yaml.
    """
    if path is None:
        project_root = Path(__file__).parent.parent.parent
        candidates = [
            project_root / "glow-deploy.local.yaml",
            project_root / "glow-deploy.yaml",
            Path("/app/glow-deploy.local.yaml"),
            Path("/app/glow-deploy.yaml"),
        ]
        for p in candidates:
            if p.exists():
                path = p
                break
        else:
            raise FileNotFoundError(
                "glow-deploy.yaml not found. Create one from the template."
            )

    raw = yaml.safe_load(Path(path).read_text())
    return _resolve_dict(raw)


# ---------------------------------------------------------------------------
# Config accessors
# ---------------------------------------------------------------------------

def get_ai_providers(config: dict) -> list[dict]:
    """Return list of AI provider configs.

    Each: {"name": str, "endpoint": str, "key": str}
    """
    return [
        p for p in config.get("ai", {}).get("providers", [])
        if p.get("name")
    ]


def get_ai_roles(config: dict) -> dict[str, str]:
    """Return role→model name mapping.

    E.g. {"text": "glow-text", "grader": "glow-grader", ...}
    """
    return config.get("ai", {}).get("roles", {})


def get_ai_models(config: dict) -> list[dict]:
    """Return list of model configs.

    Each: {"name": str, "provider": str, "description": str, "modalities": list}
    """
    return config.get("ai", {}).get("models", [])


def get_auth_providers(config: dict) -> list[dict]:
    """Return list of auth provider configs.

    Each: {"name": str, "protocol": str, "slug": str, "display_name": str,
           "client_id": str, "client_secret": str, ...provider-specific fields}
    """
    return [
        p for p in config.get("auth", {}).get("providers", [])
        if p.get("name")
    ]
