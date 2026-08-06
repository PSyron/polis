from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence

COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID_RE = re.compile(r"[1-9][0-9]*\Z")


def _require_compact_json(raw: str) -> None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit("gate receipt input must be valid compact JSON") from error
    if not isinstance(payload, dict) or not payload:
        raise SystemExit("gate receipt input must be a non-empty JSON object")
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if raw != compact:
        raise SystemExit("gate receipt input must use canonical compact JSON")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate disjoint manual release workflow inputs."
    )
    parser.add_argument("--mode", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact-run-id", default="")
    parser.add_argument("--gate-receipt-json", default="")
    parser.add_argument("--recovery-filename", default="")
    args = parser.parse_args(argv)
    if not COMMIT_RE.fullmatch(args.source_commit):
        raise SystemExit("source commit must be a lowercase 40-character SHA")
    match args.mode:
        case "qualify":
            if args.artifact_run_id or args.gate_receipt_json or args.recovery_filename:
                raise SystemExit("qualify forbids cross-run and recovery inputs")
        case "publish":
            if not RUN_ID_RE.fullmatch(args.artifact_run_id):
                raise SystemExit("publish requires a positive artifact run id")
            _require_compact_json(args.gate_receipt_json)
            if args.recovery_filename:
                raise SystemExit("publish forbids a recovery filename")
        case "recover":
            if not RUN_ID_RE.fullmatch(args.artifact_run_id):
                raise SystemExit("recover requires a positive artifact run id")
            _require_compact_json(args.gate_receipt_json)
            if not args.recovery_filename:
                raise SystemExit("recover requires a recovery filename")
        case _:
            raise SystemExit("mode must be qualify, publish, or recover")
    print("release workflow inputs are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
