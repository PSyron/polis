from __future__ import annotations

from pathlib import Path
from typing import Final

from polis.evaluation.calibration_models import CalibrationContractError

CANONICAL_CALIBRATION_CONFIG: Final = Path(
    "experiments/a-b-qualification-v2/config.json"
)
CALIBRATION_REVIEW: Final = Path(
    "experiments/a-b-qualification-v2/calibration.review.json"
)
CALIBRATION_REVIEW_PAYLOAD: Final = Path(
    ".omo/sealed/a-b-calibration-v2-v1/review.payload.json"
)


def require_canonical_calibration_config(
    config_path: Path, *, repository_root: Path | None = None
) -> Path:
    root = repository_root or Path(__file__).resolve().parents[3]
    if Path.cwd() != root:
        raise CalibrationContractError(
            "calibration command must run from the repository root"
        )
    if config_path.is_absolute() or config_path != CANONICAL_CALIBRATION_CONFIG:
        raise CalibrationContractError(
            f"calibration config path must be exactly {CANONICAL_CALIBRATION_CONFIG}"
        )
    current = root
    for component in config_path.parts:
        current /= component
        if current.is_symlink():
            raise CalibrationContractError(
                "canonical calibration config path cannot contain symlinks"
            )
    return config_path
