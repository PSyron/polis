from __future__ import annotations

import hashlib
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
MAINTAINED_V1_DOCUMENTS = (
    "README.md",
    "docs/project/RISKS.md",
    "docs/architecture/README.md",
    "docs/architecture/protocols.md",
    "docs/compatibility.md",
    "docs/customization.md",
    "docs/development/dependency-licenses.md",
    "docs/distribution-verification.md",
    "docs/evaluation-dataset.md",
    "docs/limitations.md",
    "docs/offline-operation.md",
    "docs/prerelease-candidate.md",
    "docs/privacy.md",
    "docs/privacy-audit.md",
    "docs/public-api.md",
    "docs/quick-start.md",
    "docs/rules.md",
    "examples/polis.toml",
)
OBSOLETE_V1_INSTRUCTIONS = (
    "docs/architecture/contextual-inflection-routing-design.md",
    "docs/architecture/finetuning-dataset.md",
    "docs/architecture/languagetool-rule-inventory-design.md",
    "docs/architecture/sentence-category-routing-design.md",
    "docs/development/research-workflow.md",
    "docs/llm-corrected-text-contract.md",
    "docs/llm-prompt-response-contract.md",
    "docs/llm-quality-gates.md",
    "[backend]",
    "[contextual_inflection]",
    "[language_tool]",
    "[vendored_language_tool]",
    "contextual_inflection_stdio_path",
    "contextual_inflection_timeout_seconds",
    "language_tool_timeout_seconds",
    "language_tool_url",
    "languagetool.pl",
    "specialist_engine",
    "third_party/languagetool-pl",
    "use_local_heuristic_backend",
    "vendored_language_tool_stdio_path",
    "vendored_language_tool_timeout_seconds",
    'pytest -m "not research and not slow and not model"',
)
EXPECTED_V1_RULE_SOURCE_ORDER = (
    "rule:agreement.copula",
    "rule:spelling.jestes",
    "rule:spelling.wlasnie",
    "rule:spelling.zeby",
    "rule:syntax.comma_space",
    "rule:syntax.list_space",
    "rule:syntax.missing_correlative",
    "rule:syntax.missing_reflexive",
    "rule:syntax.quote_space",
    "rule:syntax.sentence_space",
)
ACTIVE_INSTRUCTION_VERB_PATTERN = (
    r"\b(?:uruchom|skonfiguruj|włącz|użyj|zainstaluj|wykonaj)\b"
)
ACTIVE_INSTRUCTION_VERB = re.compile(
    ACTIVE_INSTRUCTION_VERB_PATTERN,
    re.IGNORECASE,
)
INACTIVE_REMOVED_V1_REFERENCE_CONTEXT = re.compile(
    r"\b(?:odrzuc\w*|rejected|removed|usunięt\w*|historycz\w*|"
    r"archiw\w*|not\s+supported)\b",
    re.IGNORECASE,
)
ACTIVE_REMOVED_V1_CAPABILITY_INSTRUCTION = re.compile(
    r"(" + ACTIVE_INSTRUCTION_VERB_PATTERN + r")[^.!?\n]{0,96}"
    r"\b(?:"
    r"llm|serwer\w*\s+model\w*|model\w*\s+server\w*|"
    r"languagetool|jav(?:a|ę|ie|y)|"
    r"kontekstow\w*\s+fleksj\w*|contextual[_ -]inflection|"
    r"runner\w*\s+bada\w*|research\s+runner|"
    r"inspekcj\w*\s+katalog\w*\s+reguł|catalog\s+inspection"
    r")\b",
    re.IGNORECASE,
)
REMOVED_TASK_13_GUIDES = frozenset(
    {
        "docs/architecture/contextual-inflection-routing-design.md",
        "docs/architecture/finetuning-dataset.md",
        "docs/architecture/languagetool-rule-inventory-design.md",
        "docs/architecture/sentence-category-routing-design.md",
        "docs/development/research-workflow.md",
        "docs/llm-corrected-text-contract.md",
        "docs/llm-prompt-response-contract.md",
        "docs/llm-quality-gates.md",
    }
)
FROZEN_REVIEW_CHECKLIST_SHA256 = {
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


def _local_clause(text: str, start: int, end: int) -> str:
    clause_start = max(text.rfind(separator, 0, start) for separator in ".!?;") + 1
    clause_end = len(text)
    for separator in ".!?;":
        separator_index = text.find(separator, end)
        if separator_index != -1:
            clause_end = min(clause_end, separator_index)
    return text[clause_start:clause_end]


def _is_directly_negated_active_verb(text: str, verb_start: int) -> bool:
    return re.search(r"\bnie\s+$", text[:verb_start], re.IGNORECASE) is not None


def _has_active_instruction_verb(text: str) -> bool:
    return any(
        not _is_directly_negated_active_verb(text, match.start())
        for match in ACTIVE_INSTRUCTION_VERB.finditer(text)
    )


def _has_only_directly_negated_active_verbs(text: str) -> bool:
    verb_matches = tuple(ACTIVE_INSTRUCTION_VERB.finditer(text))
    return bool(verb_matches) and all(
        _is_directly_negated_active_verb(text, match.start()) for match in verb_matches
    )


def _has_active_removed_v1_capability_instruction(text: str) -> bool:
    return any(
        not _is_directly_negated_active_verb(text, match.start(1))
        for match in ACTIVE_REMOVED_V1_CAPABILITY_INSTRUCTION.finditer(text)
    )


def _requires_removed_v1_reference_detection(text: str, reference: str) -> bool:
    normalized = text.casefold()
    normalized_reference = reference.casefold()
    search_start = 0
    while (reference_index := normalized.find(normalized_reference, search_start)) >= 0:
        clause = _local_clause(
            text,
            reference_index,
            reference_index + len(reference),
        )
        if _has_active_instruction_verb(clause):
            return True
        if _has_only_directly_negated_active_verbs(clause):
            search_start = reference_index + len(reference)
            continue
        if not INACTIVE_REMOVED_V1_REFERENCE_CONTEXT.search(clause):
            return True
        search_start = reference_index + len(reference)
    return False


def _find_active_removed_v1_instructions(text: str) -> tuple[str, ...]:
    matches = [
        instruction
        for instruction in OBSOLETE_V1_INSTRUCTIONS
        if _requires_removed_v1_reference_detection(text, instruction)
    ]
    if _has_active_removed_v1_capability_instruction(text):
        matches.append("removed_v1_capability_instruction")
    return tuple(matches)


@pytest.mark.parametrize(
    "instruction",
    (
        "Uruchom serwer LanguageTool w Javie.",
        "Zainstaluj Javę.",
        "Użyj Javy.",
        "Skonfiguruj lokalny LLM.",
        "Skonfiguruj lokalny model server.",
        "Włącz routing kontekstowej fleksji.",
        "Uruchom runner badań przed wydaniem.",
        "Wykonaj inspekcję katalogu reguł.",
    ),
)
def test_active_removed_v1_capability_instructions_are_detected(
    instruction: str,
) -> None:
    assert _find_active_removed_v1_instructions(instruction)


@pytest.mark.parametrize(
    "statement",
    (
        "Runtime nie wymaga modelu, Javy ani sieci.",
        "Nie uruchom serwera LanguageTool.",
        "Nie użyj language_tool_url.",
        "Historyczne badania pozostają wyłącznie w archiwum.",
        "Legacy table `[language_tool]` is rejected in Polis v1.",
        "Pole language_tool_url jest odrzucone w Polis v1.",
        "Odwołanie do docs/llm-prompt-response-contract.md jest odrzucone.",
    ),
)
def test_non_goal_and_rejection_statements_are_not_active_instructions(
    statement: str,
) -> None:
    assert _find_active_removed_v1_instructions(statement) == ()


def test_active_exact_reference_is_not_masked_by_an_inactive_occurrence() -> None:
    text = "language_tool_url jest historyczne. Skonfiguruj language_tool_url."

    assert _find_active_removed_v1_instructions(text) == ("language_tool_url",)


@pytest.mark.parametrize(
    "removed_reference",
    (
        "docs/llm-prompt-response-contract.md",
        "docs/architecture/languagetool-rule-inventory-design.md",
        "language_tool_url",
        "vendored_language_tool_timeout_seconds",
    ),
)
def test_exact_removed_v1_paths_and_configuration_are_detected(
    removed_reference: str,
) -> None:
    assert removed_reference in _find_active_removed_v1_instructions(
        f"Zobacz {removed_reference}."
    )


def test_rules_documentation_order_matches_default_registry() -> None:
    documented_sources = tuple(
        re.findall(
            r"^\| `(rule:[^`]+)` \|",
            (ROOT / "docs/rules.md").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert documented_sources == EXPECTED_V1_RULE_SOURCE_ORDER


def test_configuration_docs_describe_exact_legacy_section_rejection() -> None:
    expected = (
        "[backend]",
        "[language_tool]",
        "[contextual_inflection]",
        "[vendored_language_tool]",
    )
    for relative_path in ("README.md", "docs/offline-operation.md", "docs/privacy.md"):
        documentation = (ROOT / relative_path).read_text(encoding="utf-8")

        assert "[analysis]" in documentation
        assert "categories" in documentation
        assert "minimum_confidence" in documentation
        assert all(section in documentation for section in expected)
        assert "ConfigurationError" in documentation
        assert "ignoruje" in documentation.casefold()


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


def test_maintained_v1_documents_have_no_active_removed_runtime_instructions() -> None:
    stale_references: dict[str, list[str]] = {}
    for relative_path in MAINTAINED_V1_DOCUMENTS:
        contents = (ROOT / relative_path).read_text(encoding="utf-8")
        matches = _find_active_removed_v1_instructions(contents)
        if matches:
            stale_references[relative_path] = list(matches)

    assert stale_references == {}


def test_task_13_removed_guides_are_absent() -> None:
    assert len(REMOVED_TASK_13_GUIDES) == 8
    assert all(
        not (ROOT / relative_path).exists() for relative_path in REMOVED_TASK_13_GUIDES
    )


def test_maintained_v1_document_links_resolve_locally() -> None:
    for relative_path in MAINTAINED_V1_DOCUMENTS:
        document = ROOT / relative_path
        if document.suffix != ".md":
            continue
        for raw_target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            if raw_target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative_target = unquote(raw_target.split("#", maxsplit=1)[0])
            if relative_target:
                assert (document.parent / relative_target).is_file(), (
                    f"broken local link in {relative_path}: {raw_target}"
                )


def test_frozen_review_checklists_match_their_protected_hashes() -> None:
    assert set(FROZEN_REVIEW_CHECKLIST_SHA256) == FROZEN_REVIEW_CHECKLISTS
    for relative_path, expected_hash in FROZEN_REVIEW_CHECKLIST_SHA256.items():
        contents = (ROOT / relative_path).read_bytes()
        assert hashlib.sha256(contents).hexdigest() == expected_hash


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


def test_validator_discovers_required_artifact_omitted_from_exact_paths(
    tmp_path: Path,
) -> None:
    protected_path = "experiments/example/README.md"
    _initialize_repository(tmp_path, (protected_path,))
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "broad-experiments",
                "disposition": "translate_polish",
                "wave": "runtime-and-research-guides",
                "paths": [],
                "prefixes": ["experiments/"],
            }
        ],
    )

    result = _run_validator(tmp_path, inventory)

    assert result.returncode == 1
    assert (
        "required protected artifact must use an exact "
        "retain_research_evidence rule: experiments/example/README.md"
    ) in result.stderr


def test_validator_combines_discovery_with_generic_protected_rule_checks(
    tmp_path: Path,
) -> None:
    protected_path = "experiments/example/README.md"
    _initialize_repository(tmp_path, (protected_path,))
    inventory = _write_inventory(
        tmp_path,
        rules=[
            {
                "id": "research-evidence",
                "disposition": "retain_research_evidence",
                "wave": "protected",
                "paths": [protected_path],
                "prefixes": [],
            },
            {
                "id": "broad-experiments",
                "disposition": "translate_polish",
                "wave": "runtime-and-research-guides",
                "paths": [],
                "prefixes": ["experiments/"],
            },
        ],
    )

    result = _run_validator(tmp_path, inventory, output_json=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dispositions"] == {"retain_research_evidence": 1}
