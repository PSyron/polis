from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_uses_inventory_under_custom_root(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    inventory_path = (
        tmp_path / "docs" / "project" / "evaluation-artifact-inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["aliases"][0]["canonical"] = "docs/../../outside.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_evaluation_artifact_inventory.py"),
            "--root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "canonical path escapes root/docs" in result.stderr
