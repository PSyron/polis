from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from polis import cli


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


def run_cli_with_inherited_cp1252(
    args: list[str], input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    return subprocess.run(
        [sys.executable, "-m", "polis.cli", *args],
        input=input_bytes,
        capture_output=True,
        check=False,
        env=env,
    )


def run_cli_with_windows_newlines_and_inherited_cp1252(
    args: list[str],
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    command = (
        "import sys; "
        'sys.stdout.reconfigure(newline="\\r\\n"); '
        "from polis.cli import main; "
        "main(sys.argv[1:])"
    )
    return subprocess.run(
        [sys.executable, "-c", command, *args],
        capture_output=True,
        check=False,
        env=env,
    )


def decode_utf8_output(result: subprocess.CompletedProcess[bytes]) -> tuple[str, str]:
    return result.stdout.decode("utf-8"), result.stderr.decode("utf-8")


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
    result = run_cli_with_inherited_cp1252(
        ["analyze", "--stdin", "--json"],
        input_bytes="Cześć,świecie.".encode(),
    )

    stdout, stderr = decode_utf8_output(result)
    assert result.returncode == 0, stderr
    payload = json.loads(stdout)
    assert payload["schema_version"] == 1
    assert payload["text"] == "Cześć,świecie."
    assert payload["issues"][0]["start"] == 5


def test_cli_reads_unicode_file_and_filters_category(tmp_path: Path) -> None:
    input_path = tmp_path / "zażółć.txt"
    input_path.write_text("Witaj,świecie.", encoding="utf-8")

    result = run_cli_with_inherited_cp1252(
        [
            "analyze",
            "--file",
            str(input_path),
            "--category",
            "punctuation",
            "--json",
        ]
    )

    stdout, stderr = decode_utf8_output(result)
    assert result.returncode == 0, stderr
    payload = json.loads(stdout)
    assert payload["text"] == "Witaj,świecie."
    assert payload["issues"]
    assert {finding["category"] for finding in payload["issues"]} == {"punctuation"}


def test_cli_json_output_is_utf8_when_stdout_inherits_cp1252() -> None:
    result = run_cli_with_inherited_cp1252(["analyze", "Witaj,świecie.", "--json"])

    stdout, stderr = decode_utf8_output(result)
    assert result.returncode == 0, stderr
    payload = json.loads(stdout)
    assert payload["text"] == "Witaj,świecie."
    assert payload["issues"][0]["message"] == "Brakuje spacji po przecinku."


def test_cli_human_and_apply_outputs_are_utf8_when_stdout_inherits_cp1252() -> None:
    analyze = run_cli(["analyze", "Witaj,świecie.", "--json"])
    assert analyze.returncode == 0
    finding_id = json.loads(analyze.stdout)["issues"][0]["id"]

    human = run_cli_with_inherited_cp1252(["analyze", "Ala.Kot."])
    human_stdout, human_stderr = decode_utf8_output(human)
    assert human.returncode == 0, human_stderr
    assert "Brakuje spacji między zdaniami." in human_stdout

    applied = run_cli_with_windows_newlines_and_inherited_cp1252(
        ["analyze", "Witaj,świecie.", "--apply", finding_id]
    )
    applied_stdout, applied_stderr = decode_utf8_output(applied)
    assert applied.returncode == 0, applied_stderr
    assert applied_stdout == "Witaj, świecie.\r\n"


def test_cli_error_output_is_utf8_when_stderr_inherits_cp1252(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "brak-zażółć.txt"
    result = run_cli_with_inherited_cp1252(["analyze", "--file", str(missing)])

    stdout, stderr = decode_utf8_output(result)
    assert result.returncode == 2, stderr
    assert stdout == ""
    assert "brak-zażółć.txt" in stderr


class _EmbeddedStream(io.StringIO):
    def reconfigure(self, **kwargs: object) -> None:
        raise AssertionError(f"embedded stream was reconfigured: {kwargs}")


def test_run_keeps_caller_owned_stream_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdin = _EmbeddedStream()
    stdout = _EmbeddedStream()
    stderr = _EmbeddedStream()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    return_code = cli.run(["analyze", "Witaj,świecie."])

    assert return_code == 0
    assert "Brakuje spacji po przecinku." in stdout.getvalue()
    assert stderr.getvalue() == ""


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
