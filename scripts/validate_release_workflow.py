from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from release_workflow_contract import validate_workflow


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the protected release workflow contract."
    )
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--print-matrix", action="store_true")
    args = parser.parse_args(argv)
    validation = validate_workflow(args.workflow)
    if validation.errors:
        print("\n".join(validation.errors), file=sys.stderr)
        return 1
    print("release workflow contract is valid")
    if args.print_matrix:
        for os_name, version in validation.matrix:
            print(f"{os_name}|{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
