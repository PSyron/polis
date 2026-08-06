from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.release_workflow_helpers import (
    FIXTURES,
    STAGER,
    _publish_fixture,
    _pypi_server,
    _run,
)


def test_publish_staging_copies_only_the_two_manifest_distributions(
    tmp_path: Path,
) -> None:
    with _pypi_server(404, b"") as package_index_url:
        arguments, output = _publish_fixture(tmp_path, package_index_url)

        result = _run(STAGER, *arguments)

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in output.iterdir()) == [
        "polis_nlp-0.2.0-py3-none-any.whl",
        "polis_nlp-0.2.0.tar.gz",
    ]


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        ("run", "run metadata"),
        ("sha", "run metadata"),
        ("receipt", "gate receipt"),
        ("manifest", "manifest"),
        ("extra-dist", "manifest"),
        ("dirty-output", "output"),
        ("conclusion", "run metadata"),
        ("repository", "run metadata"),
        ("policy", "release policy"),
    ),
)
def test_publish_staging_rejects_stale_or_tampered_inputs(
    tmp_path: Path, mutation: str, error: str
) -> None:
    with _pypi_server(404, b"") as package_index_url:
        arguments, output = _publish_fixture(tmp_path, package_index_url)
        match mutation:
            case "run":
                arguments[arguments.index("--artifact-run-id") + 1] = "18"
            case "sha":
                arguments[arguments.index("--source-commit") + 1] = "b" * 40
            case "receipt":
                index = arguments.index("--receipt-json") + 1
                payload = json.loads(arguments[index])
                payload["user_approval"] = "no"
                arguments[index] = json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                )
            case "manifest":
                path = Path(arguments[arguments.index("--release-manifest") + 1])
                path.write_text(
                    path.read_text(encoding="utf-8") + " ", encoding="utf-8"
                )
            case "extra-dist":
                Path(arguments[arguments.index("--dist") + 1], "extra.txt").write_text(
                    "x", encoding="utf-8"
                )
            case "dirty-output":
                (output / "old.whl").write_bytes(b"old")
            case "conclusion" | "repository":
                run = tmp_path / "run.json"
                payload = json.loads(
                    (FIXTURES / "run-valid.json").read_text(encoding="utf-8")
                )
                if mutation == "conclusion":
                    payload["conclusion"] = "failure"
                else:
                    payload["repository"]["full_name"] = "Other/polis"
                run.write_text(json.dumps(payload), encoding="utf-8")
                arguments[arguments.index("--run-metadata") + 1] = str(run)
            case "policy":
                policy = tmp_path / "release-policy.json"
                policy.write_text(
                    '{"schema_version":1,"approved_plan_sha256":"' + "d" * 64 + '"}',
                    encoding="utf-8",
                )
                arguments[arguments.index("--release-policy") + 1] = str(policy)
            case unreachable:
                raise AssertionError(unreachable)

        result = _run(STAGER, *arguments)

    assert result.returncode != 0
    assert error in result.stderr
