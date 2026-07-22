from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from scripts import run_sentence_release_case as runner

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_sentence_release_case.py"
FAKE_STDIO = ROOT / "tests" / "fixtures" / "fake_languagetool_stdio.py"


def _fake_stdio_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-languagetool"
    executable.write_text(
        f"#!{sys.executable}\n" + FAKE_STDIO.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _runner_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    for name in (
        "ALL_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "all_proxy",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    ):
        environment.pop(name, None)
    return environment


def _start_runner(tmp_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        (
            sys.executable,
            os.fspath(RUNNER),
            "--vendored-stdio",
            os.fspath(_fake_stdio_executable(tmp_path)),
            "--expected-install-root",
            os.fspath(ROOT / "src"),
            "--timeout-seconds",
            "1",
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=_runner_environment(),
    )


def _exchange(
    process: subprocess.Popen[str], request_id: int, text: str
) -> dict[str, Any]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        json.dumps(
            {
                "schema_version": 1,
                "request_id": request_id,
                "operation": "analyze_sentence",
                "text": text,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    process.stdin.flush()
    payload: object = json.loads(process.stdout.readline())
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_runner_reuses_one_analyzer_for_multiple_sentence_requests(
    tmp_path: Path,
) -> None:
    process = _start_runner(tmp_path)
    try:
        first = _exchange(process, 1, "Wiem że wróciła.")
        second = _exchange(process, 2, "Rozmawiałem z Janem Nowak.")
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.wait(timeout=5)

    assert first["status"] == "complete"
    assert second["status"] == "complete"
    assert first["request_id"] == 1
    assert second["request_id"] == 2
    assert first["process_start_count"] == 1
    assert second["process_start_count"] == 1
    assert first["combined_peak_rss_bytes"] >= first["combined_rss_bytes"]
    assert second["combined_peak_rss_bytes"] >= second["combined_rss_bytes"]
    assert first["corrected_text"] == "Wiem, że wróciła."
    assert second["selected_text"] == "Rozmawiałem z Janem Nowakiem."


@pytest.mark.parametrize("measured", (0, 1, 2))
def test_runner_reads_analyzer_owned_process_start_count(measured: int) -> None:
    class AnalyzerEvidence:
        language_tool_process_start_count = measured

    assert runner._language_tool_process_start_count(AnalyzerEvidence()) == measured


@pytest.mark.parametrize("text", ("", "Pierwsze. Drugie."))
def test_runner_rejects_non_single_sentence_without_echoing_text(
    tmp_path: Path, text: str
) -> None:
    process = _start_runner(tmp_path)
    try:
        response = _exchange(process, 1, text)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.wait(timeout=5)

    assert response["status"] == "invalid_request"
    assert response["error_code"] == "runner.single_sentence_required"
    if text:
        assert text not in json.dumps(response, ensure_ascii=False)


def test_runner_rejects_repository_import_when_install_root_differs(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        (
            sys.executable,
            os.fspath(RUNNER),
            "--vendored-stdio",
            os.fspath(_fake_stdio_executable(tmp_path)),
            "--expected-install-root",
            os.fspath(tmp_path),
        ),
        capture_output=True,
        text=True,
        env=_runner_environment(),
        check=False,
    )

    assert completed.returncode != 0
    assert str(ROOT) not in completed.stderr
    assert "import origin is outside the expected installation" in completed.stderr
