from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from scripts.release_identity import read_release_policy
from tests.release_identity_helpers import ROOT, _receipt_binding_args


@pytest.mark.parametrize(
    "mutation",
    [
        "valid",
        "missing",
        "extra",
        "tampered-plan",
        "wrong-approval",
        "wrong-user",
        "uppercase-source",
        "uppercase-digest",
        "zero-run",
        "bad-time",
        "naive-time",
        "offset-time",
        "invalid-date",
        "override",
        "release-manifest-file",
        "wheelhouse-manifest-file",
        "wrong-source-input",
        "wrong-run-input",
        "policy-file",
        "plan-file",
    ],
)
def test_gate_receipt_validator_accepts_only_the_tracked_receipt_bindings(
    tmp_path: Path, mutation: str
) -> None:
    receipt, binding = _receipt_binding_args(tmp_path)
    created = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "create",
            *binding,
            "--output",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    match mutation:
        case "valid":
            pass
        case "missing":
            payload.pop("recorded_at")
        case "extra":
            payload["unexpected"] = True
        case "tampered-plan":
            payload["plan_sha256"] = "d" * 64
        case "wrong-approval":
            payload["approvals"]["P4"] = "REJECT"
        case "wrong-user":
            payload["user_approval"] = "approved"
        case "uppercase-source":
            payload["source_commit"] = "A" * 40
        case "uppercase-digest":
            payload["release_manifest_sha256"] = "B" * 64
        case "zero-run":
            payload["qualify_run_id"] = 0
        case "bad-time":
            payload["recorded_at"] = "not-a-time"
        case "naive-time":
            payload["recorded_at"] = "2026-08-06T12:00:00"
        case "offset-time":
            payload["recorded_at"] = "2026-08-06T13:00:00+01:00"
        case "invalid-date":
            payload["recorded_at"] = "2026-02-30T12:00:00Z"
        case "override":
            payload["policy_override"] = "d" * 64
        case "release-manifest-file":
            (tmp_path / "release-manifest.json").write_text(
                '{"release":"tampered"}\n', encoding="utf-8"
            )
        case "wheelhouse-manifest-file":
            (tmp_path / "wheelhouse-manifest.json").write_text(
                '{"wheelhouse":"tampered"}\n', encoding="utf-8"
            )
        case "wrong-source-input":
            binding[binding.index("--source-commit") + 1] = "b" * 40
        case "wrong-run-input":
            binding[binding.index("--qualify-run-id") + 1] = "18"
        case "policy-file":
            (tmp_path / "release-policy.json").write_text(
                '{"schema_version":1,"approved_plan_sha256":"d"}',
                encoding="utf-8",
            )
        case "plan-file":
            plan = tmp_path / "plan.md"
            plan.write_text("tampered plan\n", encoding="utf-8")
            binding[binding.index("--plan") + 1] = str(plan)
        case _:
            raise AssertionError(f"unknown receipt mutation: {mutation}")
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "validate",
            "--receipt",
            str(receipt),
            *binding,
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    if mutation == "valid":
        assert result.returncode == 0, result.stderr
        assert result.stdout == f"gate receipt is valid: {receipt}\n"
    else:
        assert result.returncode != 0
        assert "release gate receipt check failed:" in result.stderr


def test_gate_receipt_cli_creates_and_rebinds_real_input_files(tmp_path: Path) -> None:
    receipt, binding = _receipt_binding_args(tmp_path)

    created = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "create",
            *binding,
            "--output",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert created.returncode == 0, created.stderr
    assert created.stdout == f"gate receipt created: {receipt}\n"
    assert receipt.read_text(encoding="utf-8").endswith("\n")
    created_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert len(created_payload["recorded_at"]) == 20
    datetime.strptime(created_payload["recorded_at"], "%Y-%m-%dT%H:%M:%SZ")

    repeated = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "create",
            *binding,
            "--output",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert repeated.returncode != 0
    assert "output already exists" in repeated.stderr

    validated = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "validate",
            "--receipt",
            str(receipt),
            *binding,
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert validated.returncode == 0, validated.stderr
    assert validated.stdout == f"gate receipt is valid: {receipt}\n"


def test_gate_receipt_cli_rejects_a_caller_plan_or_approval_override(
    tmp_path: Path,
) -> None:
    receipt, binding = _receipt_binding_args(tmp_path)
    plan_index = binding.index("--plan") + 1
    binding[plan_index] = "d" * 64

    invalid_plan = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "create",
            *binding,
            "--output",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert invalid_plan.returncode != 0
    assert "plan digest does not match policy" in invalid_plan.stderr
    assert not receipt.exists()

    binding[plan_index] = read_release_policy(
        tmp_path / "release-policy.json"
    ).approved_plan_sha256
    binding[binding.index("--p1") + 1] = "REJECT"
    invalid_approval = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_release_gate_receipt.py"),
            "create",
            *binding,
            "--output",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert invalid_approval.returncode != 0
    assert "invalid choice" in invalid_approval.stderr
    assert not receipt.exists()
