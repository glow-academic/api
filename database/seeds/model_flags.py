"""Module 07a — Model-flag sub-resource seed definitions.

Pre-creates `model_flags_resource` rows for every (model, use_custom=true)
pair. These rows must exist before the eval module runs so eval junction
inserts (eval_model_flags_junction) can FK-resolve.

Defined in seeds/evals.py as the single source of truth for the
eval × model cross-product; this module just re-exports the list so the
runner can `import database.seeds.model_flags` like every other module.
"""

from database.seeds.evals import model_flags

__all__ = ["model_flags"]
