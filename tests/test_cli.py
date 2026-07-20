from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(
    args: list[str], input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polis.cli", *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_shows_help() -> None:
    result = run_cli(["--help"])

    assert result.returncode == 0
    assert "analyze" in result.stdout


def test_cli_invalid_config_path_fails_with_safe_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    result = run_cli(["analyze", "Tekst", "--config", str(missing), "--json"])

    assert result.returncode == 2
    assert "error:" in result.stderr


def test_cli_reads_stdin_unicode_input() -> None:
    result = run_cli(["analyze", "--stdin", "--json"], input_text="Witaj,świat.")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1


def test_cli_reads_unicode_file_and_filters_category(tmp_path: Path) -> None:
    input_path = tmp_path / "input.txt"
    input_path.write_text("Witaj,świecie.", encoding="utf-8")

    result = run_cli(
        [
            "analyze",
            "--file",
            str(input_path),
            "--category",
            "punctuation",
            "--json",
        ]
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["issues"]
    assert {finding["category"] for finding in payload["issues"]} == {"punctuation"}


def test_cli_applies_selected_finding() -> None:
    analyze = run_cli(["analyze", "Witaj,świecie.", "--json"])
    assert analyze.returncode == 0
    payload = json.loads(analyze.stdout)
    finding_ids = [finding["id"] for finding in payload["issues"]]
    assert finding_ids

    corrected = run_cli(
        ["analyze", "Witaj,świecie.", "--json", "--apply", finding_ids[0]]
    )
    assert corrected.returncode == 0
    payload_corrected = json.loads(corrected.stdout)
    assert payload_corrected["corrected_text"] == "Witaj, świecie."
