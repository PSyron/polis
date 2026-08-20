from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.rjp_2026_audit_contract import (
    CHANGE_NUMBERS,
    RjpAuditError,
    validate_rjp_2026_audit,
)

from polis.evaluation._quality_types import JsonValue

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/project/rule-coverage-rjp-2026.json"


def _data() -> dict[str, JsonValue]:
    value: JsonValue = json.loads(AUDIT.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("audit fixture must be an object")
    return value


def _write(tmp_path: Path, data: dict[str, JsonValue]) -> Path:
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_rjp_audit_has_full_snapshot_and_change_matrix() -> None:
    audit = validate_rjp_2026_audit()
    assert audit["schema_id"] == "polis.rule-coverage-rjp-2026-audit"
    snapshot = audit["source_snapshot"]
    assert isinstance(snapshot, dict)
    assert snapshot["count"] == 60
    rows = audit["source_rows"]
    changes = audit["change_rows"]
    assert isinstance(rows, list)
    assert isinstance(changes, list)
    assert len(rows) == 60
    assert len(changes) == len(CHANGE_NUMBERS)


def test_evaluation_artifacts_do_not_invalidate_rjp_source_audit() -> None:
    validate_rjp_2026_audit()


def test_source_rows_keep_live_order_and_category_counts() -> None:
    audit = validate_rjp_2026_audit()
    rows = audit["source_rows"]
    summary = audit["category_summary"]
    assert isinstance(rows, list)
    assert isinstance(summary, dict)
    categories = [row["category"] for row in rows if isinstance(row, dict)]
    assert {category: categories.count(category) for category in set(categories)} == {
        "agreement": 9,
        "inflection": 14,
        "punctuation": 5,
        "spelling": 23,
        "syntax": 9,
    }
    assert all(
        isinstance(item, dict) and item["source"].startswith("rule:") for item in rows
    )


def test_rjp_comma_sources_and_withdrawal_title_use_exact_authority() -> None:
    audit = validate_rjp_2026_audit()
    rows = audit["source_rows"]
    assert isinstance(rows, list)
    row_by_source = {row["source"]: row for row in rows if isinstance(row, dict)}
    for source in (
        "rule:syntax.initial_conditional_comma",
        "rule:syntax.initial_temporal_comma",
        "rule:syntax.comma_before_ze_reporting",
        "rule:syntax.comma_before_zeby_purpose",
        "rule:syntax.comma_before_bo",
    ):
        row = row_by_source[source]
        assert row["normative_scope"] == "governed-by-rjp"
        references = row["normative_references"]
        assert isinstance(references, list)
        assert references[0]["locator"] == "Część II, pkt 12.1.1, PDF s. 62-63"
        assert references[0]["title"] == "Zasady pisowni i interpunkcji polskiej"
    for source in ("rule:syntax.comma_space", "rule:syntax.duplicate_comma"):
        row = row_by_source[source]
        assert row["normative_scope"] == "not-governed-by-audited-rjp-material"
        assert row["normative_references"] == []
        assert row["conformance_disposition"] == "not-governed-by-audited-rjp-material"
    sources = audit["exact_rjp_sources"]
    assert isinstance(sources, list)
    assert sources[1]["title"] == (
        "Komunikat Rady Języka Polskiego przy Prezydium PAN z dnia 7 listopada 2025 r."
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "source row count"),
        ("extra", "source row count"),
        ("duplicate", "source row parity"),
        ("operation", "source operation/version"),
        ("category", "unsupported source category"),
        ("provider", "qualified provider identity"),
    ],
)
def test_source_matrix_mutations_fail_closed(
    tmp_path: Path, mutation: str, message: str
) -> None:
    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append(copy.deepcopy(rows[-1]))
    elif mutation == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif mutation == "operation":
        assert isinstance(rows[0], dict)
        rows[0]["operation"] = "replace.synthetic"
    elif mutation == "category":
        assert isinstance(rows[0], dict)
        rows[0]["category"] = "unknown"
    else:
        assert isinstance(rows[4], dict)
        rows[4]["provider_requirement"] = "provider-independent"
    with pytest.raises(RjpAuditError, match=message):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_rjp_source_reference_and_non_rjp_boundary_are_executable(
    tmp_path: Path,
) -> None:
    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0]["normative_references"] = [{"url": "unexpected"}]
    with pytest.raises(RjpAuditError, match="non-RJP source"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[23], dict)
    rows[23]["normative_references"] = []
    with pytest.raises(RjpAuditError, match="RJP reference missing"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[23], dict)
    rows[23]["normative_references"] = [{"fabricated": "accepted"}]
    with pytest.raises(RjpAuditError, match="fields drifted"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[23], dict)
    references = rows[23]["normative_references"]
    assert isinstance(references, list)
    assert isinstance(references[0], dict)
    references[0]["locator"] = "dokument jednolity; fabricated locator"
    with pytest.raises(RjpAuditError, match="RJP reference locator"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    positives = rows[0]["supporting_public_positives"]
    assert isinstance(positives, list)
    assert isinstance(positives[0], dict)
    positives[0]["path"] = "https://example.invalid/evidence"
    with pytest.raises(RjpAuditError, match="unsupported public evidence path"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_change_matrix_rejects_missing_or_unknown_official_change(
    tmp_path: Path,
) -> None:
    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    changes.pop()
    with pytest.raises(RjpAuditError, match="official change row count"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[0], dict)
    changes[0]["implementation_disposition"] = "unknown"
    with pytest.raises(RjpAuditError, match="unsupported implementation"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_metadata_and_candidate_schema_fail_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(_data())
    sources = data["exact_rjp_sources"]
    assert isinstance(sources, list)
    assert isinstance(sources[0], dict)
    sources[0].pop("document_url")
    with pytest.raises(RjpAuditError, match="fields drifted"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    sources = data["exact_rjp_sources"]
    assert isinstance(sources, list)
    assert isinstance(sources[0], dict)
    sources[0]["publisher"] = "fabricated publisher"
    with pytest.raises(RjpAuditError, match="source identity drifted"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[2], dict)
    candidates = changes[2]["positive_example_candidates"]
    assert isinstance(candidates, list)
    assert isinstance(candidates[0], dict)
    candidates[0].pop("expected_span_behavior")
    with pytest.raises(RjpAuditError, match="fields drifted"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_every_positive_candidate_is_validated(tmp_path: Path) -> None:
    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[12], dict)
    candidates = changes[12]["positive_example_candidates"]
    assert isinstance(candidates, list)
    assert isinstance(candidates[0], dict)
    extra = copy.deepcopy(candidates[0])
    extra["category"] = "unknown"
    candidates.append(extra)
    with pytest.raises(RjpAuditError, match="invalid candidate shape"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_source_sha_and_public_v3_baseline_are_bound(tmp_path: Path) -> None:
    data = copy.deepcopy(_data())
    data["audited_full_sha"] = "0" * 40
    with pytest.raises(RjpAuditError, match="resolvable commit"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    baseline = data["public_v3_baseline"]
    assert isinstance(baseline, dict)
    profiles = baseline["profiles"]
    assert isinstance(profiles, dict)
    default = profiles["default"]
    assert isinstance(default, dict)
    default["true_positives"] = 110
    with pytest.raises(RjpAuditError, match="public v3 counts"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_audited_sha_is_resolvable_from_the_current_audit_checkout() -> None:
    data = _data()
    audited_sha = data["audited_full_sha"]
    assert isinstance(audited_sha, str)
    resolved = subprocess.run(
        ["git", "rev-list", "--all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resolved.returncode == 0
    assert audited_sha in resolved.stdout.splitlines()
    validate_rjp_2026_audit()


def test_source_policy_and_normative_scope_parity_fail_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0]["correction_policy_status"] = "review-only"
    with pytest.raises(RjpAuditError, match="correction policy parity"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    rows = data["source_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0]["conformance_disposition"] = "conforming"
    with pytest.raises(RjpAuditError, match="conformance contradicts scope"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_duplicate_json_keys_and_weak_candidate_provenance_fail_closed(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    raw = AUDIT.read_text(encoding="utf-8").replace(
        '"schema_id":"polis.rule-coverage-rjp-2026-audit","schema_version"',
        '"schema_id":"polis.rule-coverage-rjp-2026-audit","schema_id":"duplicate","schema_version"',
        1,
    )
    duplicate.write_text(raw, encoding="utf-8")
    with pytest.raises(RjpAuditError, match="duplicate JSON key"):
        validate_rjp_2026_audit(duplicate)

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[3], dict)
    changes[3]["provider_requirement"] = "x"
    changes[3]["deterministic_boundary_analysis"] = "x"
    changes[3]["rationale"] = "x"
    negatives = changes[3]["hard_negative_or_ambiguity_candidates"]
    assert isinstance(negatives, list)
    assert isinstance(negatives[0], dict)
    negatives[0]["reason"] = "x"
    with pytest.raises(RjpAuditError, match="not substantive"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_rjp_11_does_not_promote_comparative_to_superlative() -> None:
    audit = validate_rjp_2026_audit()
    changes = audit["change_rows"]
    assert isinstance(changes, list)
    row = changes[-1]
    assert isinstance(row, dict)
    assert row["implementation_disposition"] == "ambiguous_or_non_deterministic"
    candidate = row["positive_example_candidates"]
    assert isinstance(candidate, list)
    assert isinstance(candidate[0], dict)
    assert candidate[0]["status"] == "not-admitted"


def test_rjp_03_candidate_excludes_lexical_by_forms() -> None:
    audit = validate_rjp_2026_audit()
    changes = audit["change_rows"]
    assert isinstance(changes, list)
    row = changes[2]
    assert isinstance(row, dict)
    assert row["implementation_disposition"] == "deterministic_v1_candidate"
    candidate = row["positive_example_candidates"]
    assert isinstance(candidate, list)
    assert isinstance(candidate[0], dict)
    assert candidate[0]["wrong_form"] == "czyby"
    assert candidate[0]["expected_form"] == "czy by"
    assert candidate[0]["status"] == "admitted"
    assert candidate[0]["expected_span_behavior"] == "[start,end) original-text span"
    negatives = row["hard_negative_or_ambiguity_candidates"]
    assert isinstance(negatives, list)
    assert len(negatives) >= 2
    reasons = " ".join(str(item["reason"]) for item in negatives)
    assert "czy by" in reasons


def test_candidate_and_withdrawal_guards_fail_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[8], dict)
    changes[8]["implementation_disposition"] = "deterministic_v1_candidate"
    candidate = changes[8]["positive_example_candidates"]
    assert isinstance(candidate, list)
    assert isinstance(candidate[0], dict)
    candidate[0]["status"] = "admitted"
    with pytest.raises(RjpAuditError, match="withdrawn RJP-08b"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[2], dict)
    candidate = changes[2]["positive_example_candidates"]
    assert isinstance(candidate, list)
    assert isinstance(candidate[0], dict)
    candidate[0]["wrong_form"] = None
    with pytest.raises(RjpAuditError, match="candidate admission fields"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[12], dict)
    changes[12]["provider_requirement"] = "unrelated substantive provider boundary"
    with pytest.raises(RjpAuditError, match="provider boundary"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[0], dict)
    changes[0]["effective_date"] = "1999-01-01"
    with pytest.raises(RjpAuditError, match="effective date drifted"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[0], dict)
    reference = changes[0]["exact_rjp_reference"]
    assert isinstance(reference, list)
    assert isinstance(reference[0], dict)
    reference[0]["title"] = "fabricated substantive official title"
    with pytest.raises(RjpAuditError, match="official reference locator"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[3], dict)
    changes[3]["provider_requirement"] = (
        "qualified:morfeusz2/1.99.15/pl.sgjp.sgjp-2026.06.01/notice-fabricated; "
        "provider absence or drift abstains"
    )
    with pytest.raises(RjpAuditError, match="authorized provider identity"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[0], dict)
    links = changes[0]["evidence_links"]
    assert isinstance(links, list)
    links[0] = "https://example.invalid/evidence"
    with pytest.raises(RjpAuditError, match="unsupported evidence link"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[12], dict)
    candidate = changes[12]["positive_example_candidates"]
    assert isinstance(candidate, list)
    assert isinstance(candidate[0], dict)
    candidate[0]["expected_span_behavior"] = "not a half-open span"
    with pytest.raises(RjpAuditError, match="span semantics"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[12], dict)
    negatives = changes[12]["hard_negative_or_ambiguity_candidates"]
    assert isinstance(negatives, list)
    assert isinstance(negatives[0], dict)
    negatives[0]["reason"] = "valid enough text"
    with pytest.raises(RjpAuditError, match="hard-negative boundary"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[12], dict)
    changes[12]["deterministic_boundary_analysis"] = "proper-name guards"
    with pytest.raises(RjpAuditError, match="candidate boundary"):
        validate_rjp_2026_audit(_write(tmp_path, data))

    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[2], dict)
    changes[2]["deterministic_boundary_analysis"] = "fused token boundary"
    with pytest.raises(RjpAuditError, match="candidate boundary"):
        validate_rjp_2026_audit(_write(tmp_path, data))


@pytest.mark.parametrize(
    ("mutation", "value", "message"),
    [
        ("audit_date", "2026-08-18", "audit date"),
        ("category_summary", "fabricated boundary", "category summary"),
        ("maintainer_review_status", "approved", "maintainer review"),
        ("official_change_name", "RJP-01: fabricated", "official change name"),
        (
            "official_change_paraphrase",
            "fabricated paraphrase",
            "official change paraphrase",
        ),
    ],
)
def test_required_audit_metadata_mutations_fail_closed(
    tmp_path: Path, mutation: str, value: JsonValue, message: str
) -> None:
    data = copy.deepcopy(_data())
    if mutation == "audit_date":
        data["audit_date"] = value
    elif mutation == "category_summary":
        summary = data["category_summary"]
        assert isinstance(summary, dict)
        spelling = summary["spelling"]
        assert isinstance(spelling, dict)
        spelling["claim_boundary"] = value
    elif mutation == "maintainer_review_status":
        review = data["maintainer_review_status"]
        assert isinstance(review, dict)
        review["status"] = value
    else:
        changes = data["change_rows"]
        assert isinstance(changes, list)
        first_change = changes[0]
        assert isinstance(first_change, dict)
        first_change[
            "official_number_or_name"
            if mutation == "official_change_name"
            else "concise_paraphrase"
        ] = value
    with pytest.raises(RjpAuditError, match=message):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_maintainer_review_count_reconciles_unresolved_rows(tmp_path: Path) -> None:
    data = copy.deepcopy(_data())
    changes = data["change_rows"]
    assert isinstance(changes, list)
    assert isinstance(changes[0], dict)
    changes[0]["implementation_disposition"] = "unresolved_pending_clarification"
    with pytest.raises(RjpAuditError, match="row count is not reconciled"):
        validate_rjp_2026_audit(_write(tmp_path, data))


def test_cli_reports_validity_and_rejects_malformed_fixture(tmp_path: Path) -> None:
    valid = subprocess.run(
        [sys.executable, "-m", "scripts.rule_coverage_rjp_2026"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert valid.returncode == 0
    assert "RJP 2026 audit is valid" in valid.stdout

    malformed = _data()
    malformed.pop("change_rows")
    path = _write(tmp_path, malformed)
    invalid = subprocess.run(
        [sys.executable, "-m", "scripts.rule_coverage_rjp_2026", "--path", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode == 1
    assert "audit fields drifted" in invalid.stdout
