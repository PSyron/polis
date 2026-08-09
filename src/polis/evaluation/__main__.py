from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from polis.evaluation.holdout_paths import require_canonical_config
from polis.evaluation.holdout_reservation import HoldoutAlreadyConsumedError
from polis.evaluation.holdout_runner import HoldoutAdmissionError, run_from_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m polis.evaluation")
    commands = parser.add_subparsers(dest="command", required=True)
    run_holdout = commands.add_parser("run-holdout")
    run_holdout.add_argument("--config", type=Path, required=True)
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
        require_canonical_config(config, repository_root=repository_root)
        return runner(config)
    except (HoldoutAdmissionError, HoldoutAlreadyConsumedError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
