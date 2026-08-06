from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.release_workflow_helpers import (
    STAGER,
    _publish_fixture,
    _pypi_release_payload,
    _pypi_server,
    _run,
)


def test_recovery_stages_only_the_named_missing_manifest_artifact(
    tmp_path: Path,
) -> None:
    arguments, output = _publish_fixture(tmp_path)
    arguments[arguments.index("--mode") + 1] = "recover"
    missing = "polis_nlp-0.2.0.tar.gz"
    arguments.extend(["--recovery-filename", missing])
    body = _pypi_release_payload(arguments, ("polis_nlp-0.2.0-py3-none-any.whl",))

    with _pypi_server(200, body) as package_index_url:
        arguments[arguments.index("--package-index-url") + 1] = package_index_url
        result = _run(STAGER, *arguments)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"staged=1 mode=recover filename={missing}\n"
    assert [path.name for path in output.iterdir()] == [missing]


@pytest.mark.parametrize(
    ("case", "error"),
    (
        ("zero", "exactly one"),
        ("two", "exactly one"),
        ("unknown", "release manifest"),
        ("wrong-size", "size"),
        ("wrong-hash", "SHA-256"),
        ("existing-requested", "missing"),
        ("wrong-run", "run metadata"),
        ("malformed", "invalid JSON"),
    ),
)
def test_recovery_rejects_unsafe_project_classifications(
    tmp_path: Path, case: str, error: str
) -> None:
    arguments, output = _publish_fixture(tmp_path)
    arguments[arguments.index("--mode") + 1] = "recover"
    missing = "polis_nlp-0.2.0.tar.gz"
    arguments.extend(["--recovery-filename", missing])
    existing = "polis_nlp-0.2.0-py3-none-any.whl"
    body = _pypi_release_payload(arguments, (existing,))
    match case:
        case "zero":
            body = _pypi_release_payload(arguments, ())
        case "two":
            body = _pypi_release_payload(arguments, (existing, missing))
        case "unknown":
            payload = json.loads(body)
            payload["releases"]["0.2.0"][0]["filename"] = "other.whl"
            body = json.dumps(payload).encode()
        case "wrong-size":
            payload = json.loads(body)
            payload["releases"]["0.2.0"][0]["size"] += 1
            body = json.dumps(payload).encode()
        case "wrong-hash":
            payload = json.loads(body)
            payload["releases"]["0.2.0"][0]["digests"]["sha256"] = "0" * 64
            body = json.dumps(payload).encode()
        case "existing-requested":
            arguments[arguments.index("--recovery-filename") + 1] = existing
        case "wrong-run":
            arguments[arguments.index("--artifact-run-id") + 1] = "18"
        case "malformed":
            body = b"{"
        case unreachable:
            raise AssertionError(unreachable)

    with _pypi_server(200, body) as package_index_url:
        arguments[arguments.index("--package-index-url") + 1] = package_index_url
        result = _run(STAGER, *arguments)

    assert result.returncode != 0
    assert error in result.stderr
    assert list(output.iterdir()) == []


def test_recovery_rejects_project_level_404(tmp_path: Path) -> None:
    with _pypi_server(404, b"") as package_index_url:
        arguments, output = _publish_fixture(tmp_path, package_index_url)
        arguments[arguments.index("--mode") + 1] = "recover"
        arguments.extend(["--recovery-filename", "polis_nlp-0.2.0.tar.gz"])
        result = _run(STAGER, *arguments)

    assert result.returncode != 0
    assert "HTTP 404" in result.stderr
    assert list(output.iterdir()) == []


def test_publish_rejects_project_level_200(tmp_path: Path) -> None:
    arguments, output = _publish_fixture(tmp_path)
    body = _pypi_release_payload(arguments, ())
    with _pypi_server(200, body) as package_index_url:
        arguments[arguments.index("--package-index-url") + 1] = package_index_url
        result = _run(STAGER, *arguments)

    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert list(output.iterdir()) == []
