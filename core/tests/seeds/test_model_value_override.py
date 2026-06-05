"""Tests for the per-model ``value`` override in the model seed.

The DB ``models_resource.value`` is the model id sent to the upstream
provider/proxy at runtime (``prepare_pipeline`` resolves
``model.value or model.name``). It defaults to the model ``name`` so the
committed config keeps ``value == name == "glow-text"``. A deployment whose
proxy uses different upstream ids (e.g. the academic-demo routes ``glow-*`` →
``local-*`` on a DGX litellm proxy) can override ``value`` per-model in its
gitignored ``glow-deploy.local.yaml`` WITHOUT renaming the model — renaming
would break the deterministic ``sid("model-resource/<name>")`` linkage that
``database/seeds/evals.py`` depends on. The override is durable across reseed
(it lives in the config the seed re-reads) and never leaks into the committed
template.

These tests cover the pure resolver, the end-to-end config plumbing (a
``value:`` key in YAML reaches the seed builder), and the default/backward-compat
behaviour (committed config → ``value == name``).
"""

from __future__ import annotations

import sys
from pathlib import Path

# `database` is a top-level package at the repo root (sibling of `core`),
# not on the path under the `PYTHONPATH=core` test invocation.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from database.seeds.config import get_ai_models, load_deploy_config  # noqa: E402
from database.seeds.models import _resolve_model_value  # noqa: E402


# --- pure resolver -------------------------------------------------------


def test_value_defaults_to_name_when_absent():
    assert _resolve_model_value({"name": "glow-text"}, "glow-text") == "glow-text"


def test_value_override_is_honoured():
    cfg = {"name": "glow-text", "value": "local-text"}
    assert _resolve_model_value(cfg, "glow-text") == "local-text"


def test_unrelated_keys_do_not_affect_value():
    cfg = {"name": "glow-text", "provider": "learnloop", "description": "x"}
    assert _resolve_model_value(cfg, "glow-text") == "glow-text"


def test_empty_string_value_is_respected_not_silently_dropped():
    # An explicit empty string is a real (if odd) override, distinct from absent.
    # dict.get only falls back when the key is missing, so "" is preserved here;
    # the runtime's own `value or name` fallback handles the empty case downstream.
    assert _resolve_model_value({"name": "glow-text", "value": ""}, "glow-text") == ""


# --- end-to-end config plumbing -----------------------------------------


def test_value_override_flows_through_config_loader(tmp_path: Path):
    """A `value:` key in a deploy YAML survives load_deploy_config + get_ai_models
    and resolves correctly through the seed's resolver — the durable-override path."""
    yaml_path = tmp_path / "glow-deploy.yaml"
    yaml_path.write_text(
        "ai:\n"
        "  providers:\n"
        "    - name: learnloop\n"
        "      endpoint: http://proxy.local/v1\n"
        "      key: \"\"\n"
        "  models:\n"
        "    - name: glow-text\n"
        "      provider: learnloop\n"
        "      value: local-text\n"
        "    - name: glow-image\n"
        "      provider: learnloop\n"
    )
    config = load_deploy_config(yaml_path)
    models = {m["name"]: m for m in get_ai_models(config)}

    assert _resolve_model_value(models["glow-text"], "glow-text") == "local-text"
    # No `value:` key → falls back to the name.
    assert _resolve_model_value(models["glow-image"], "glow-image") == "glow-image"


# --- default / backward-compat regression guard --------------------------


def test_committed_config_keeps_value_equal_to_name():
    """The committed glow-deploy.yaml carries no `value:` keys, so every seeded
    model must have value == name (preserves the eval ID linkage + all existing
    deployments). Guards against a regression that hardcodes a remapped value."""
    from database.seeds.models import models

    assert models, "expected the committed config to seed at least one model"
    for m in models:
        assert m["value"] == m["name"], (
            f"model {m['name']!r} has value {m['value']!r} != name in the "
            f"committed config; the committed template must stay un-remapped"
        )
