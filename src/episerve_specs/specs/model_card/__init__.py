"""The model card: describes a forecast model container (stored as fdo.json in the model's repository)."""

from .checks import check_v1

SPEC_ID = "model-card"
CHECKS = {"1": check_v1}
