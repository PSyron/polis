"""Installed-wheel entry point for isolated runtime performance protocol v2."""

from __future__ import annotations

import sys
from typing import cast

from polis.runtime_performance_protocol import (
    RuntimePerformanceProtocolError,
    run_worker,
)


def main() -> int:
    try:
        return cast(int, run_worker(sys.stdin, sys.stdout))
    except (RuntimePerformanceProtocolError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
