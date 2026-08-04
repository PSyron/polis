"""Regression gate for the verified v2 research archive baseline."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "docs/project/v2-research-archive-manifest.md"

REQUIRED_METADATA = {
    "repository": "PSyron/polis",
    "branch": "feature/v2-research-archive",
}
REQUIRED_CHECKLIST_PATHS = {
    "experiments/",
    "data/",
    "third_party/languagetool-pl/",
    "src/polis/llm/",
    "src/polis/evaluation/",
    "docs/architecture/decisions/",
    "docs/release-notes/",
    "docs/superpowers/",
}


def _metadata_and_checklist(document: str) -> tuple[dict[str, str], set[str]]:
    metadata = dict(
        re.findall(
            r"^(repository|branch|baseline_sha|remote_ref_sha): (.+)$",
            document,
            re.MULTILINE,
        )
    )
    checklist = set(re.findall(r"^- \[x\] `([^`]+)`$", document, re.MULTILINE))
    return metadata, checklist


def _assert_manifest_contract(document: str) -> None:
    metadata, checklist = _metadata_and_checklist(document)

    for field, expected_value in REQUIRED_METADATA.items():
        assert metadata.get(field) == expected_value

    baseline_sha = metadata.get("baseline_sha")
    assert baseline_sha is not None
    assert re.fullmatch(r"[0-9a-f]{40}", baseline_sha)
    assert metadata.get("remote_ref_sha") == baseline_sha
    assert REQUIRED_CHECKLIST_PATHS <= checklist


def test_manifest_records_the_immutable_v2_archive_baseline() -> None:
    assert MANIFEST_PATH.is_file(), "missing v2 research archive manifest"
    _assert_manifest_contract(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "document",
    [
        "repository: PSyron/polis\nbranch: feature/v2-research-archive\n",
        "\n".join(
            [
                "repository: PSyron/polis",
                "branch: feature/v2-research-archive",
                "baseline_sha: origin/main",
                "remote_ref_sha: origin/main",
            ]
        ),
    ],
)
def test_manifest_rejects_missing_or_symbolic_baseline_sha(document: str) -> None:
    with pytest.raises(AssertionError):
        _assert_manifest_contract(document)


def test_manifest_rejects_an_incomplete_presence_checklist() -> None:
    document = "\n".join(
        [
            "repository: PSyron/polis",
            "branch: feature/v2-research-archive",
            "baseline_sha: 0123456789abcdef0123456789abcdef01234567",
            "remote_ref_sha: 0123456789abcdef0123456789abcdef01234567",
            "- [x] `experiments/`",
        ]
    )

    with pytest.raises(AssertionError):
        _assert_manifest_contract(document)
