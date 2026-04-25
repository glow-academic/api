"""Module 07c — Model-position sub-resource seed definitions.

Pre-creates `model_positions_resource` rows for every (model, eval, index)
tuple. These rows must exist before the eval module runs so eval junction
inserts (eval_model_positions_junction) can FK-resolve.

Defined in seeds/evals.py as the single source of truth for the
eval × model cross-product; this module just re-exports the list.
"""

from database.seeds.evals import model_positions

__all__ = ["model_positions"]
