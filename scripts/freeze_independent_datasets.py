from __future__ import annotations

import sys

from polis.evaluation.calibration_operator import run_operator


def main() -> int:
    return 0 if run_operator(sys.argv[1:]) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
