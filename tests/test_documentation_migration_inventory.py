from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_documentation_inventory.py"
INVENTORY = ROOT / "docs" / "project" / "documentation-migration-inventory.json"
POLICY_DOCUMENTS = (
    ROOT / "AGENTS.md",
    ROOT / "PROMPT.md",
    ROOT / "docs" / "project" / "ROADMAP.md",
    ROOT / "docs" / "project" / "DOCUMENTATION-ROADMAP.md",
)
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
EVIDENCE_ROOTS = (
    "data/",
    "experiments/",
    "src/polis/evaluation/",
    "third_party/languagetool-pl/",
)
PROTECTED_EVIDENCE_FILENAMES = frozenset(
    {
        "README.md",
        "config.json",
        "report.json",
        "results.json",
        "assembly.json",
        "cases.json",
        "holdout.started",
        "evaluated_source.json",
        "pre_evaluation_inputs.patch",
        "LICENSE-LGPL-2.1.txt",
        "NOTICE",
        "UPSTREAM.md",
        "BENCHMARK.md",
        "manifest.json",
        "0001-reproducible-build-metadata.patch",
    }
)
PROTECTED_DISPOSITIONS = frozenset(
    {
        "retain_historical_evidence",
        "retain_research_evidence",
        "retain_upstream_original",
    }
)
FROZEN_REVIEW_CHECKLISTS = frozenset(
    {
        "docs/evaluation-corpus-v3-review-checklist.md",
        "docs/evaluation-safety-corpus-v1-review-checklist.md",
        "docs/evaluation-safety-corpus-v2-review-checklist.md",
    }
)


def _run_validator(
    root: Path,
    inventory: Path,
    *,
    output_json: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(VALIDATOR),
        "--root",
        str(root),
        "--inventory",
        str(inventory),
    ]
    if output_json:
        command.append("--json")
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _initialize_repository(root: Path, markdown_paths: tuple[str, ...]) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for relative_path in markdown_paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative_path}\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", *markdown_paths], cwd=root, check=True)


def _write_inventory(
    root: Path,
    rules: list[dict[str, Any]],
) -> Path:
    path = root / "inventory.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "issue": 158,
                "policy_version": "1.0",
                "rules": rules,
            }
        ),
        encoding="utf-8",
    )
    return path


def _effective_disposition(inventory: dict[str, Any], path: str) -> str | None:
    for rule in inventory["rules"]:
        if path in rule["paths"] or any(
            path.startswith(prefix) for prefix in rule["prefixes"]
        ):
            return str(rule["disposition"])
    return None


def _tracked_paths(*pathspecs: str) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *pathspecs],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return {path.decode("utf-8") for path in result.stdout.split(b"\0") if path}


def _protected_exact_paths(inventory: dict[str, Any]) -> set[str]:
    return {
        path
        for rule in inventory["rules"]
        if rule["disposition"] in PROTECTED_DISPOSITIONS
        for path in rule["paths"]
    }


def test_repository_markdown_inventory_is_complete() -> None:
    result = _run_validator(ROOT, INVENTORY)

    assert result.returncode == 0, result.stderr
    assert "documentation migration inventory is complete" in result.stdout


def test_inventory_paths_and_local_policy_links_exist() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    for rule in inventory["rules"]:
        for relative_path in rule["paths"]:
            assert (ROOT / relative_path).is_file(), relative_path

    for document in POLICY_DOCUMENTS:
        for raw_target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            if raw_target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative_target = unquote(raw_target.split("#", maxsplit=1)[0])
            if relative_target:
                assert (document.parent / relative_target).is_file(), (
                    f"broken local link in {document.relative_to(ROOT)}: {raw_target}"
                )


def test_production_inventory_protects_immutable_and_upstream_documents() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    expected = {
        "CHANGELOG.md": "retain_historical_evidence",
        "data/finetuning/bielik_1_5b_v1/README.md": "retain_research_evidence",
        "docs/performance-baseline.md": "retain_research_evidence",
        "docs/quality-baseline.md": "retain_research_evidence",
        "docs/release-notes/0.1.0.md": "retain_historical_evidence",
        "docs/superpowers/plans/2026-07-20-issue-1-policy.md": (
            "retain_historical_evidence"
        ),
        "experiments/real_llm_benchmark/README.md": "retain_research_evidence",
        "third_party/languagetool-pl/README.md": "retain_upstream_original",
    }

    for path, disposition in expected.items():
        assert _effective_disposition(inventory, path) == disposition, path

    for adr in (ROOT / "docs" / "architecture" / "decisions").glob("*.md"):
        path = adr.relative_to(ROOT).as_posix()
        assert _effective_disposition(inventory, path) == (
            "retain_historical_evidence"
        ), path


def test_production_inventory_uses_exact_evidence_paths_before_removable_trees() -> (
    None
):
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    exact_paths = _protected_exact_paths(inventory)
    tracked_candidates = {
        path
        for path in _tracked_paths(*EVIDENCE_ROOTS)
        if Path(path).name in PROTECTED_EVIDENCE_FILENAMES
        or Path(path).name.startswith("frozen_")
        and Path(path).suffix == ".json"
    }
    historical_paths = (
        _tracked_paths("docs/architecture/decisions/")
        | _tracked_paths("docs/release-notes/")
        | _tracked_paths("docs/superpowers/")
        | {"CHANGELOG.md"}
    )

    assert tracked_candidates | historical_paths | FROZEN_REVIEW_CHECKLISTS <= (
        exact_paths
    )
    assert all(
        not rule["prefixes"]
        for rule in inventory["rules"]
        if rule["disposition"] in PROTECTED_DISPOSITIONS
    )
    assert (
        _effective_disposition(
            inventory, "experiments/contextual_inflection_routing/run.py"
        )
        is None
    )
    assert (
        _effective_disposition(
            inventory,
            "third_party/languagetool-pl/src/main/java/org/example/Rule.java",
        )
        is None
    )


def test_frozen_review_checklists_are_protected_exact_paths() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    exact_paths = _protected_exact_paths(inventory)

    assert FROZEN_REVIEW_CHECKLISTS <= exact_paths
    for path in FROZEN_REVIEW_CHECKLISTS:
        assert _effective_disposition(inventory, path) == "retain_research_evidence"


def test_frozen_baselines_use_an_earlier_protected_inventory_rule() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    protected_paths = {
        "docs/performance-baseline.md",
        "docs/quality-baseline.md",
    }
    matching_rules = [
        rule for rule in inventory["rules"] if protected_paths & set(rule["paths"])
    ]

    assert len(matching_rules) == 1
    protected_rule = matching_rules[0]
    assert set(protected_rule["paths"]) == protected_paths
    assert protected_rule["disposition"] == "retain_research_evidence"
    assert protected_rule["wave"] == "protected"
    assert inventory["rules"].index(protected_rule) < next(
        index
        for index, rule in enumerate(inventory["rules"])
        if "docs/" in rule["prefixes"]
    )


def test_validator_rejects_unknown_dispositions(tmp_path: Path) -> None:
    _initialize_repository(tmp_path, ("README.md",))
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "misspelled-disposition",
                "disposition": "translate_polsh",
                "wave": "public-entry",
                "paths": ["README.md"],
                "prefixes": [],
            }
        ],
    )

    result = _run_validator(tmp_path, inventory)

    assert result.returncode == 1
    assert "unsupported disposition: translate_polsh" in result.stderr


def test_validator_rejects_unknown_waves(tmp_path: Path) -> None:
    _initialize_repository(tmp_path, ("README.md",))
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "misspelled-wave",
                "disposition": "translate_polish",
                "wave": "public-entyr",
                "paths": ["README.md"],
                "prefixes": [],
            }
        ],
    )

    result = _run_validator(tmp_path, inventory)

    assert result.returncode == 1
    assert "unsupported wave: public-entyr" in result.stderr


def test_validator_rejects_an_unclassified_tracked_markdown(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path, ("notes/unclassified.md",))
    inventory = _write_inventory(tmp_path, rules=[])

    result = _run_validator(tmp_path, inventory)

    assert result.returncode == 1
    assert "unclassified Markdown path: notes/unclassified.md" in result.stderr


def test_validator_uses_specific_protected_rules_before_broad_docs_rules(
    tmp_path: Path,
) -> None:
    _initialize_repository(
        tmp_path,
        (
            "docs/superpowers/plans/example.md",
            "docs/public-api.md",
        ),
    )
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "historical-plans",
                "disposition": "retain_historical_evidence",
                "wave": "protected",
                "paths": ["docs/superpowers/plans/example.md"],
                "prefixes": [],
            },
            {
                "id": "maintained-docs",
                "disposition": "translate_polish",
                "wave": "runtime-and-research-guides",
                "paths": [],
                "prefixes": ["docs/"],
            },
        ],
    )

    result = _run_validator(tmp_path, inventory, output_json=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dispositions"] == {
        "retain_historical_evidence": 1,
        "translate_polish": 1,
    }


@pytest.mark.parametrize("disposition", sorted(PROTECTED_DISPOSITIONS))
def test_validator_rejects_prefixes_on_every_protected_disposition(
    disposition: str,
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path, ("notes/example.md",))
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "protected-prefix",
                "disposition": disposition,
                "wave": "protected",
                "paths": [],
                "prefixes": ["notes/"],
            }
        ],
    )

    result = _run_validator(tmp_path, inventory)

    assert result.returncode == 1
    assert "protected rule must not use prefixes: protected-prefix" in result.stderr


@pytest.mark.parametrize("disposition", sorted(PROTECTED_DISPOSITIONS))
@pytest.mark.parametrize(
    "protected_path",
    (
        "docs/performance-baseline.md",
        "docs/quality-baseline.md",
        "docs/project/v2-research-archive-manifest.md",
    ),
)
def test_validator_rejects_every_protected_exact_path_shadowed_by_a_prefix(
    disposition: str,
    protected_path: str,
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path, (protected_path,))
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "broad-docs",
                "disposition": "translate_polish",
                "wave": "runtime-and-research-guides",
                "paths": [],
                "prefixes": ["docs/"],
            },
            {
                "id": "protected-exact",
                "disposition": disposition,
                "wave": "protected",
                "paths": [protected_path],
                "prefixes": [],
            },
        ],
    )

    result = _run_validator(tmp_path, inventory)

    assert result.returncode == 1
    assert (
        "protected exact path is shadowed by an earlier rule: "
        f"protected-exact: {protected_path} -> broad-docs"
    ) in result.stderr
