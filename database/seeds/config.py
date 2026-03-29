"""Deploy config loader — reads glow-deploy.yaml and resolves env vars.

Resolves ${VAR:-default} patterns from the environment.
Used by the seed runner to determine what credentials to inject.
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
            result[k] = [_resolve_env_vars(i) if isinstance(i, str) else i for i in v]
        else:
            result[k] = v
    return result


def load_deploy_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and resolve glow-deploy.yaml.

    Args:
        path: Path to yaml file. Defaults to repo root glow-deploy.yaml.

    Returns:
        Resolved config dict with env vars substituted.
    """
    if path is None:
        # Look in common locations
        candidates = [
            Path("glow-deploy.yaml"),
            Path("/app/glow-deploy.yaml"),
            Path(__file__).parent.parent.parent / "glow-deploy.yaml",
        ]
        for p in candidates:
            if p.exists():
                path = p
                break
        else:
            raise FileNotFoundError(
                "glow-deploy.yaml not found. Create one from the template or set SEED_SETUP env var."
            )

    raw = yaml.safe_load(Path(path).read_text())
    return _resolve_dict(raw)


def get_ai_config(config: dict) -> dict:
    """Extract resolved AI credentials from config.

    Returns:
        {
            "provider": "learnloop" | "direct",
            "openai_key": str,
            "gemini_key": str,
            "openai_endpoint": str | None,
            "gemini_endpoint": str | None,
        }
    """
    ai = config.get("ai", {})
    provider = ai.get("provider", "direct")

    if provider == "learnloop":
        ll = ai.get("learnloop", {})
        api_key = ll.get("api_key", "")
        base_url = ll.get("base_url", "https://api.learn-loop.org/ai/v1")
        return {
            "provider": "learnloop",
            "openai_key": api_key,
            "gemini_key": api_key,
            "openai_endpoint": base_url,
            "gemini_endpoint": base_url,
        }

    direct = ai.get("direct", {})
    return {
        "provider": "direct",
        "openai_key": direct.get("openai", {}).get("api_key", "please_change_me"),
        "gemini_key": direct.get("gemini", {}).get("api_key", "please_change_me"),
        "openai_endpoint": None,
        "gemini_endpoint": None,
    }


def get_auth_config(config: dict) -> dict:
    """Extract resolved auth credentials from config.

    Returns:
        {
            "provider": "keycloak" | "learnloop" | "microsoft" | "google",
            "client_id": str,
            "client_secret": str,
            # provider-specific fields
        }
    """
    auth = config.get("auth", {})
    provider = auth.get("provider", "keycloak")

    if provider == "learnloop":
        ll = auth.get("learnloop", {})
        issuer = ll.get("issuer", "https://api.learn-loop.org")
        return {
            "provider": "learnloop",
            "client_id": ll.get("client_id", ""),
            "client_secret": ll.get("client_secret", ""),
            "issuer": issuer,
            "issuer_internal": ll.get("issuer_internal", issuer),
        }

    if provider == "microsoft":
        ms = auth.get("microsoft", {})
        return {
            "provider": "microsoft",
            "client_id": ms.get("client_id", "please_change_me"),
            "client_secret": ms.get("client_secret", "please_change_me"),
            "tenant_id": ms.get("tenant_id", "common"),
        }

    if provider == "google":
        g = auth.get("google", {})
        return {
            "provider": "google",
            "client_id": g.get("client_id", "please_change_me"),
            "client_secret": g.get("client_secret", "please_change_me"),
        }

    # keycloak — no external credentials needed
    return {"provider": "keycloak"}
