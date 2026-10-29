"""The model card: describes a forecast model container (stored as fdo.json in the model's repository)."""

from .checks import check_v1
from .config import check_config, config_defaults

SPEC_ID = "model-card"
CHECKS = {"1": check_v1}

__all__ = ["CHECKS", "SPEC_ID", "check_config", "config_defaults", "check_v1"]
