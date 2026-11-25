"""The FAIR Digital Object record (<QID>.fdo.json) of a dataset, model run or benchmark on the platform."""

from .checks import check_v1, detect

SPEC_ID = "fdo"
CHECKS = {"1": check_v1}
DETECT = detect

__all__ = ["CHECKS", "DETECT", "SPEC_ID", "check_v1", "detect"]
