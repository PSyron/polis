from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.morphology_provider_json import (
    ContractError,
    JsonValue,
    canonical_bytes,
    mapping,
    read_json,
)
from scripts.provider_independent_spelling_qualification import (
    matrix_digest,
    validate_documents,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = (
    ROOT / "tests/fixtures/v1/provider_independent_spelling_qualification.json"
)
MATRIX_PATH = ROOT / "docs/provider-independent-spelling-qualification-v1.json"
MANIFEST_PATH = EVIDENCE_PATH.with_suffix(".manifest.json")
EXPECTED_CANDIDATE_IDS = [f"PI-TYPO-{number:02d}" for number in range(1, 7)]


def _typed_mapping(value: JsonValue, context: str) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    result.update(mapping(value, context))
    return result


def _load(path: Path) -> dict[str, JsonValue]:
    return _typed_mapping(read_json(path), str(path))


def _candidate_ids(document: dict[str, JsonValue], key: str) -> list[str]:
    values = document[key]
    assert isinstance(values, list)
    identifiers: list[str] = []
    for value in values:
        assert isinstance(value, dict)
        identifier = value["id"]
        assert isinstance(identifier, str)
        identifiers.append(identifier)
    return identifiers


def _documents() -> tuple[
    dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]
]:
    return _load(EVIDENCE_PATH), _load(MANIFEST_PATH), _load(MATRIX_PATH)


def _first_candidate(evidence: dict[str, JsonValue]) -> dict[str, JsonValue]:
    candidates = evidence["candidates"]
    assert isinstance(candidates, list)
    return _typed_mapping(candidates[0], "first candidate")


def _first_matrix_row(matrix: dict[str, JsonValue]) -> dict[str, JsonValue]:
    rows = matrix["rows"]
    assert isinstance(rows, list)
    return _typed_mapping(rows[0], "first matrix row")


def _write_matrix_digest(matrix: dict[str, JsonValue]) -> None:
    digest = matrix_digest(matrix)
    integrity = mapping(matrix["integrity"], "matrix integrity")
    approval = mapping(matrix["approval"], "matrix approval")
    integrity["matrix_sha256"] = digest
    approval["bound_matrix_sha256"] = digest
    rows = matrix["rows"]
    assert isinstance(rows, list)
    for raw_row in rows:
        row = mapping(raw_row, "matrix row")
        decision = mapping(row["decision"], "row decision")
        row_approval = mapping(
            decision["maintainer_approval"], "row maintainer approval"
        )
        row_approval["bound_matrix_sha256"] = digest


def _write_manifest_digest(
    evidence: dict[str, JsonValue], manifest: dict[str, JsonValue]
) -> None:
    manifest["evidence_sha256"] = hashlib.sha256(canonical_bytes(evidence)).hexdigest()


def test_issue_402_publishes_exact_candidate_universe() -> None:
    evidence = _load(EVIDENCE_PATH)
    matrix = _load(MATRIX_PATH)

    assert _candidate_ids(evidence, "candidates") == EXPECTED_CANDIDATE_IDS
    assert _candidate_ids(matrix, "rows") == EXPECTED_CANDIDATE_IDS


def test_each_candidate_covers_lower_title_and_uppercase_findings() -> None:
    evidence = _load(EVIDENCE_PATH)
    candidates = evidence["candidates"]
    assert isinstance(candidates, list)

    for raw_candidate in candidates:
        candidate = mapping(raw_candidate, "candidate")
        incorrect = candidate["incorrect_surface"]
        assert isinstance(incorrect, str)
        expected_originals = {incorrect, incorrect.capitalize(), incorrect.upper()}
        positives = candidate["positive_cases"]
        assert isinstance(positives, list)
        actual_originals: set[str] = set()
        for raw_case in positives:
            case = mapping(raw_case, "positive case")
            findings = case["expected_findings"]
            assert isinstance(findings, list)
            for raw_finding in findings:
                finding = mapping(raw_finding, "expected finding")
                original = finding["original"]
                assert isinstance(original, str)
                actual_originals.add(original)
        assert expected_originals <= actual_originals


def test_metalinguistic_questions_are_not_positive_evidence() -> None:
    evidence = _load(EVIDENCE_PATH)
    candidates = evidence["candidates"]
    assert isinstance(candidates, list)

    for raw_candidate in candidates:
        candidate = mapping(raw_candidate, "candidate")
        positives = candidate["positive_cases"]
        assert isinstance(positives, list)
        for raw_case in positives:
            case = mapping(raw_case, "positive case")
            text = case["text"]
            assert isinstance(text, str)
            assert not text.startswith("Czy zapis ")


def test_validator_cli_accepts_approved_artifacts() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.provider_independent_spelling_qualification",
            "validate",
            "--evidence",
            str(EVIDENCE_PATH),
            "--manifest",
            str(MANIFEST_PATH),
            "--matrix",
            str(MATRIX_PATH),
        ],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary == {
        "accepted_count": 6,
        "candidate_count": 6,
        "case_count": 144,
        "hard_negative_case_count": 96,
        "positive_expected_finding_count": 54,
    }


def test_validator_cli_rejects_duplicate_evidence_key(tmp_path: Path) -> None:
    evidence_text = EVIDENCE_PATH.read_text(encoding="utf-8")
    approved = '  "license": "CC0-1.0",'
    assert evidence_text.count(approved) == 1
    duplicate_evidence = tmp_path / "duplicate-evidence.json"
    duplicate_evidence.write_text(
        evidence_text.replace(
            approved,
            '  "license": "UNAPPROVED",\n' + approved,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.provider_independent_spelling_qualification",
            "validate",
            "--evidence",
            str(duplicate_evidence),
            "--manifest",
            str(MANIFEST_PATH),
            "--matrix",
            str(MATRIX_PATH),
        ],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "duplicate JSON key" in completed.stdout


def test_validator_cli_rejects_duplicate_approval_key(tmp_path: Path) -> None:
    matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
    approved = (
        '    "note": "Approval binds the exact six-row qualification content after '
        'independent validation; runtime implementation remains forbidden in #402."'
    )
    assert matrix_text.count(approved) == 1
    duplicate_matrix = tmp_path / "duplicate-matrix.json"
    duplicate_matrix.write_text(
        matrix_text.replace(
            approved,
            '    "note": "UNAPPROVED",\n' + approved,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.provider_independent_spelling_qualification",
            "validate",
            "--evidence",
            str(EVIDENCE_PATH),
            "--manifest",
            str(MANIFEST_PATH),
            "--matrix",
            str(duplicate_matrix),
        ],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "duplicate JSON key" in completed.stdout


def test_manifest_hash_drift_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    manifest["evidence_sha256"] = "0" * 64

    with pytest.raises(ContractError, match="evidence SHA-256"):
        validate_documents(evidence, manifest, matrix)


def test_inexact_positive_span_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    first_case = mapping(positives[0], "first positive")
    findings = first_case["expected_findings"]
    assert isinstance(findings, list)
    finding = mapping(findings[0], "first finding")
    end = finding["end"]
    assert isinstance(end, int)
    finding["end"] = end + 1

    with pytest.raises(ContractError, match="exact original span"):
        validate_documents(evidence, manifest, matrix)


def test_inexact_positive_suggestion_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    first_case = mapping(positives[0], "first positive")
    findings = first_case["expected_findings"]
    assert isinstance(findings, list)
    finding = mapping(findings[0], "first finding")
    finding["suggestion"] = "niepoprawna sugestia"
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="casing-aware suggestion"):
        validate_documents(evidence, manifest, matrix)


def test_missing_title_case_evidence_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    title_case = mapping(positives[1], "title-case positive")
    title_case["text"] = "Powiedział: „coniemiara kłopotów nas czeka”."
    findings = title_case["expected_findings"]
    assert isinstance(findings, list)
    finding = mapping(findings[0], "title-case finding")
    finding["original"] = "coniemiara"
    finding["suggestion"] = "co niemiara"
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="casing coverage"):
        validate_documents(evidence, manifest, matrix)


def test_reintroduced_metalinguistic_positive_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    metalinguistic = mapping(positives[7], "metalinguistic positive")
    metalinguistic["text"] = "Czy zapis coniemiara? Tak, to błąd."
    findings = metalinguistic["expected_findings"]
    assert isinstance(findings, list)
    finding = mapping(findings[0], "metalinguistic finding")
    finding["start"] = 10
    finding["end"] = 20
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="metalinguistic"):
        validate_documents(evidence, manifest, matrix)


def test_required_metalinguistic_hard_negative_cannot_be_removed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    negatives = candidate["hard_negative_cases"]
    assert isinstance(negatives, list)
    metalinguistic = mapping(negatives[1], "metalinguistic hard negative")
    metalinguistic["guard"] = "natural-language"
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="hard-negative guard coverage"):
        validate_documents(evidence, manifest, matrix)


def test_accepted_row_cannot_drop_a_hard_negative() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    negatives = candidate["hard_negative_cases"]
    assert isinstance(negatives, list)
    negatives.pop()

    with pytest.raises(ContractError, match="16 hard negatives"):
        validate_documents(evidence, manifest, matrix)


def test_duplicate_public_case_id_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    first = mapping(positives[0], "first positive")
    second = mapping(positives[1], "second positive")
    second["id"] = copy.deepcopy(first["id"])

    with pytest.raises(ContractError, match="duplicate case ID"):
        validate_documents(evidence, manifest, matrix)


def test_missing_required_shape_stratum_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    for raw_case in positives:
        case = mapping(raw_case, "positive")
        strata = case["shape_strata"]
        assert isinstance(strata, list)
        case["shape_strata"] = [
            stratum for stratum in strata if stratum != "repeated-occurrence"
        ]

    with pytest.raises(ContractError, match="repeated-occurrence"):
        validate_documents(evidence, manifest, matrix)


def test_provider_dependent_row_fails_the_provider_independent_contract() -> None:
    evidence, manifest, matrix = _documents()
    row = _first_matrix_row(matrix)
    identity = mapping(row["identity"], "row identity")
    identity["provider_profile"] = "qualified-morphology"
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match="provider-absent"):
        validate_documents(evidence, manifest, matrix)


def test_matrix_controlled_pair_ids_must_match_evidence() -> None:
    evidence, manifest, matrix = _documents()
    row = _first_matrix_row(matrix)
    public_evidence = mapping(row["public_evidence"], "row public evidence")
    public_evidence["controlled_pair_ids"] = [
        "FAKE-PAIR-01",
        "FAKE-PAIR-02",
        "FAKE-PAIR-03",
        "FAKE-PAIR-04",
    ]
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match="controlled pair IDs"):
        validate_documents(evidence, manifest, matrix)


def test_fewer_than_eight_positive_cases_fails_after_full_rebinding() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    positives = candidate["positive_cases"]
    assert isinstance(positives, list)
    removed = mapping(positives.pop(), "removed positive")
    removed_id = removed["id"]
    assert isinstance(removed_id, str)

    for key in ("case_count", "positive_case_count", "positive_expected_finding_count"):
        value = evidence[key]
        assert isinstance(value, int)
        evidence[key] = value - 1

    reviewed_case_ids = manifest["reviewed_case_ids"]
    assert isinstance(reviewed_case_ids, list)
    reviewed_case_ids.remove(removed_id)
    manifest["case_id_sha256"] = hashlib.sha256(
        canonical_bytes(reviewed_case_ids)
    ).hexdigest()
    _write_manifest_digest(evidence, manifest)

    row = _first_matrix_row(matrix)
    public_evidence = mapping(row["public_evidence"], "row public evidence")
    positive_case_ids = public_evidence["positive_case_ids"]
    assert isinstance(positive_case_ids, list)
    positive_case_ids.remove(removed_id)
    finding_count = public_evidence["positive_expected_finding_count"]
    assert isinstance(finding_count, int)
    public_evidence["positive_expected_finding_count"] = finding_count - 1
    shape_strata = mapping(public_evidence["shape_strata"], "shape strata")
    sentence_internal = mapping(
        shape_strata["sentence-internal"], "sentence-internal counts"
    )
    positive_count = sentence_internal["positive_cases"]
    assert isinstance(positive_count, int)
    sentence_internal["positive_cases"] = positive_count - 1
    provider_profiles = mapping(
        public_evidence["provider_profiles"], "provider profiles"
    )
    for profile_name in ("provider-absent", "qualified-morphology"):
        profile = mapping(provider_profiles[profile_name], profile_name)
        profile_positive_count = profile["positive_cases"]
        assert isinstance(profile_positive_count, int)
        profile["positive_cases"] = profile_positive_count - 1
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match="8 positive cases"):
        validate_documents(evidence, manifest, matrix)


def test_controlled_pair_semantics_fail_after_full_rebinding() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    negatives = candidate["hard_negative_cases"]
    assert isinstance(negatives, list)
    already_correct = mapping(negatives[0], "already-correct pair")
    metalinguistic = mapping(negatives[1], "metalinguistic pair")
    already_correct["pair_id"], metalinguistic["pair_id"] = (
        metalinguistic["pair_id"],
        already_correct["pair_id"],
    )
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="controlled pair semantics"):
        validate_documents(evidence, manifest, matrix)


def test_normative_authority_url_drift_fails_after_full_rebinding() -> None:
    evidence, manifest, matrix = _documents()
    authorities = mapping(evidence["authorities"], "authorities")
    authorities["nck_co_niemiara"] = "https://example.com/not-normative"
    row = _first_matrix_row(matrix)
    normative_basis = mapping(row["normative_basis"], "normative basis")
    normative_basis["authority_url"] = "https://example.com/not-normative"
    _write_manifest_digest(evidence, manifest)
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match="authority URL"):
        validate_documents(evidence, manifest, matrix)


def test_candidate_authority_swap_fails_after_full_rebinding() -> None:
    evidence, manifest, matrix = _documents()
    candidates = evidence["candidates"]
    rows = matrix["rows"]
    assert isinstance(candidates, list)
    assert isinstance(rows, list)
    first_candidate = mapping(candidates[0], "first candidate")
    second_candidate = mapping(candidates[1], "second candidate")
    (
        first_candidate["normative_authority_id"],
        second_candidate["normative_authority_id"],
    ) = (
        second_candidate["normative_authority_id"],
        first_candidate["normative_authority_id"],
    )
    first_basis = mapping(
        mapping(rows[0], "first row")["normative_basis"], "first normative basis"
    )
    second_basis = mapping(
        mapping(rows[1], "second row")["normative_basis"],
        "second normative basis",
    )
    first_basis["authority_id"], second_basis["authority_id"] = (
        second_basis["authority_id"],
        first_basis["authority_id"],
    )
    first_basis["authority_url"], second_basis["authority_url"] = (
        second_basis["authority_url"],
        first_basis["authority_url"],
    )
    _write_manifest_digest(evidence, manifest)
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match="normative_authority_id"):
        validate_documents(evidence, manifest, matrix)


@pytest.mark.parametrize("negative_index", range(16))
def test_guard_label_cannot_replace_hard_negative_semantics(
    negative_index: int,
) -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    negatives = candidate["hard_negative_cases"]
    assert isinstance(negatives, list)
    hard_negative = mapping(negatives[negative_index], "hard negative")
    incorrect_surface = candidate["incorrect_surface"]
    assert isinstance(incorrect_surface, str)
    hard_negative["text"] = incorrect_surface
    hard_negative["probes"] = [
        {
            "start": 0,
            "end": len(incorrect_surface),
            "original": incorrect_surface,
        }
    ]
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="approved evidence digest"):
        validate_documents(evidence, manifest, matrix)


def test_controlled_pair_content_cannot_be_rebound_under_stable_labels() -> None:
    evidence, manifest, matrix = _documents()
    candidate = _first_candidate(evidence)
    negatives = candidate["hard_negative_cases"]
    assert isinstance(negatives, list)
    already_correct = mapping(negatives[0], "already-correct hard negative")
    metalinguistic = mapping(negatives[1], "metalinguistic hard negative")
    metalinguistic["text"] = copy.deepcopy(already_correct["text"])
    metalinguistic["probes"] = copy.deepcopy(already_correct["probes"])
    _write_manifest_digest(evidence, manifest)

    with pytest.raises(ContractError, match="approved evidence digest"):
        validate_documents(evidence, manifest, matrix)


@pytest.mark.parametrize(
    ("section", "replacement", "message"),
    [
        ("normative_basis", {}, "normative basis fields"),
        (
            "deterministic_boundary",
            [],
            "matrix row contract deterministic boundary",
        ),
        ("expected_value", False, "matrix row contract expected value"),
        ("risk_and_cost", 7, "matrix row contract risk and cost"),
    ],
)
def test_malformed_required_matrix_section_fails_closed(
    section: str, replacement: JsonValue, message: str
) -> None:
    evidence, manifest, matrix = _documents()
    rows = matrix["rows"]
    assert isinstance(rows, list)
    row = mapping(rows[0], "first matrix row")
    row[section] = copy.deepcopy(replacement)
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match=message):
        validate_documents(evidence, manifest, matrix)


def test_extra_nested_matrix_field_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    row = _first_matrix_row(matrix)
    normative_basis = mapping(row["normative_basis"], "normative basis")
    normative_basis["unexpected"] = "must fail closed"
    _write_matrix_digest(matrix)

    with pytest.raises(ContractError, match="normative basis fields"):
        validate_documents(evidence, manifest, matrix)


def test_manifest_review_date_drift_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    manifest["reviewed_at"] = "not-a-date"

    with pytest.raises(ContractError, match="manifest review metadata"):
        validate_documents(evidence, manifest, matrix)


def test_matrix_approval_note_drift_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    approval = mapping(matrix["approval"], "matrix approval")
    approval["note"] = "UNKNOWN DRIFT"

    with pytest.raises(ContractError, match="matrix approval metadata"):
        validate_documents(evidence, manifest, matrix)


def test_matrix_approval_date_drift_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    approval = mapping(matrix["approval"], "matrix approval")
    approval["approved_at"] = "not-a-date"

    with pytest.raises(ContractError, match="matrix approval metadata"):
        validate_documents(evidence, manifest, matrix)


def test_row_approval_date_drift_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    row = _first_matrix_row(matrix)
    decision = mapping(row["decision"], "row decision")
    approval = mapping(decision["maintainer_approval"], "row approval")
    approval["approved_at"] = "not-a-date"

    with pytest.raises(ContractError, match="row approval metadata"):
        validate_documents(evidence, manifest, matrix)


def test_approval_digest_drift_fails_closed() -> None:
    evidence, manifest, matrix = _documents()
    approval = mapping(matrix["approval"], "matrix approval")
    approval["bound_matrix_sha256"] = "0" * 64

    with pytest.raises(ContractError, match="approval digest"):
        validate_documents(evidence, manifest, matrix)
