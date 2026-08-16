"""Wave 3 (#341) review-only punctuation and capitalization sources."""

from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import Category, Confidence, Source, SourceKind
from polis.core.models import Finding, Severity
from polis.correction.policy import (
    SOURCE_POLICY_VERSION,
    SourceBehavior,
    is_automatic_correction_eligible,
)
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset

_CASES = (
    (
        "rule:syntax.comma_before_ze_reporting",
        "Wiem że Ania już wróciła.",
        "",
        ",",
        4,
        4,
    ),
    (
        "rule:syntax.comma_before_zeby_purpose",
        "Chcę żebyś wrócił.",
        "",
        ",",
        4,
        4,
    ),
    (
        "rule:syntax.comma_before_bo",
        "Nie idę bo pada.",
        "",
        ",",
        7,
        7,
    ),
    (
        "rule:spelling.month_weekday_lowercase",
        "Spotkamy się w Poniedziałek.",
        "Poniedziałek",
        "poniedziałek",
        15,
        27,
    ),
    (
        "rule:spelling.proper_adjective_lowercase",
        "Uczę się języka Polskiego.",
        "Polskiego",
        "polskiego",
        16,
        25,
    ),
    (
        "rule:spelling.sentence_initial_capital",
        "To działa. potem wróciłem.",
        "potem",
        "Potem",
        11,
        16,
    ),
    (
        "rule:punctuation.abbreviation_dot",
        "owoce, warzywa itp i wróciliśmy",
        "",
        ".",
        18,
        18,
    ),
)

_WAVE3 = tuple(item[0] for item in _CASES)


def test_runtime_exposes_fifty_nine_sources_after_wave3() -> None:
    snapshot = Analyzer(AnalyzerConfig()).source_identity_snapshot
    assert len(snapshot) >= 52
    sources = [item.source for item in snapshot]
    for source in _WAVE3:
        assert source in sources
    assert sources.index("rule:spelling.wlanczac") < sources.index(
        "rule:spelling.month_weekday_lowercase"
    )
    assert sources.index("rule:syntax.initial_temporal_comma") < sources.index(
        "rule:syntax.comma_before_ze_reporting"
    )
    assert sources[-1] == "rule:punctuation.abbreviation_dot"


@pytest.mark.parametrize(
    ("source", "text", "original", "suggestion", "start", "end"), _CASES
)
def test_wave3_emits_exact_contract(
    source: str,
    text: str,
    original: str,
    suggestion: str,
    start: int,
    end: int,
) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(text)
    hits = [item for item in result.issues if str(item.source) == source]
    assert hits
    finding = hits[0]
    assert finding.original == original
    assert finding.suggestion == suggestion
    assert (finding.start, finding.end) == (start, end)
    assert text[finding.start : finding.end] == original
    correction = Analyzer(AnalyzerConfig()).correct(text)
    assert correction.applied_findings == ()
    assert any(str(item.source) == source for item in correction.skipped_findings)


def test_month_weekday_abstains_on_holiday_uppercase_follower() -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        "Spotkamy się w Poniedziałek Wielkanocny."
    )
    assert not any(
        str(item.source) == "rule:spelling.month_weekday_lowercase"
        for item in result.issues
    )


def test_abbreviation_dot_covers_closed_set_and_excludes_np() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text, source_present in (
        ("owoce, warzywa itd i wróciliśmy", True),
        ("to tzn coś innego", True),
        ("owoce np warzywa", False),
    ):
        hits = [
            item
            for item in analyzer.analyze(text).issues
            if str(item.source) == "rule:punctuation.abbreviation_dot"
        ]
        assert bool(hits) is source_present


def test_comma_before_bo_excludes_precursor_allowlist() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text in (
        "To nie bo pada.",
        "Idę jak bo pada.",
        "Idę jako bo pada.",
        "Lepsze niż bo pada.",
    ):
        assert not any(
            str(item.source) == "rule:syntax.comma_before_bo"
            for item in analyzer.analyze(text).issues
        )


def test_ze_reporting_case_explicit_and_skips_nominalizations() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    assert any(
        str(item.source) == "rule:syntax.comma_before_ze_reporting"
        for item in analyzer.analyze("Wiem że Ania już wróciła.").issues
    )
    for text in (
        "Wiadomość że Ania wróciła.",
        "Twierdzenie że Ania wróciła.",
        "WIADOMOŚĆ że Ania wróciła.",
    ):
        assert not any(
            str(item.source) == "rule:syntax.comma_before_ze_reporting"
            for item in analyzer.analyze(text).issues
        )


def test_already_correct_and_existing_commas_abstain() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text, source in (
        ("Wiem, że Ania już wróciła.", "rule:syntax.comma_before_ze_reporting"),
        ("Chcę, żebyś wrócił.", "rule:syntax.comma_before_zeby_purpose"),
        ("Nie idę, bo pada.", "rule:syntax.comma_before_bo"),
        ("Spotkamy się w poniedziałek.", "rule:spelling.month_weekday_lowercase"),
        ("Uczę się języka polskiego.", "rule:spelling.proper_adjective_lowercase"),
        ("To działa. Potem wróciłem.", "rule:spelling.sentence_initial_capital"),
        ("owoce, warzywa itp. i wróciliśmy", "rule:punctuation.abbreviation_dot"),
    ):
        assert not any(
            str(item.source) == source for item in analyzer.analyze(text).issues
        )


@pytest.mark.parametrize("source", _WAVE3)
def test_wave3_sources_remain_review_only(source: str) -> None:
    name = source.removeprefix("rule:")
    meta = {
        "syntax.comma_before_ze_reporting": (
            Category.SYNTAX,
            "insert.reporting_clause_comma",
            "syntax-comma-before-ze-reporting/1.0",
        ),
        "syntax.comma_before_zeby_purpose": (
            Category.SYNTAX,
            "insert.purpose_clause_comma",
            "syntax-comma-before-zeby-purpose/1.0",
        ),
        "syntax.comma_before_bo": (
            Category.SYNTAX,
            "insert.causal_clause_comma",
            "syntax-comma-before-bo/1.0",
        ),
        "spelling.month_weekday_lowercase": (
            Category.SPELLING,
            "replace.case",
            "spelling-month-weekday-lowercase/1.0",
        ),
        "spelling.proper_adjective_lowercase": (
            Category.SPELLING,
            "replace.case",
            "spelling-proper-adjective-lowercase/1.0",
        ),
        "spelling.sentence_initial_capital": (
            Category.SPELLING,
            "replace.case",
            "spelling-sentence-initial-capital/1.0",
        ),
        "punctuation.abbreviation_dot": (
            Category.PUNCTUATION,
            "insert.abbreviation_dot",
            "punctuation-abbreviation-dot/1.0",
        ),
    }[name]
    category, operation, behavior_version = meta
    source_obj = Source(SourceKind.RULE, name)
    finding = Finding.create(
        category=category,
        severity=Severity.SUGGESTION,
        message="x",
        explanation="x",
        original="x",
        suggestion="y",
        start=0,
        end=1,
        confidence=Confidence(0.99),
        source=source_obj,
    )
    behavior = SourceBehavior(
        source=source_obj, operation=operation, behavior_version=behavior_version
    )
    assert not is_automatic_correction_eligible(
        finding, behavior, source_policy_version=SOURCE_POLICY_VERSION
    )


def test_wave3_v3_error_cases_flip_fn_to_tp() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    analyzer = Analyzer(AnalyzerConfig())
    samples = {
        "rule:syntax.comma_before_ze_reporting": "v3_comma_before_ze_reporting_error",
        "rule:syntax.comma_before_zeby_purpose": "v3_comma_before_zeby_purpose_error",
        "rule:syntax.comma_before_bo": "v3_comma_before_bo_error",
        "rule:spelling.month_weekday_lowercase": "v3_month_weekday_lowercase_error",
        "rule:spelling.proper_adjective_lowercase": (
            "v3_proper_adjective_lowercase_error"
        ),
        "rule:spelling.sentence_initial_capital": "v3_sentence_initial_capital_error",
        "rule:punctuation.abbreviation_dot": "v3_abbreviation_dot_error",
    }
    by_id = {case.id: case for case in dataset.cases}
    for source, case_id in samples.items():
        case = by_id[case_id]
        assert any(
            str(item.source) == source for item in analyzer.analyze(case.text).issues
        )
        pair = by_id[case_id.replace("_error", "_corrected_pair")]
        pair_hits = [
            item
            for item in analyzer.analyze(pair.text).issues
            if str(item.source) == source
        ]
        assert pair_hits == []
