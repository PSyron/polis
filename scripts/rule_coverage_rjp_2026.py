"""CLI for the maintained RJP 2026 rule-coverage audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.rjp_2026_audit_contract import (
    AUDIT_PATH,
    RjpAuditError,
    validate_rjp_2026_audit,
)


def main(argv: list[str] | None = None) -> int:
    """Validate the RJP audit and return a shell-friendly exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=AUDIT_PATH)
    args = parser.parse_args(argv)
    try:
        validate_rjp_2026_audit(args.path)
    except RjpAuditError as error:
        print(f"RJP 2026 audit validation failed: {error}")
        return 1
    print("RJP 2026 audit is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
