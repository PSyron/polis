"""Regression gate for the verified v2 research archive baseline."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "docs/project/v2-research-archive-manifest.md"
ARCHIVE_BASELINE_SHA = "ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8"
EXPECTED_METADATA = {
    "repository": "PSyron/polis",
    "branch": "feature/v2-research-archive",
    "baseline_sha": ARCHIVE_BASELINE_SHA,
    "remote_ref_sha": ARCHIVE_BASELINE_SHA,
}
REQUIRED_CHECKLIST_PATHS = frozenset(
    {
        "experiments/",
        "data/",
        "third_party/languagetool-pl/",
        "src/polis/llm/",
        "src/polis/evaluation/",
        "docs/architecture/decisions/",
        "docs/release-notes/",
        "docs/superpowers/",
    }
)
PROTECTED_MARKER_PATHS = frozenset(
    {
        "data/finetuning/bielik_1_5b_v1/manifest.json",
        "experiments/contextual_inflection_routing/frozen_router.json",
        "experiments/contextual_inflection_routing/holdout.started",
        "experiments/contextual_inflection_routing/report.json",
        "experiments/languagetool_rule_inventory/frozen_allowlist.json",
        "experiments/languagetool_rule_inventory/holdout.started",
        "experiments/languagetool_rule_inventory/report.json",
        "experiments/languagetool_stdio_session/report.json",
        "experiments/llm_backends/results.json",
        "experiments/nlp_dependencies/results.json",
        "experiments/qlora_benchmark/report.json",
        "experiments/residual_syntax_rules/frozen_rules.json",
        "experiments/residual_syntax_rules/holdout.started",
        "experiments/residual_syntax_rules/report.json",
        "experiments/sentence_category_routing/report.json",
        "experiments/sentence_safety_gate/frozen_gate.json",
        "experiments/sentence_safety_gate/holdout.started",
        "experiments/sentence_safety_gate/report.json",
        "experiments/sentence_safety_gate_v2/report.json",
        "experiments/sentence_syntax_qualification/report.json",
        "experiments/two_pass_qwen35/report.json",
        "third_party/languagetool-pl/manifest.json",
    }
)
ACCEPTED_ADR_PATHS = frozenset(
    {
        "docs/architecture/decisions/0001-python-platform-licensing-policy.md",
        "docs/architecture/decisions/0002-polish-nlp-dependency-strategy.md",
        "docs/architecture/decisions/0003-public-api-and-exception-contract.md",
        "docs/architecture/decisions/0004-local-llm-backend-selection.md",
        "docs/architecture/decisions/0005-real-local-polish-model-benchmark.md",
        "docs/architecture/decisions/0006-local-languagetool-benchmark.md",
        "docs/architecture/decisions/0007-vendored-polish-languagetool-module.md",
        "docs/architecture/decisions/0008-hybrid-correction-policy.md",
        "docs/architecture/decisions/0009-specialist-prompt-benchmark.md",
        "docs/architecture/decisions/0010-inflection-candidate-generation.md",
        "docs/architecture/decisions/0011-reject-bielik-1.5b-qlora.md",
        "docs/architecture/decisions/0012-reject-constrained-qwen35-2b.md",
        "docs/architecture/decisions/0013-reject-sentence-category-routing.md",
        "docs/architecture/decisions/0014-qualify-broader-polish-languagetool-rules.md",
        "docs/architecture/decisions/0015-qualify-contextual-inflection-routing.md",
        "docs/architecture/decisions/0016-reject-qwen17-sentence-syntax-route.md",
        "docs/architecture/decisions/0017-reviewable-residual-sentence-syntax-rules.md",
        "docs/architecture/decisions/0018-runtime-composition-protocols.md",
        "docs/architecture/decisions/0019-evaluation-namespace-compatibility.md",
        "docs/architecture/decisions/0020-runtime-first-product-charter.md",
        "docs/architecture/decisions/0021-rule-catalog-ownership.md",
    }
)
RELEASE_NOTE_PATHS = frozenset(
    {
        "docs/release-notes/0.1.0-erratum.md",
        "docs/release-notes/0.1.0.md",
    }
)
FROZEN_CHECKLIST_SHA256 = {
    "docs/evaluation-corpus-v3-review-checklist.md": (
        "9793329b5ee1f7f71d2de6a0e652f0a67eff5d8f795b150ba1ff91b81db94847"
    ),
    "docs/evaluation-safety-corpus-v1-review-checklist.md": (
        "6aef2d479c4806be2b3f3379aad20ef2bc695c04ade93c331bb3edaacdd9fc2e"
    ),
    "docs/evaluation-safety-corpus-v2-review-checklist.md": (
        "b63e8ab7beaee16984c28c80dfea84b95ba740dbb26b67248be90a8adcf3eae9"
    ),
}


def _section(document: str, heading: str) -> str:
    match = re.search(
        rf"^{re.escape(heading)}\n(?P<body>.*?)(?=^#+ |\Z)",
        document,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing section {heading}"
    return match.group("body")


def _listed_paths(document: str, heading: str) -> frozenset[str]:
    return frozenset(
        re.findall(r"^- `([^`]+)`$", _section(document, heading), re.MULTILINE)
    )


def _frozen_checklists(document: str) -> dict[str, str]:
    return dict(
        re.findall(
            r"^- `([^`]+)`: `([0-9a-f]{64})`$",
            _section(document, "### Zamrożone checklisty"),
            re.MULTILINE,
        )
    )


def _assert_manifest_contract(document: str) -> None:
    metadata = dict(
        re.findall(
            r"^(repository|branch|baseline_sha|remote_ref_sha): (.+)$",
            document,
            re.MULTILINE,
        )
    )
    checklist = frozenset(re.findall(r"^- \[x\] `([^`]+)`$", document, re.MULTILINE))

    assert metadata == EXPECTED_METADATA
    assert REQUIRED_CHECKLIST_PATHS <= checklist
    assert _listed_paths(document, "### Markery ochronne") == PROTECTED_MARKER_PATHS
    assert _listed_paths(document, "### Zaakceptowane ADR-y") == ACCEPTED_ADR_PATHS
    assert (
        _listed_paths(document, "### Opublikowane release notes") == RELEASE_NOTE_PATHS
    )
    assert _frozen_checklists(document) == FROZEN_CHECKLIST_SHA256


def _manifest_document() -> str:
    assert MANIFEST_PATH.is_file(), "missing v2 research archive manifest"
    return MANIFEST_PATH.read_text(encoding="utf-8")


def test_manifest_records_the_exact_immutable_v2_archive_baseline() -> None:
    _assert_manifest_contract(_manifest_document())


@pytest.mark.parametrize("field", ["baseline_sha", "remote_ref_sha"])
def test_manifest_rejects_a_changed_archive_sha(field: str) -> None:
    document = _manifest_document()
    mutated = document.replace(
        f"{field}: {ARCHIVE_BASELINE_SHA}", f"{field}: {'0' * 40}", 1
    )

    with pytest.raises(AssertionError):
        _assert_manifest_contract(mutated)


@pytest.mark.parametrize(
    "path",
    sorted(PROTECTED_MARKER_PATHS | ACCEPTED_ADR_PATHS | RELEASE_NOTE_PATHS),
)
def test_manifest_rejects_any_missing_protected_path(path: str) -> None:
    document = _manifest_document()
    mutated = document.replace(f"- `{path}`\n", "", 1)
    assert mutated != document

    with pytest.raises(AssertionError):
        _assert_manifest_contract(mutated)


@pytest.mark.parametrize("path, sha256", sorted(FROZEN_CHECKLIST_SHA256.items()))
def test_manifest_rejects_a_missing_or_changed_frozen_checklist_digest(
    path: str, sha256: str
) -> None:
    document = _manifest_document()

    for mutated in (
        document.replace(f"- `{path}`: `{sha256}`\n", "", 1),
        document.replace(f"- `{path}`: `{sha256}`", f"- `{path}`: `{'0' * 64}`", 1),
    ):
        assert mutated != document
        with pytest.raises(AssertionError):
            _assert_manifest_contract(mutated)
