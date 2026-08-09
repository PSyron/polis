from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from polis.evaluation.calibration_models import CalibrationContractError
from polis.evaluation.calibration_paths import require_canonical_calibration_config
from polis.evaluation.calibration_runner import run_calibration as _run_calibration
from polis.evaluation.holdout_paths import require_canonical_config
from polis.evaluation.holdout_reservation import HoldoutAlreadyConsumedError
from polis.evaluation.holdout_runner import HoldoutAdmissionError, run_from_config

run_calibration: Callable[[Path], int] = _run_calibration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m polis.evaluation")
    commands = parser.add_subparsers(dest="command", required=True)
    run_holdout = commands.add_parser("run-holdout")
    run_holdout.add_argument("--config", type=Path, required=True)
    run_calibration_command = commands.add_parser("run-calibration")
    run_calibration_command.add_argument("--config", type=Path, required=True)
    return parser


def run(
    arguments: list[str],
    *,
    runner: Callable[[Path], int] = run_from_config,
    repository_root: Path | None = None,
) -> int:
    parsed = _parser().parse_args(arguments)
    config = parsed.config
    if not isinstance(config, Path):
        raise HoldoutAdmissionError("config path was not parsed")
    try:
        if parsed.command == "run-calibration":
            require_canonical_calibration_config(
                config, repository_root=repository_root
            )
            return run_calibration(config)
        require_canonical_config(config, repository_root=repository_root)
        return runner(config)
    except (
        CalibrationContractError,
        HoldoutAdmissionError,
        HoldoutAlreadyConsumedError,
        OSError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
