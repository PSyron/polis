from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from polis import (
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
    analysis_result_from_json,
    analysis_result_to_json,
)


def make_finding(**changes: object) -> Finding:
    values: dict[str, object] = {
        "category": Category.AGREEMENT,
        "severity": Severity.ERROR,
        "message": "Niezgodność rodzaju zaimka i rzeczownika.",
        "explanation": "Forma „Te” nie zgadza się z rzeczownikiem „zdanie”.",
        "original": "Te zdanie",
        "suggestion": "To zdanie",
        "start": 0,
        "end": 9,
        "confidence": Confidence(0.98),
        "source": Source(SourceKind.RULE, "agreement"),
    }
    values.update(changes)
    return Finding.create(**values)


def test_categories_cover_the_mvp_detection_scope() -> None:
    assert {category.value for category in Category} == {
        "inflection",
        "agreement",
        "syntax",
        "spelling",
        "punctuation",
        "style",
    }


def test_severities_distinguish_errors_warnings_and_suggestions() -> None:
    assert {severity.value for severity in Severity} == {
        "error",
        "warning",
        "suggestion",
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("rule:agreement", Source(SourceKind.RULE, "agreement")),
        ("llm:local", Source(SourceKind.LLM, "local")),
    ],
)
def test_source_parses_and_formats_its_stable_wire_value(
    raw: str, expected: Source
) -> None:
    assert Source.parse(raw) == expected
    assert str(expected) == raw


@pytest.mark.parametrize(
    "raw",
    ["", "rule", "rule:", ":agreement", "remote:agreement", "rule:has space"],
)
def test_source_rejects_malformed_values(raw: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        Source.parse(raw)


@pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_confidence_rejects_values_outside_the_closed_unit_interval(
    value: float,
) -> None:
    with pytest.raises(ValueError):
        Confidence(value)


def test_confidence_rejects_boolean_values() -> None:
    with pytest.raises(TypeError):
        Confidence(True)


def test_confidence_rejects_numbers_too_large_for_a_finite_float() -> None:
    with pytest.raises(ValueError, match="finite"):
        Confidence(10**400)


def test_confidence_normalizes_negative_zero() -> None:
    negative_zero = Confidence(-0.0)

    assert math.copysign(1.0, negative_zero.value) == 1.0
    assert negative_zero == Confidence(0.0)


@pytest.mark.parametrize("value", [0, 0.25, 1])
def test_confidence_accepts_finite_real_values(value: float) -> None:
    assert Confidence(value).value == float(value)


@pytest.mark.parametrize(
    ("changes", "exception"),
    [
        ({"start": True}, TypeError),
        ({"end": False}, TypeError),
        ({"start": -1}, ValueError),
        ({"start": 9, "end": 4}, ValueError),
        ({"start": 4, "end": 4}, ValueError),
        ({"message": ""}, ValueError),
        ({"explanation": ""}, ValueError),
    ],
)
def test_finding_rejects_invalid_fields(
    changes: dict[str, object], exception: type[Exception]
) -> None:
    with pytest.raises(exception):
        make_finding(**changes)


def test_finding_identifier_is_stable_and_changes_with_identity() -> None:
    first = make_finding(confidence=Confidence(0.8), message="First wording")
    rerun = make_finding(confidence=Confidence(0.9), message="Revised wording")
    changed_suggestion = make_finding(suggestion="Tamto zdanie")

    assert first.id == rerun.id
    assert first.id.startswith("finding_")
    assert len(first.id) == len("finding_") + 32
    assert first.id != changed_suggestion.id


def test_finding_identifier_uses_verbatim_unicode_case_and_whitespace() -> None:
    canonical_order = make_finding(
        original="a\N{COMBINING DOT BELOW}\N{COMBINING ACUTE ACCENT}",
        suggestion="a",
        start=0,
        end=3,
    )
    reordered_marks = make_finding(
        original="a\N{COMBINING ACUTE ACCENT}\N{COMBINING DOT BELOW}",
        suggestion="a",
        start=0,
        end=3,
    )
    lowercase = make_finding(original="kot", suggestion="pies", start=0, end=3)
    uppercase = make_finding(original="Kot", suggestion="pies", start=0, end=3)
    trailing_space = make_finding(original="Kot ", suggestion="Kot", start=0, end=4)
    trailing_tab = make_finding(original="Kot\t", suggestion="Kot", start=0, end=4)

    assert len({canonical_order.id, reordered_marks.id}) == 2
    assert len({lowercase.id, uppercase.id}) == 2
    assert len({trailing_space.id, trailing_tab.id}) == 2


def test_finding_rejects_an_identifier_that_does_not_match_its_identity() -> None:
    with pytest.raises(ValueError, match="identity"):
        replace(make_finding(), id=f"finding_{'0' * 32}")


def test_finding_supports_a_zero_width_insertion() -> None:
    insertion = make_finding(
        original="", suggestion=".", start=3, end=3, category=Category.PUNCTUATION
    )

    assert insertion.start == insertion.end == 3
    assert insertion.original == ""


def test_finding_supports_whitespace_only_deletion() -> None:
    deletion = make_finding(
        original="  ", suggestion="", start=3, end=5, category=Category.SPELLING
    )

    assert deletion.original == "  "
    assert deletion.suggestion == ""


@pytest.mark.parametrize(
    ("original", "suggestion", "start", "end"),
    [("Te zdanie", "Te zdanie", 0, 9), ("", "", 3, 3)],
)
def test_finding_rejects_non_none_no_op_suggestions(
    original: str, suggestion: str, start: int, end: int
) -> None:
    with pytest.raises(ValueError, match="differ from original"):
        make_finding(original=original, suggestion=suggestion, start=start, end=end)


def test_direct_finding_reconstruction_rejects_a_no_op_suggestion() -> None:
    finding = make_finding()

    with pytest.raises(ValueError, match="differ from original"):
        replace(finding, suggestion=finding.original)


@pytest.mark.parametrize(
    ("original", "start", "end"),
    [("Te", 0, 1), ("🙂", 0, 2), ("e\N{COMBINING ACUTE ACCENT}", 0, 1)],
)
def test_finding_requires_span_length_to_equal_original_code_points(
    original: str, start: int, end: int
) -> None:
    with pytest.raises(ValueError, match="length"):
        make_finding(original=original, start=start, end=end)


def test_analysis_options_normalize_string_categories_and_confidence() -> None:
    options = AnalysisOptions(
        categories={"spelling", Category.AGREEMENT}, minimum_confidence=0.75
    )

    assert options.categories == frozenset({Category.SPELLING, Category.AGREEMENT})
    assert options.minimum_confidence == Confidence(0.75)


def test_analysis_options_distinguish_all_categories_from_no_categories() -> None:
    assert AnalysisOptions().categories is None
    assert AnalysisOptions(categories=set()).categories == frozenset()


def test_analysis_options_reject_invalid_category_and_boolean_confidence() -> None:
    with pytest.raises(ValueError):
        AnalysisOptions(categories={"unknown"})
    with pytest.raises(TypeError):
        AnalysisOptions(minimum_confidence=True)


def test_result_validates_unicode_offsets_against_the_original_text() -> None:
    text = "🙂 Te zdanie"
    issue = make_finding(original="Te zdanie", start=2, end=11)

    result = AnalysisResult(text=text, issues=(issue,))

    assert result.text[issue.start : issue.end] == issue.original
    assert result.issues == (issue,)


def test_result_accepts_insertion_at_end_of_text_and_whitespace_deletion() -> None:
    text = "Kot  śpi"
    whitespace_deletion = make_finding(
        original="  ", suggestion="", start=3, end=5, category=Category.SPELLING
    )
    end_insertion = make_finding(
        original="",
        suggestion=".",
        start=len(text),
        end=len(text),
        category=Category.PUNCTUATION,
    )

    result = AnalysisResult(text=text, issues=(whitespace_deletion, end_insertion))

    assert result.issues == (whitespace_deletion, end_insertion)


def test_result_rejects_zero_width_insertion_beyond_end_of_text() -> None:
    insertion = make_finding(original="", suggestion=".", start=4, end=4)

    with pytest.raises(ValueError, match="beyond"):
        AnalysisResult(text="Kot", issues=(insertion,))


@pytest.mark.parametrize(
    "issue",
    [
        make_finding(start=1, end=10),
        make_finding(original="Ta zdanie"),
    ],
)
def test_result_rejects_out_of_bounds_or_mismatched_fragments(issue: Finding) -> None:
    with pytest.raises(ValueError):
        AnalysisResult(text="Te zdanie", issues=(issue,))


def test_result_rejects_duplicate_finding_identifiers() -> None:
    issue = make_finding()

    with pytest.raises(ValueError, match="duplicate"):
        AnalysisResult(text="Te zdanie", issues=(issue, issue))


def test_result_rejects_distinct_findings_with_colliding_identity() -> None:
    first = make_finding(message="Pierwszy opis", confidence=Confidence(0.7))
    second = make_finding(message="Drugi opis", confidence=Confidence(0.9))

    assert first is not second
    assert first.id == second.id
    with pytest.raises(ValueError, match="duplicate"):
        AnalysisResult(text="Te zdanie", issues=(first, second))


def test_json_is_canonical_versioned_and_preserves_polish_text() -> None:
    result = AnalysisResult(
        text="Te zdanie zawiera błąd.",
        issues=(make_finding(),),
        options=AnalysisOptions(
            categories={"spelling", "agreement"}, minimum_confidence=0.5
        ),
    )

    encoded = analysis_result_to_json(result)

    assert encoded == analysis_result_to_json(result)
    assert "Niezgodność" in encoded
    assert '": ' not in encoded
    assert '", ' not in encoded
    payload = json.loads(encoded)
    assert payload["schema_version"] == 1
    assert payload["options"]["categories"] == ["agreement", "spelling"]
    assert payload["issues"][0] == {
        "category": "agreement",
        "confidence": 0.98,
        "end": 9,
        "explanation": "Forma „Te” nie zgadza się z rzeczownikiem „zdanie”.",
        "id": result.issues[0].id,
        "message": "Niezgodność rodzaju zaimka i rzeczownika.",
        "original": "Te zdanie",
        "severity": "error",
        "source": "rule:agreement",
        "start": 0,
        "suggestion": "To zdanie",
    }


def test_json_round_trip_is_lossless_including_optional_suggestion() -> None:
    result = AnalysisResult(
        text="Kot śpi.",
        issues=(
            make_finding(
                category=Category.STYLE,
                severity=Severity.SUGGESTION,
                original="Kot",
                suggestion=None,
                start=0,
                end=3,
                source=Source(SourceKind.LLM, "local"),
            ),
        ),
        options=AnalysisOptions(categories=set(), minimum_confidence=1),
    )

    decoded = analysis_result_from_json(analysis_result_to_json(result))

    assert decoded == result


def test_json_round_trip_preserves_insertion_and_whitespace_deletion() -> None:
    text = "Kot  śpi"
    result = AnalysisResult(
        text=text,
        issues=(
            make_finding(original="  ", suggestion="", start=3, end=5),
            make_finding(original="", suggestion=".", start=len(text), end=len(text)),
        ),
    )

    encoded = result.to_json()
    decoded = AnalysisResult.from_json(encoded)

    assert decoded == result
    assert tuple(issue.id for issue in decoded.issues) == tuple(
        issue.id for issue in result.issues
    )
    assert decoded.to_json() == encoded


def test_json_round_trip_preserves_none_as_no_replacement() -> None:
    result = AnalysisResult(text="Te zdanie", issues=(make_finding(suggestion=None),))

    encoded = result.to_json()

    assert AnalysisResult.from_json(encoded).to_json() == encoded
    assert AnalysisResult.from_json(encoded).issues[0].suggestion is None


def test_json_serializes_negative_and_positive_zero_confidence_identically() -> None:
    negative = AnalysisResult(
        text="Te zdanie", issues=(make_finding(confidence=Confidence(-0.0)),)
    )
    positive = AnalysisResult(
        text="Te zdanie", issues=(make_finding(confidence=Confidence(0.0)),)
    )

    assert negative.to_json() == positive.to_json()


def test_result_json_convenience_methods_use_the_same_schema() -> None:
    result = AnalysisResult(text="Te zdanie", issues=(make_finding(),))

    assert result.to_json() == analysis_result_to_json(result)
    assert AnalysisResult.from_json(result.to_json()) == result


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(schema_version=2),
        lambda payload: payload.update(extra=True),
        lambda payload: payload["options"].update(extra=True),
        lambda payload: payload["issues"][0].update(extra=True),
        lambda payload: payload["issues"][0].update(category="unknown"),
        lambda payload: payload["issues"][0].update(confidence=True),
        lambda payload: payload["issues"][0].update(start=True),
        lambda payload: payload["issues"][0].update(end=999),
    ],
)
def test_json_decoder_rejects_unknown_or_invalid_content(mutation: object) -> None:
    result = AnalysisResult(text="Te zdanie", issues=(make_finding(),))
    payload = json.loads(analysis_result_to_json(result))
    mutation(payload)  # type: ignore[operator]

    with pytest.raises((TypeError, ValueError)):
        analysis_result_from_json(json.dumps(payload))


def test_json_decoder_rejects_a_non_none_no_op_suggestion() -> None:
    result = AnalysisResult(text="Te zdanie", issues=(make_finding(),))
    payload = json.loads(analysis_result_to_json(result))
    payload["issues"][0]["suggestion"] = payload["issues"][0]["original"]

    with pytest.raises(ValueError, match="differ from original"):
        analysis_result_from_json(json.dumps(payload))


def test_json_decoder_rejects_duplicate_object_keys() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        analysis_result_from_json('{"schema_version":1,"schema_version":1}')


def test_json_decoder_rejects_non_finite_numbers() -> None:
    result = AnalysisResult(text="Te zdanie", issues=(make_finding(),))
    encoded = analysis_result_to_json(result).replace(
        '"confidence":0.98', '"confidence":NaN'
    )

    with pytest.raises(ValueError):
        analysis_result_from_json(encoded)


def test_json_decoder_converts_huge_numeric_overflow_to_value_error() -> None:
    result = AnalysisResult(text="Te zdanie", issues=(make_finding(),))
    encoded = analysis_result_to_json(result).replace(
        '"confidence":0.98', f'"confidence":{10**400}'
    )

    with pytest.raises(ValueError, match="finite"):
        analysis_result_from_json(encoded)
