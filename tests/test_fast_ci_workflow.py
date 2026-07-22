from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_fast_ci_workflow.py"
WORKFLOW = ROOT / ".github/workflows/fast-ci.yml"
LICENSE_REVIEW = ROOT / "docs/development/dependency-licenses.md"
COMPATIBILITY_POLICY = ROOT / "docs/compatibility.md"
DISTRIBUTION_VERIFICATION = ROOT / "docs/distribution-verification.md"
BYTE_STABLE_TEXT_PATHS = (
    "experiments/languagetool_stdio_session/config.json",
    "experiments/languagetool_stdio_session/run_benchmark.py",
    "tests/fixtures/evaluation/polish_correction_corpus_v3.json",
    "third_party/languagetool-pl/manifest.json",
    "third_party/languagetool-pl/scripts/run_stdio.sh",
    "third_party/languagetool-pl/src/main/java/org/polis/languagetool/PolisStdioServer.java",
)
BYTE_EXACT_UPSTREAM_PATHS = (
    "third_party/languagetool-pl/LICENSE-LGPL-2.1.txt",
    "third_party/languagetool-pl/sources/languagetool-core/pom.xml",
)


def run_validator(workflow: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(VALIDATOR)]
    if workflow is not None:
        command.extend(["--workflow", str(workflow)])
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )


def test_fast_ci_contract_is_valid() -> None:
    result = run_validator()

    assert result.returncode == 0, result.stderr
    assert result.stdout == "fast CI workflow contract is valid\n"


def test_fast_ci_contract_requires_full_tag_history_for_release_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in workflow
    assert "fetch-tags: true" in workflow


def test_fast_ci_contract_rejects_a_missing_required_matrix_entry(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace("ubuntu-24.04", "ubuntu-latest"),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required matrix entry" in result.stderr


def test_fast_ci_contract_rejects_x86_64_for_setup_python(tmp_path: Path) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "architecture: ${{ matrix.setup-python-architecture }}",
            "architecture: x86_64",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "setup-python architecture" in result.stderr


def test_fast_ci_contract_rejects_invalid_action_architecture(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "setup-python-architecture: x64",
            "setup-python-architecture: x86_64",
            1,
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "invalid setup-python architecture value: x86_64" in result.stderr


def test_fast_ci_contract_rejects_wrong_policy_to_action_mapping(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "setup-python-architecture: x64",
            "setup-python-architecture: x86",
            1,
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "x86_64 -> x86" in result.stderr


def test_fast_ci_contract_rejects_an_unfiltered_pytest_command(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            'pytest -m "not slow and not model"',
            "pytest",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "fast pytest marker filter" in result.stderr


def test_fast_ci_contract_rejects_a_second_unfiltered_test_command(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            'run: uv run --locked --extra dev pytest -m "not slow and not model"',
            'run: uv run --locked --extra dev pytest -m "not slow and not model"\n'
            "      - name: Run unfiltered unittest suite\n"
            "        run: uv run --locked --extra dev python -m unittest discover",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "exactly one filtered test command" in result.stderr


def test_workflow_has_only_the_filtered_pytest_test_command() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    test_commands = [
        line.strip()
        for line in workflow.splitlines()
        if line.lstrip().startswith("run:") and ("pytest" in line or "unittest" in line)
    ]

    assert test_commands == [
        'run: uv run --locked --extra dev pytest -m "not slow and not model"'
    ]


def test_workflow_actions_have_an_exact_license_review() -> None:
    review = LICENSE_REVIEW.read_text(encoding="utf-8")

    for action, commit in (
        ("actions/checkout", "34e114876b0b11c390a56381ad16ebd13914f8d5"),
        ("actions/setup-python", "ece7cb06caefa5fff74198d8649806c4678c61a1"),
        ("astral-sh/setup-uv", "37802adc94f370d6bfd71619e3f0bf239e1f3b78"),
    ):
        assert f"`{action}`" in review
        assert commit in review
        assert "MIT" in review


def test_fast_pytest_filter_deselects_slow_and_model_tests(tmp_path: Path) -> None:
    sample = tmp_path / "test_marker_selection.py"
    sample.write_text(
        """import unittest

import pytest


def test_fast_case():
    assert True


@pytest.mark.slow
class SlowCase(unittest.TestCase):
    def test_slow_case(self):
        self.assertTrue(True)


@pytest.mark.model
class ModelCase(unittest.TestCase):
    def test_model_case(self):
        self.assertTrue(True)
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--strict-markers",
            "-c",
            str(ROOT / "pyproject.toml"),
            "-m",
            "not slow and not model",
            str(sample),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 2 deselected" in result.stdout


def test_byte_stable_text_uses_effective_text_and_lf_attributes() -> None:
    result = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", *BYTE_STABLE_TEXT_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"{path}: {attribute}: {value}"
        for path in BYTE_STABLE_TEXT_PATHS
        for attribute, value in (("text", "auto"), ("eol", "lf"))
    ]


def _run_git(*args: str, cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_crlf_configured_checkout_preserves_declared_bytes_and_hashes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    checkout = tmp_path / "checkout"
    source.mkdir()
    paths = (*BYTE_STABLE_TEXT_PATHS, *BYTE_EXACT_UPSTREAM_PATHS)
    for relative_path in (".gitattributes", *paths):
        target = source / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, target)

    _run_git("init", "--quiet", cwd=source)
    _run_git("config", "user.email", "ci@example.invalid", cwd=source)
    _run_git("config", "user.name", "Fast CI regression", cwd=source)
    _run_git("config", "core.autocrlf", "false", cwd=source)
    _run_git("add", ".", cwd=source)
    _run_git("commit", "--quiet", "-m", "fixture", cwd=source)

    _run_git(
        "-c",
        "core.autocrlf=true",
        "-c",
        "core.eol=crlf",
        "clone",
        "--quiet",
        "--no-local",
        str(source),
        str(checkout),
        cwd=tmp_path,
    )

    for relative_path in paths:
        expected = (source / relative_path).read_bytes()
        actual = (checkout / relative_path).read_bytes()
        assert actual == expected, relative_path
        assert hashlib.sha256(actual).digest() == hashlib.sha256(expected).digest()


def test_platform_specific_release_checks_have_versioned_owners() -> None:
    compatibility = COMPATIBILITY_POLICY.read_text(encoding="utf-8")
    distribution = DISTRIBUTION_VERIFICATION.read_text(encoding="utf-8")

    assert "Platform verification profile 1.0" in compatibility
    assert "`tests/test_cli.py`" in compatibility
    assert "`tests/test_languagetool_vendor_artifacts.py`" in compatibility
    assert "POSIX executable bits" in compatibility
    assert "macOS network-denial evidence" in compatibility
    assert "separate release-gate verification" in compatibility
    assert "`PYTHONIOENCODING=cp1252`" in distribution
    assert "`tests/test_release_distribution_installation.py`" in distribution
    assert "platform-native line endings" in distribution
    assert "python scripts/verify_distribution_install.py --dist dist" in distribution


def test_vendored_upstream_text_is_exempt_from_checkout_normalization() -> None:
    result = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "eol",
            "--",
            *BYTE_EXACT_UPSTREAM_PATHS,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"{path}: {attribute}: unset"
        for path in BYTE_EXACT_UPSTREAM_PATHS
        for attribute in ("text", "eol")
    ]
