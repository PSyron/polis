"""Validate the maintained RJP 2026 source and change audit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Final

from polis import Analyzer, AnalyzerConfig
from polis.correction.policy import _ACTIVE_POLICY_ENTRIES, SOURCE_POLICY_VERSION
from polis.evaluation._quality_types import JsonValue

AUDIT_PATH: Final = (
    Path(__file__).resolve().parents[1] / "docs/project/rule-coverage-rjp-2026.json"
)
SCHEMA_ID: Final = "polis.rule-coverage-rjp-2026-audit"
CATEGORIES: Final = ("agreement", "inflection", "punctuation", "spelling", "syntax")
CONFORMANCE: Final = (
    "conforming",
    "change_required",
    "unclear_fail_closed",
    "not-governed-by-audited-rjp-material",
)
IMPLEMENTATION: Final = (
    "already_covered_and_conforming",
    "deterministic_v1_candidate",
    "provider_dependent_candidate",
    "ambiguous_or_non_deterministic",
    "outside_supported_categories",
    "not_applicable_to_analyzed_prose",
    "unresolved_pending_clarification",
)
CHANGE_NUMBERS: Final = (
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08a",
    "08b",
    "08c",
    "08d",
    "08e",
    "09a",
    "09b",
    "10",
    "11",
)
AUDIT_DATE: Final = "2026-08-18"
RJP_DOC_URL: Final = "https://rjp.pan.pl/app/uploads/2026/03/Zalacznik-do-komunikatu-11-25-wersja-ostateczna-jednolita.pdf"
RJP_LANDING_URL: Final = "https://rjp.pan.pl/zasady-pisowni-i-interpunkcji-polskiej-2/"
WITHDRAWAL_URL: Final = "https://rjp.pan.pl/komunikat-rady-jezyka-polskiego-przy-prezydium-pan-z-dnia-7-listopada-2025-r/"
RJP_PUBLISHER: Final = "Rada Języka Polskiego przy Prezydium PAN"
RJP_CONSOLIDATED_TITLE: Final = "Zasady pisowni i interpunkcji polskiej"
RJP_WITHDRAWAL_TITLE: Final = (
    "Komunikat Rady Języka Polskiego przy Prezydium PAN z dnia 7 listopada 2025 r."
)
EXPECTED_CATEGORY_SUMMARY: Final[dict[str, dict[str, JsonValue]]] = {
    "agreement": {
        "source_count": 8,
        "rjp_normative_scope": "not claimed",
        "claim_boundary": "Source audit, not completeness.",
    },
    "inflection": {
        "source_count": 14,
        "rjp_normative_scope": "not claimed",
        "claim_boundary": "Source audit, not completeness.",
    },
    "punctuation": {
        "source_count": 5,
        "rjp_normative_scope": "bounded only",
        "claim_boundary": "Source audit, not completeness.",
    },
    "spelling": {
        "source_count": 23,
        "rjp_normative_scope": "bounded only",
        "claim_boundary": "Source audit, not completeness.",
    },
    "syntax": {
        "source_count": 9,
        "rjp_normative_scope": "not claimed",
        "claim_boundary": "Source audit, not completeness.",
    },
}
EXPECTED_MAINTAINER_REVIEW_STATUS: Final[dict[str, JsonValue]] = {
    "status": "not-required-for-closed-dispositions",
    "unresolved_or_unclear_row_count": 0,
    "reason": (
        "All rows use allowed dispositions; ambiguous/provider-dependent rows are "
        "explicit fail-closed non-approvals."
    ),
}
EXPECTED_CHANGE_DETAILS: Final[dict[str, tuple[str, str]]] = {
    "RJP-01:": (
        "RJP-01: Nazwy mieszkańców miast, dzielnic, osiedli i wsi oraz "
        "warianty nazw etnicznych.",
        "Nazwy mieszkańców miast, dzielnic, osiedli i wsi oraz warianty "
        "nazw etnicznych.",
    ),
    "RJP-02:": (
        "RJP-02: Pojedyncze egzemplarze firm, marek i modeli wielką literą.",
        "Pojedyncze egzemplarze firm, marek i modeli wielką literą.",
    ),
    "RJP-03:": (
        "RJP-03: Rozdzielna pisownia cząstek -by ze spójnikami.",
        "Rozdzielna pisownia cząstek -by ze spójnikami.",
    ),
    "RJP-04:": (
        "RJP-04: Łączna pisownia nie- z imiesłowami odmiennymi.",
        "Łączna pisownia nie- z imiesłowami odmiennymi.",
    ),
    "RJP-05:": (
        "RJP-05: Małą literą przymiotniki od nazw osobowych; limited variants.",
        "Małą literą przymiotniki od nazw osobowych; limited variants.",
    ),
    "RJP-06:": (
        "RJP-06: Łączna pisownia pół- and hyphen in pół-Polka.",
        "Łączna pisownia pół- and hyphen in pół-Polka.",
    ),
    "RJP-07:": (
        "RJP-07: Three valid variants for paired words.",
        "Three valid variants for paired words.",
    ),
    "RJP-08a:": (
        "RJP-08a: All comet-name members capitalized.",
        "All comet-name members capitalized.",
    ),
    "RJP-08b:": (
        "RJP-08b: Withdrawn geographic-name capitalization change.",
        "Withdrawn geographic-name capitalization change.",
    ),
    "RJP-08c:": (
        "RJP-08c: Public-space object name initial member capitalized except ulica.",
        "Public-space object name initial member capitalized except ulica.",
    ),
    "RJP-08d:": (
        "RJP-08d: Business and food-service name members capitalized with exceptions.",
        "Business and food-service name members capitalized with exceptions.",
    ),
    "RJP-08e:": (
        "RJP-08e: Awards, orders, medals, titles capitalized with exceptions.",
        "Awards, orders, medals, titles capitalized with exceptions.",
    ),
    "RJP-09a:": (
        "RJP-09a: Prefixes joined to lowercase and hyphenated before uppercase.",
        "Prefixes joined to lowercase and hyphenated before uppercase.",
    ),
    "RJP-09b:": (
        "RJP-09b: Optional separation for prefixes usable as independent words.",
        "Optional separation for prefixes usable as independent words.",
    ),
    "RJP-10:": (
        "RJP-10: niby-/quasi- joined lowercase and hyphenated uppercase.",
        "niby-/quasi- joined lowercase and hyphenated uppercase.",
    ),
    "RJP-11:": (
        "RJP-11: nie- joined to adjectives and adjective-derived adverbs at "
        "all degrees.",
        "nie- joined to adjectives and adjective-derived adverbs at all degrees.",
    ),
}
MORPHOLOGY_FRAGMENT: Final = "morfeusz2/1.99.15/pl.sgjp.sgjp-2026.06.01"
AUTHORIZED_PROVIDER_REQUIREMENT: Final = (
    "qualified:morfeusz2/1.99.15/"
    "pl.sgjp.sgjp-2026.06.01/"
    "notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393; "
    "provider absence or drift abstains"
)
SOURCE_RJP_LOCATORS: Final[dict[str, str]] = {
    "rule:spelling.jestes": "Część I, pkt 3.2(a), PDF s. 14",
    "rule:spelling.napewno": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.wlasnie": "Część I, pkt 3.2(a), PDF s. 14",
    "rule:spelling.zeby": "Część I, pkt 3.5.2, PDF s. 17-18",
    "rule:spelling.wogole": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.wogole_diacritic": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.narazie": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.wziasc": "Część I, pkt 2.3.1(1c), PDF s. 11",
    "rule:spelling.wziasc_diacritic": "Część I, pkt 2.3.1(1c), PDF s. 11",
    "rule:spelling.conajmniej": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.poprostu": "Część I, pkt 2.2.2(b), PDF s. 11",
    "rule:spelling.pozatym": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.przedewszystkim": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.wkoncu": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.spowrotem": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.tymbardziej": "Część I, pkt 4.4.1, PDF s. 24",
    "rule:spelling.naprawde": "Część I, pkt 4.4.2, PDF s. 24",
    "rule:spelling.nie_byc_joint": "Część I, pkt 4.9.2(1a), PDF s. 31",
    "rule:spelling.poszlem": "Część I, pkt 3.3(c), PDF s. 14",
    "rule:spelling.wlanczac": "Część I, pkt 3.7.2, PDF s. 19",
    "rule:spelling.month_weekday_lowercase": "Część I, pkt 8.2(1), PDF s. 51",
    "rule:spelling.proper_adjective_lowercase": "Część I, pkt 8.2(4), PDF s. 51",
    "rule:spelling.sentence_initial_capital": "Część I, pkt 8.1.1, PDF s. 42",
    "rule:syntax.initial_conditional_comma": "Część II, pkt 12.1.1, PDF s. 62-63",
    "rule:syntax.initial_temporal_comma": "Część II, pkt 12.1.1, PDF s. 62-63",
    "rule:syntax.comma_before_ze_reporting": "Część II, pkt 12.1.1, PDF s. 62-63",
    "rule:syntax.comma_before_zeby_purpose": "Część II, pkt 12.1.1, PDF s. 62-63",
    "rule:syntax.comma_before_bo": "Część II, pkt 12.1.1, PDF s. 62-63",
    "rule:syntax.quote_space": "Część II, pkt 20, PDF s. 80",
    "rule:syntax.sentence_space": "Część I, pkt 8.1.1, PDF s. 42",
    "rule:punctuation.abbreviation_dot": "Część I, pkt 6.2(c2), PDF s. 38",
}
PUBLIC_EVIDENCE_PATHS: Final[frozenset[str]] = frozenset(
    {
        "docs/rules.md",
        "docs/quality-comparison-v3.json",
        "tests/test_rule_source_contract.py",
    }
)
AUTOMATIC_POLICY_KEYS: Final[frozenset[tuple[str, str, str, str, str]]] = frozenset(
    (
        f"rule:{entry.key.source.name}",
        entry.key.category.value,
        entry.key.operation,
        entry.key.behavior_version,
        entry.key.source_policy_version,
    )
    for entry in _ACTIVE_POLICY_ENTRIES
)
ADMITTED_SPAN_BEHAVIOR: Final[str] = "[start,end) original-text span"
ADMITTED_BOUNDARIES: Final[dict[str, str]] = {
    "RJP-03:": (
        "Admit only the exact fused token `czyby`; the replacement span covers "
        "the fused token. Lexical forms listed by RJP §4.5.1(c)-(d), including "
        "`aby`, `ażeby`, `byleby`, `chociażby`, `choćby`, `czyżby`, `gdyby`, "
        "`gdzieżby`, `iżby`, `jakby`, `jakoby`, `jakżeby`, `niby`, `niżby`, "
        "`oby`, and `żeby`, remain outside the candidate boundary."
    ),
    "RJP-09a:": (
        "Admit only the exact token pair `arcy` + space + a non-sentence-initial "
        "uppercase target; no entity or NER inference is used and the replacement "
        "span covers both tokens plus the separator."
    ),
}
ADMITTED_NEGATIVE_MARKERS: Final[dict[str, tuple[str, ...]]] = {
    "RJP-03:": (
        "aby",
        "ażeby",
        "byleby",
        "chociażby",
        "choćby",
        "czyżby",
        "gdyby",
        "gdzieżby",
        "iżby",
        "jakby",
        "jakoby",
        "jakżeby",
        "niby",
        "niżby",
        "oby",
        "żeby",
        "czy by",
    ),
    "RJP-09a:": ("super pomysł", "sentence-initial"),
}
V3_COMPARISON_SHA256: Final = (
    "b16ce0a44d46d06ed0b61a49a7153797338c93a616fff5c634c7c676ebe87c16"
)
V3_DATASET_SHA256: Final = (
    "8f6dec8379af6330f2fb8330421f6a6581f6c9e39ad98fe304322b4a9abb6276"
)


class RjpAuditError(ValueError):
    """Raised when the maintained RJP audit is incomplete or unsafe."""


def _object(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise RjpAuditError(f"{label} must be an object")
    return value


def _list(value: JsonValue, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise RjpAuditError(f"{label} must be a list")
    return value


def _string(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RjpAuditError(f"{label} must be a non-empty string")
    return value


def _substantive(value: JsonValue, label: str) -> str:
    result = _string(value, label)
    if len(result.strip()) < 12:
        raise RjpAuditError(f"{label} is not substantive")
    return result


def _integer(value: JsonValue, label: str) -> int:
    if type(value) is not int:
        raise RjpAuditError(f"{label} must be an integer")
    return value


def _boolean(value: JsonValue, label: str) -> bool:
    if type(value) is not bool:
        raise RjpAuditError(f"{label} must be a boolean")
    return value


def _fields(value: dict[str, JsonValue], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise RjpAuditError(
            f"{label} fields drifted: expected {sorted(expected)}, got {sorted(actual)}"
        )


def _load(path: Path) -> dict[str, JsonValue]:
    def reject_duplicate_keys(
        pairs: list[tuple[str, JsonValue]],
    ) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, item in pairs:
            if key in result:
                raise RjpAuditError(f"duplicate JSON key: {key}")
            result[key] = item
        return result

    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as error:
        raise RjpAuditError(f"cannot load {path}") from error
    return _object(raw, str(path))


def _canonical_snapshot() -> tuple[list[dict[str, str]], str]:
    snapshot = Analyzer(AnalyzerConfig()).source_identity_snapshot
    identities = [
        {
            "source": item.source,
            "operation": item.operation,
            "behavior_version": item.behavior_version,
        }
        for item in snapshot
    ]
    encoded = json.dumps(
        identities, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return identities, hashlib.sha256(encoded).hexdigest()


def _validate_audited_source_sha(audited_sha: str) -> None:
    commit = subprocess.run(
        ["git", "cat-file", "-e", f"{audited_sha}^{{commit}}"],
        cwd=AUDIT_PATH.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        raise RjpAuditError("audited_full_sha is not a resolvable commit")
    for diff_args in (
        ["git", "diff", "--quiet", audited_sha, "--", "src"],
        ["git", "diff", "--cached", "--quiet", audited_sha, "--", "src"],
    ):
        diff = subprocess.run(
            diff_args,
            cwd=AUDIT_PATH.parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        if diff.returncode != 0:
            raise RjpAuditError("runtime source differs from the audited source SHA")


def _validate_v3_baseline(audit: dict[str, JsonValue]) -> None:
    baseline = _object(audit["public_v3_baseline"], "public_v3_baseline")
    _fields(
        baseline,
        {
            "comparison_path",
            "comparison_sha256",
            "source_git_sha",
            "dataset_sha256",
            "profiles",
        },
        "public_v3_baseline",
    )
    if baseline["comparison_path"] != "docs/quality-comparison-v3.json":
        raise RjpAuditError("public v3 comparison path drifted")
    if baseline["comparison_sha256"] != V3_COMPARISON_SHA256:
        raise RjpAuditError("public v3 comparison digest drifted")
    if baseline["dataset_sha256"] != V3_DATASET_SHA256:
        raise RjpAuditError("public v3 dataset identity drifted")
    comparison_path = AUDIT_PATH.parents[2] / str(baseline["comparison_path"])
    try:
        comparison_sha = hashlib.sha256(comparison_path.read_bytes()).hexdigest()
    except OSError as error:
        raise RjpAuditError("public v3 comparison artifact is unavailable") from error
    if comparison_sha != V3_COMPARISON_SHA256:
        raise RjpAuditError("public v3 comparison artifact digest drifted")
    comparison = _load(comparison_path)
    if (
        comparison["schema_id"] != "polis.quality-comparison"
        or comparison["dataset_sha256"] != V3_DATASET_SHA256
        or comparison["source_git_sha"] != baseline["source_git_sha"]
    ):
        raise RjpAuditError("public v3 comparison provenance drifted")
    _substantive(baseline["source_git_sha"], "public_v3_baseline.source_git_sha")
    profiles = _object(baseline["profiles"], "public_v3_baseline.profiles")
    if set(profiles) != {"default", "morphology"}:
        raise RjpAuditError("public v3 baseline profiles are incomplete")
    expected = {
        "default": (111, 59, 0, 0),
        "morphology": (151, 19, 0, 0),
    }
    for profile, counts in expected.items():
        values = _object(profiles[profile], f"public_v3_baseline.{profile}")
        _fields(
            values,
            {
                "true_positives",
                "false_negatives",
                "false_positives",
                "correct_sentence_false_alarms",
            },
            f"public_v3_baseline.{profile}",
        )
        actual = tuple(
            _integer(values[field], f"public_v3_baseline.{profile}.{field}")
            for field in (
                "true_positives",
                "false_negatives",
                "false_positives",
                "correct_sentence_false_alarms",
            )
        )
        if actual != counts:
            raise RjpAuditError(f"public v3 counts drifted: {profile}")
        comparison_profile = _object(
            _object(comparison["profiles"], "public_v3_comparison.profiles")[profile],
            f"public_v3_comparison.{profile}",
        )
        for field, expected_value in zip(
            ("true_positives", "false_negatives", "false_positives"),
            counts[:3],
            strict=True,
        ):
            result_counts = _object(
                comparison_profile["quality_counts_result"],
                f"public_v3_comparison.{profile}.quality_counts_result",
            )
            if (
                _integer(
                    result_counts[field], f"public_v3_comparison.{profile}.{field}"
                )
                != expected_value
            ):
                raise RjpAuditError(f"public v3 comparison counts drifted: {profile}")
        result_counts = _object(
            comparison_profile["quality_counts_result"],
            f"public_v3_comparison.{profile}.quality_counts_result",
        )
        if (
            _integer(
                result_counts["alarmed_correct_cases"],
                f"public_v3_comparison.{profile}.false_alarms",
            )
            != counts[3]
        ):
            raise RjpAuditError(f"public v3 false alarms drifted: {profile}")


def _validate_metadata(audit: dict[str, JsonValue]) -> None:
    if _string(audit["audit_date"], "audit_date") != AUDIT_DATE:
        raise RjpAuditError("audit date drifted")
    sources = _list(audit["exact_rjp_sources"], "exact_rjp_sources")
    if len(sources) != 2:
        raise RjpAuditError("exact RJP source list is incomplete")
    source_fields = {
        "id",
        "title",
        "publisher",
        "effective_date",
        "scope",
    }
    for index, raw_source in enumerate(sources):
        source = _object(raw_source, f"exact_rjp_sources[{index}]")
        _fields(
            source,
            source_fields
            | ({"landing_page", "document_url"} if index == 0 else {"url"}),
            f"exact_rjp_sources[{index}]",
        )
        for field in source:
            _string(source[field], f"exact_rjp_sources[{index}].{field}")
    if any(
        sources[0][field] != value
        for field, value in (
            ("id", "rjp-2026-orthography-interpunkcja"),
            ("title", RJP_CONSOLIDATED_TITLE),
            ("publisher", RJP_PUBLISHER),
            ("effective_date", "2026-01-01"),
            (
                "scope",
                "Orthography/punctuation authority only; no agreement, inflection, "
                "syntax, or completeness claim.",
            ),
        )
    ):
        raise RjpAuditError("consolidated RJP source identity drifted")
    if any(
        sources[1][field] != value
        for field, value in (
            ("id", "rjp-2025-withdrawal-notice"),
            ("title", RJP_WITHDRAWAL_TITLE),
            ("publisher", RJP_PUBLISHER),
            ("effective_date", "2025-11-07"),
            (
                "scope",
                "Enumerates official 2026 changes and withdraws numbered change "
                "8b; cannot generate a withdrawn candidate.",
            ),
        )
    ):
        raise RjpAuditError("RJP withdrawal source identity drifted")
    if (
        sources[0]["document_url"] != RJP_DOC_URL
        or sources[0]["landing_page"] != RJP_LANDING_URL
    ):
        raise RjpAuditError("consolidated RJP source identity drifted")
    if sources[1]["url"] != WITHDRAWAL_URL:
        raise RjpAuditError("RJP withdrawal source identity drifted")
    allowed = _object(audit["allowed_dispositions"], "allowed_dispositions")
    _fields(allowed, {"conformance", "implementation"}, "allowed_dispositions")
    if allowed["conformance"] != list(CONFORMANCE) or allowed["implementation"] != list(
        IMPLEMENTATION
    ):
        raise RjpAuditError("allowed disposition vocabulary drifted")
    snapshot = _object(audit["source_snapshot"], "source_snapshot")
    _fields(
        snapshot,
        {"derivation", "count", "sha256", "canonicalization"},
        "source_snapshot",
    )
    _string(snapshot["derivation"], "source_snapshot.derivation")
    _string(snapshot["canonicalization"], "source_snapshot.canonicalization")
    digest = _string(snapshot["sha256"], "source_snapshot.sha256")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise RjpAuditError("source snapshot digest is not SHA-256")
    review = _object(audit["maintainer_review_status"], "maintainer_review_status")
    _fields(
        review,
        {"status", "unresolved_or_unclear_row_count", "reason"},
        "maintainer_review_status",
    )
    _string(review["status"], "maintainer_review_status.status")
    _integer(
        review["unresolved_or_unclear_row_count"], "maintainer_review_status.count"
    )
    _string(review["reason"], "maintainer_review_status.reason")
    if review != EXPECTED_MAINTAINER_REVIEW_STATUS:
        raise RjpAuditError("maintainer review status drifted")
    if _list(audit["unresolved_questions"], "unresolved_questions"):
        raise RjpAuditError("unresolved questions are not closed")


def _validate_source_rows(
    audit: dict[str, JsonValue],
    identities: list[dict[str, str]],
) -> None:
    rows = _list(audit["source_rows"], "source_rows")
    if len(rows) != len(identities):
        raise RjpAuditError("source row count does not match the live snapshot")
    seen: set[str] = set()
    policy_keys_seen: set[tuple[str, str, str, str, str]] = set()
    counts = dict.fromkeys(CATEGORIES, 0)
    for index, (raw_row, identity) in enumerate(zip(rows, identities, strict=True)):
        row = _object(raw_row, f"source_rows[{index}]")
        _fields(
            row,
            {
                "source",
                "category",
                "operation",
                "behavior_version",
                "maintained_public_description",
                "provider_requirement",
                "correction_policy_status",
                "normative_scope",
                "normative_references",
                "conformance_disposition",
                "supporting_public_positives",
                "supporting_public_hard_negatives",
                "ambiguity_abstention_notes",
                "action_required",
            },
            f"source_rows[{index}]",
        )
        source = _string(row["source"], f"source_rows[{index}].source")
        if source in seen or source != identity["source"]:
            raise RjpAuditError(f"source row parity drift at {source}")
        seen.add(source)
        category = _string(row["category"], f"source_rows[{index}].category")
        if category not in CATEGORIES:
            raise RjpAuditError(f"unsupported source category: {category}")
        counts[category] += 1
        if (
            row["operation"] != identity["operation"]
            or row["behavior_version"] != identity["behavior_version"]
        ):
            raise RjpAuditError(f"source operation/version drift: {source}")
        _string(row["maintained_public_description"], f"{source}.description")
        provider = _string(row["provider_requirement"], f"{source}.provider")
        if (
            "morfeusz2-" in identity["behavior_version"]
            and MORPHOLOGY_FRAGMENT not in provider
        ):
            raise RjpAuditError(f"qualified provider identity missing: {source}")
        policy = _string(
            row["correction_policy_status"], f"{source}.correction_policy_status"
        )
        if policy not in {"automatic", "review-only"}:
            raise RjpAuditError(f"unsupported correction policy: {source}")
        policy_key = (
            source,
            category,
            str(row["operation"]),
            str(row["behavior_version"]),
            SOURCE_POLICY_VERSION,
        )
        policy_keys_seen.add(policy_key)
        expected_policy = (
            "automatic" if policy_key in AUTOMATIC_POLICY_KEYS else "review-only"
        )
        if policy != expected_policy:
            raise RjpAuditError(f"correction policy parity drift: {source}")
        scope = _string(row["normative_scope"], f"{source}.normative_scope")
        references = _list(
            row["normative_references"], f"{source}.normative_references"
        )
        if scope == "governed-by-rjp" and not references:
            raise RjpAuditError(f"RJP reference missing: {source}")
        if scope == "governed-by-rjp":
            for reference_index, raw_reference in enumerate(references):
                reference = _object(
                    raw_reference,
                    f"{source}.normative_references[{reference_index}]",
                )
                _fields(
                    reference,
                    {"authority_id", "url", "title", "effective_date", "locator"},
                    f"{source}.normative_references[{reference_index}]",
                )
                if (
                    reference["authority_id"] != "rjp-2026-orthography-interpunkcja"
                    or reference["url"] != RJP_DOC_URL
                    or reference["effective_date"] != "2026-01-01"
                    or reference["title"] != "Zasady pisowni i interpunkcji polskiej"
                ):
                    raise RjpAuditError(f"RJP reference identity drift: {source}")
                locator = _string(reference["locator"], f"{source}.reference.locator")
                valid_locator = locator == SOURCE_RJP_LOCATORS.get(source)
                if not valid_locator:
                    raise RjpAuditError(f"RJP reference locator drift: {source}")
        if scope == "not-governed-by-audited-rjp-material" and references:
            raise RjpAuditError(f"non-RJP source has a normative reference: {source}")
        if scope not in {
            "governed-by-rjp",
            "governed-by-another-authority",
            "not-governed-by-audited-rjp-material",
        }:
            raise RjpAuditError(f"unsupported normative scope: {source}")
        conformance = _string(row["conformance_disposition"], f"{source}.disposition")
        if conformance not in CONFORMANCE:
            raise RjpAuditError(f"unsupported conformance disposition: {source}")
        if scope == "not-governed-by-audited-rjp-material":
            if conformance != scope:
                raise RjpAuditError(
                    f"normative conformance contradicts scope: {source}"
                )
        elif conformance == "not-governed-by-audited-rjp-material":
            raise RjpAuditError(f"normative conformance contradicts scope: {source}")
        for field in (
            "supporting_public_positives",
            "supporting_public_hard_negatives",
        ):
            evidence = _list(row[field], f"{source}.{field}")
            if not evidence:
                raise RjpAuditError(f"missing public evidence: {source}.{field}")
            for evidence_index, raw_evidence in enumerate(evidence):
                evidence_item = _object(
                    raw_evidence, f"{source}.{field}[{evidence_index}]"
                )
                _fields(
                    evidence_item,
                    {"path", "locator"},
                    f"{source}.{field}[{evidence_index}]",
                )
                path = _string(
                    evidence_item["path"], f"{source}.{field}[{evidence_index}].path"
                )
                if (
                    path not in PUBLIC_EVIDENCE_PATHS
                    or not (AUDIT_PATH.parents[2] / path).is_file()
                ):
                    raise RjpAuditError(f"unsupported public evidence path: {source}")
                _string(
                    evidence_item["locator"],
                    f"{source}.{field}[{evidence_index}].locator",
                )
        _string(
            row["ambiguity_abstention_notes"], f"{source}.ambiguity_abstention_notes"
        )
        _string(row["action_required"], f"{source}.action_required")
    if not AUTOMATIC_POLICY_KEYS <= policy_keys_seen:
        raise RjpAuditError("automatic correction policy has an unlisted source key")
    summary = _object(audit["category_summary"], "category_summary")
    if set(summary) != set(CATEGORIES):
        raise RjpAuditError("category summary does not cover all categories")
    for category in CATEGORIES:
        item = _object(summary[category], f"category_summary.{category}")
        if (
            _integer(item["source_count"], f"category_summary.{category}.source_count")
            != counts[category]
        ):
            raise RjpAuditError(f"category source count drift: {category}")
    if summary != EXPECTED_CATEGORY_SUMMARY:
        raise RjpAuditError("category summary drifted")


def _validate_changes(audit: dict[str, JsonValue], sources: set[str]) -> None:
    changes = _list(audit["change_rows"], "change_rows")
    expected_prefixes = tuple(f"RJP-{number}:" for number in CHANGE_NUMBERS)
    if len(changes) != len(CHANGE_NUMBERS):
        raise RjpAuditError("official change row count is incomplete")
    seen: set[str] = set()
    for index, raw_change in enumerate(changes):
        change = _object(raw_change, f"change_rows[{index}]")
        _fields(
            change,
            {
                "official_number_or_name",
                "effective_date",
                "exact_rjp_reference",
                "concise_paraphrase",
                "affected_categories",
                "affected_phenomena",
                "existing_polis_source_identities",
                "deterministic_boundary_analysis",
                "provider_requirement",
                "positive_example_candidates",
                "hard_negative_or_ambiguity_candidates",
                "implementation_disposition",
                "rationale",
                "evidence_links",
                "withdrawn",
            },
            f"change_rows[{index}]",
        )
        title = _string(change["official_number_or_name"], f"change_rows[{index}].name")
        prefix = next(
            (value for value in expected_prefixes if title.startswith(value)), None
        )
        if prefix is None or prefix in seen:
            raise RjpAuditError(
                "official change numbering is missing, extra, or duplicated"
            )
        seen.add(prefix)
        expected_title, expected_paraphrase = EXPECTED_CHANGE_DETAILS[prefix]
        if title != expected_title:
            raise RjpAuditError(f"official change name drifted: {prefix}")
        _string(change["effective_date"], f"{prefix}.effective_date")
        expected_effective_date = (
            "2025-11-07 withdrawal" if prefix.endswith("08b:") else "2026-01-01"
        )
        if change["effective_date"] != expected_effective_date:
            raise RjpAuditError(f"effective date drifted: {prefix}")
        refs = _list(change["exact_rjp_reference"], f"{prefix}.reference")
        if len(refs) != 1:
            raise RjpAuditError(f"normative reference missing: {prefix}")
        reference = _object(refs[0], f"{prefix}.reference")
        _fields(
            reference,
            {
                "authority_id",
                "url",
                "title",
                "effective_date",
                "locator",
                "official_number",
            },
            f"{prefix}.reference",
        )
        expected_number = prefix.removeprefix("RJP-").removesuffix(":")
        if reference["official_number"] != expected_number:
            raise RjpAuditError(f"official reference number drifted: {prefix}")
        if prefix.endswith("08b:"):
            expected_reference = (
                "rjp-2025-withdrawal-notice",
                WITHDRAWAL_URL,
                "2025-11-07",
            )
        else:
            expected_reference = (
                "rjp-2025-withdrawal-notice",
                WITHDRAWAL_URL,
                "2026-01-01",
            )
        if (
            tuple(
                reference[field] for field in ("authority_id", "url", "effective_date")
            )
            != expected_reference
        ):
            raise RjpAuditError(f"official reference identity drifted: {prefix}")
        expected_locator = (
            "wycofanie pkt 8b"
            if prefix.endswith("08b:")
            else f"Załącznik nr 1, pkt {expected_number.lstrip('0')}"
        )
        if (
            reference["title"] != RJP_WITHDRAWAL_TITLE
            or reference["locator"] != expected_locator
        ):
            raise RjpAuditError(f"official reference locator drifted: {prefix}")
        categories = _list(change["affected_categories"], f"{prefix}.categories")
        if not categories or any(
            _string(item, f"{prefix}.category") not in CATEGORIES for item in categories
        ):
            raise RjpAuditError(f"invalid affected categories: {prefix}")
        existing = _list(
            change["existing_polis_source_identities"], f"{prefix}.sources"
        )
        if any(_string(item, f"{prefix}.source") not in sources for item in existing):
            raise RjpAuditError(f"unknown existing source in {prefix}")
        if change["concise_paraphrase"] != expected_paraphrase:
            raise RjpAuditError(f"official change paraphrase drifted: {prefix}")
        for field in (
            "concise_paraphrase",
            "deterministic_boundary_analysis",
            "rationale",
        ):
            _substantive(change[field], f"{prefix}.{field}")
        disposition = _string(
            change["implementation_disposition"], f"{prefix}.disposition"
        )
        if disposition not in IMPLEMENTATION:
            raise RjpAuditError(f"unsupported implementation disposition: {prefix}")
        admitted = disposition in {
            "deterministic_v1_candidate",
            "provider_dependent_candidate",
        }
        if admitted and prefix in ADMITTED_BOUNDARIES:
            if change["deterministic_boundary_analysis"] != ADMITTED_BOUNDARIES[prefix]:
                raise RjpAuditError(f"candidate boundary is incomplete: {prefix}")
        if prefix.endswith("08b:"):
            if not _boolean(change["withdrawn"], f"{prefix}.withdrawn") or admitted:
                raise RjpAuditError("withdrawn RJP-08b cannot generate a candidate")
        elif _boolean(change["withdrawn"], f"{prefix}.withdrawn"):
            raise RjpAuditError(f"unexpected withdrawn change: {prefix}")
        if disposition in {
            "deterministic_v1_candidate",
            "provider_dependent_candidate",
        }:
            _substantive(
                change["provider_requirement"], f"{prefix}.provider_requirement"
            )
            if disposition == "provider_dependent_candidate":
                provider = _string(
                    change["provider_requirement"], f"{prefix}.provider_requirement"
                ).casefold()
                boundary = _string(
                    change["deterministic_boundary_analysis"],
                    f"{prefix}.deterministic_boundary_analysis",
                ).casefold()
                rationale = _string(
                    change["rationale"], f"{prefix}.rationale"
                ).casefold()
                if not all(token in provider for token in ("qualified", "morfeusz2")):
                    raise RjpAuditError(f"provider boundary is incomplete: {prefix}")
                if provider != AUTHORIZED_PROVIDER_REQUIREMENT.casefold():
                    raise RjpAuditError(
                        f"authorized provider identity is incomplete: {prefix}"
                    )
                if "guard" not in boundary or "abstain" not in rationale:
                    raise RjpAuditError(f"provider behavior is incomplete: {prefix}")
                if prefix == "RJP-04:":
                    if change["deterministic_boundary_analysis"] != (
                        "Needs participle classification and licensed-separation guard."
                    ) or change["rationale"] != (
                        "Only exact qualified provider; review-only; absence or drift "
                        "abstains."
                    ):
                        raise RjpAuditError(f"provider evidence drifted: {prefix}")
            rationale = _string(change["rationale"], f"{prefix}.rationale").casefold()
            if "review-only" not in rationale:
                raise RjpAuditError(
                    f"candidate review boundary is incomplete: {prefix}"
                )
            if disposition == "deterministic_v1_candidate":
                provider = _string(
                    change["provider_requirement"], f"{prefix}.provider_requirement"
                ).casefold()
                if not all(
                    token in provider
                    for token in (
                        "provider-independent",
                        "provider absence",
                        "no morphology",
                    )
                ):
                    raise RjpAuditError(f"provider boundary is incomplete: {prefix}")
        else:
            _string(change["provider_requirement"], f"{prefix}.provider_requirement")
        phenomena = _list(change["affected_phenomena"], f"{prefix}.phenomena")
        if not phenomena or any(
            len(_string(item, f"{prefix}.phenomenon").strip()) < 4 for item in phenomena
        ):
            raise RjpAuditError(f"affected phenomena are incomplete: {prefix}")
        for field in (
            "positive_example_candidates",
            "hard_negative_or_ambiguity_candidates",
            "evidence_links",
        ):
            if not _list(change[field], f"{prefix}.{field}"):
                raise RjpAuditError(f"missing candidate evidence: {prefix}.{field}")
        for index, link in enumerate(
            _list(change["evidence_links"], f"{prefix}.evidence_links")
        ):
            link_value = _substantive(link, f"{prefix}.evidence_links[{index}]")
            if link_value not in {
                RJP_LANDING_URL,
                RJP_DOC_URL,
                WITHDRAWAL_URL,
                "docs/project/rule-coverage-contract-v1.json",
            }:
                raise RjpAuditError(f"unsupported evidence link: {prefix}")
        evidence_links = {
            _string(link, f"{prefix}.evidence_links[{index}]")
            for index, link in enumerate(
                _list(change["evidence_links"], f"{prefix}.evidence_links")
            )
        }
        required_links = (
            {RJP_LANDING_URL, WITHDRAWAL_URL}
            if prefix.endswith("08b:")
            else {RJP_LANDING_URL, RJP_DOC_URL}
        )
        if not required_links <= evidence_links:
            raise RjpAuditError(f"official evidence links are incomplete: {prefix}")
        candidates = _list(change["positive_example_candidates"], f"{prefix}.positive")
        candidate_objects: list[dict[str, JsonValue]] = []
        for candidate_index, raw_candidate in enumerate(candidates):
            candidate_location = f"{prefix}.positive[{candidate_index}]"
            candidate = _object(raw_candidate, candidate_location)
            _fields(
                candidate,
                {
                    "status",
                    "wrong_form",
                    "expected_form",
                    "category",
                    "edit_type",
                    "expected_span_behavior",
                },
                candidate_location,
            )
            status = _string(candidate["status"], f"{candidate_location}.status")
            if status not in {"admitted", "not-admitted"}:
                raise RjpAuditError(f"invalid candidate status: {prefix}")
            for field in ("category", "edit_type", "expected_span_behavior"):
                _string(candidate[field], f"{candidate_location}.{field}")
            for field in ("wrong_form", "expected_form"):
                if candidate[field] is not None:
                    _string(candidate[field], f"{candidate_location}.{field}")
            if candidate["category"] not in categories:
                raise RjpAuditError(f"invalid candidate shape: {prefix}")
            if candidate["edit_type"] not in {
                "replacement",
                "insertion",
                "not-applicable",
            }:
                raise RjpAuditError(f"invalid candidate shape: {prefix}")
            if status == "admitted":
                if candidate["edit_type"] == "not-applicable":
                    raise RjpAuditError(f"invalid candidate shape: {prefix}")
                if candidate["expected_span_behavior"] != ADMITTED_SPAN_BEHAVIOR:
                    raise RjpAuditError(
                        f"candidate span semantics are incomplete: {prefix}"
                    )
                if not candidate.get("wrong_form") or not candidate.get(
                    "expected_form"
                ):
                    raise RjpAuditError(
                        f"candidate admission fields are incomplete: {prefix}"
                    )
            candidate_objects.append(candidate)
        if admitted and not any(
            candidate["status"] == "admitted" for candidate in candidate_objects
        ):
            raise RjpAuditError(f"candidate admission fields are incomplete: {prefix}")
        for index, raw_negative in enumerate(
            _list(change["hard_negative_or_ambiguity_candidates"], f"{prefix}.negative")
        ):
            negative = _object(raw_negative, f"{prefix}.negative[{index}]")
            _fields(negative, {"status", "reason"}, f"{prefix}.negative[{index}]")
            status = _string(negative["status"], f"{prefix}.negative[{index}].status")
            reason = _substantive(
                negative["reason"], f"{prefix}.negative[{index}].reason"
            ).casefold()
            if admitted:
                if status != "required-boundary":
                    raise RjpAuditError(
                        f"candidate hard-negative status is incomplete: {prefix}"
                    )
                if not any(
                    marker in reason for marker in ("keep ", "do not ", "unchanged")
                ) or not any(
                    marker in reason
                    for marker in (
                        "only ",
                        "requires ",
                        "limited ",
                        "eligible",
                        "abstain",
                    )
                ):
                    raise RjpAuditError(
                        f"candidate hard-negative boundary is incomplete: {prefix}"
                    )
        if admitted and prefix in ADMITTED_NEGATIVE_MARKERS:
            reasons = " ".join(
                _string(
                    _object(raw_negative, f"{prefix}.negative[{index}]")["reason"],
                    f"{prefix}.negative[{index}].reason",
                ).casefold()
                for index, raw_negative in enumerate(
                    _list(
                        change["hard_negative_or_ambiguity_candidates"],
                        f"{prefix}.negative",
                    )
                )
            )
            if not all(
                marker in reasons for marker in ADMITTED_NEGATIVE_MARKERS[prefix]
            ):
                raise RjpAuditError(
                    f"candidate hard-negative coverage is incomplete: {prefix}"
                )
        if not admitted and any(
            candidate["status"] == "admitted" for candidate in candidate_objects
        ):
            raise RjpAuditError(f"non-candidate row is marked admitted: {prefix}")
    if seen != set(expected_prefixes):
        raise RjpAuditError("official change set is incomplete")


def _validate_maintainer_review_status(audit: dict[str, JsonValue]) -> None:
    review = _object(audit["maintainer_review_status"], "maintainer_review_status")
    unresolved_rows = 0
    for raw_row in _list(audit["source_rows"], "source_rows"):
        if isinstance(raw_row, dict) and raw_row.get("conformance_disposition") == (
            "unclear_fail_closed"
        ):
            unresolved_rows += 1
    for raw_change in _list(audit["change_rows"], "change_rows"):
        if (
            isinstance(raw_change, dict)
            and raw_change.get("implementation_disposition")
            == "unresolved_pending_clarification"
        ):
            unresolved_rows += 1
    if (
        _integer(
            review["unresolved_or_unclear_row_count"],
            "maintainer_review_status.count",
        )
        != unresolved_rows
    ):
        raise RjpAuditError("maintainer review row count is not reconciled")


def validate_rjp_2026_audit(path: Path = AUDIT_PATH) -> dict[str, JsonValue]:
    """Load and fail closed on the complete maintained RJP audit."""
    audit = _load(path)
    _fields(
        audit,
        {
            "schema_id",
            "schema_version",
            "issue",
            "parent_issue",
            "audited_full_sha",
            "audit_date",
            "normative_effective_date",
            "source_snapshot",
            "exact_rjp_sources",
            "allowed_dispositions",
            "public_v3_baseline",
            "category_summary",
            "source_rows",
            "change_rows",
            "unresolved_questions",
            "maintainer_review_status",
            "runtime_change",
            "protected_data_accessed",
        },
        "audit",
    )
    if (
        audit["schema_id"] != SCHEMA_ID
        or _integer(audit["schema_version"], "schema_version") != 1
        or _integer(audit["issue"], "issue") != 365
        or _integer(audit["parent_issue"], "parent_issue") != 363
    ):
        raise RjpAuditError("audit schema or issue identity drifted")
    audited_sha = _string(audit["audited_full_sha"], "audited_full_sha")
    if len(audited_sha) != 40 or any(
        character not in "0123456789abcdef" for character in audited_sha
    ):
        raise RjpAuditError("audited_full_sha is not a full Git SHA")
    _validate_audited_source_sha(audited_sha)
    if (
        _string(audit["normative_effective_date"], "normative_effective_date")
        != "2026-01-01"
    ):
        raise RjpAuditError("normative effective date drifted")
    identities, digest = _canonical_snapshot()
    snapshot = _object(audit["source_snapshot"], "source_snapshot")
    if (
        _integer(snapshot["count"], "source_snapshot.count") != len(identities)
        or _string(snapshot["sha256"], "source_snapshot.sha256") != digest
    ):
        raise RjpAuditError("source snapshot count or digest drifted")
    _validate_metadata(audit)
    _validate_v3_baseline(audit)
    _validate_source_rows(audit, identities)
    _validate_changes(audit, {item["source"] for item in identities})
    _validate_maintainer_review_status(audit)
    if audit["runtime_change"] != "none" or _boolean(
        audit["protected_data_accessed"], "protected_data_accessed"
    ):
        raise RjpAuditError(
            "audit claims an out-of-scope runtime or protected-data change"
        )
    return audit
