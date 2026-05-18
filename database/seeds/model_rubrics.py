"""Module 07b — Model-rubric sub-resource seed definitions.

Pre-creates `model_rubrics_resource` rows for every (model, rubric) pair
referenced by an eval. These rows must exist before the eval module runs so
eval junction inserts (eval_model_rubrics_junction) can FK-resolve.

Defined in seeds/evals.py as the single source of truth for the
eval × model cross-product; this module just re-exports the list.
"""

from database.seeds.evals import model_rubrics

__all__ = ["model_rubrics"]
