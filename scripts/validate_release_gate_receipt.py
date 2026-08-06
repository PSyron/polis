from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_identity_models import ReleaseIdentityError
from scripts.release_identity_policy import (
    GateReceiptBinding,
    create_gate_receipt,
    validate_gate_receipt,
)


def add_binding_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--qualify-run-id", type=int, required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--release-policy", type=Path, required=True)
    parser.add_argument("--p1", choices=("APPROVE",), required=True)
    parser.add_argument("--p2", choices=("APPROVE",), required=True)
    parser.add_argument("--p3", choices=("APPROVE",), required=True)
    parser.add_argument("--p4", choices=("APPROVE",), required=True)
    parser.add_argument("--user-approval", choices=("okay",), required=True)


def binding_from_args(args: argparse.Namespace) -> GateReceiptBinding:
    return GateReceiptBinding(
        source_commit=args.source_commit,
        release_manifest=args.release_manifest,
        wheelhouse_manifest=args.wheelhouse_manifest,
        qualify_run_id=args.qualify_run_id,
        plan=args.plan,
        release_policy=args.release_policy,
        approvals=(args.p1, args.p2, args.p3, args.p4),
        user_approval=args.user_approval,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create or validate one release gate receipt."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create one strictly bound receipt")
    add_binding_arguments(create)
    create.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser(
        "validate", help="validate one strictly bound receipt"
    )
    add_binding_arguments(validate)
    validate.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    binding = binding_from_args(args)
    if args.command == "create":
        create_gate_receipt(binding, args.output)
        print(f"gate receipt created: {args.output}")
        return 0
    if args.command == "validate":
        validate_gate_receipt(args.receipt, binding)
        print(f"gate receipt is valid: {args.receipt}")
        return 0
    raise AssertionError(f"unsupported gate receipt command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseIdentityError as error:
        raise SystemExit(f"release gate receipt check failed: {error}") from error
