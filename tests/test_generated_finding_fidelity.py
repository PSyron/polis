"""Bounded generated checks for public finding and result fidelity."""

from __future__ import annotations

from collections.abc import Callable

from tests.generative import (
    assert_structural_invariant,
    generate_unicode_text_cases,
)

from polis.analysis import normalize_findings
from polis.core import (
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)


def test_generated_public_results_preserve_code_point_offsets_and_stable_ids() -> None:
    """Catch a public result accepting invalid generated findings."""
    for case in generate_unicode_text_cases():
        findings = _generated_findings(case.text)
        repeated_findings = _generated_findings(case.text)
        result = AnalysisResult(text=case.text, issues=findings)

        assert_structural_invariant(
            tuple(finding.id for finding in findings)
            == tuple(finding.id for finding in repeated_findings),
            invariant="finding.stable_ids",
            replay=case.replay,
        )
        assert_structural_invariant(
            result.issues == findings,
            invariant="result.finding_tuple",
            replay=case.replay,
        )
        for finding in result.issues:
            assert_structural_invariant(
                0 <= finding.start <= finding.end <= len(case.text),
                invariant="finding.bounds",
                replay=case.replay,
            )
            assert_structural_invariant(
                finding.original == case.text[finding.start : finding.end],
                invariant="finding.original_slice",
                replay=case.replay,
            )


def test_generated_permutations_normalize_to_hand_derived_canonical_order() -> None:
    """Catch normalization depending on the generated input order."""
    options = AnalysisOptions()
    for case in generate_unicode_text_cases():
        canonical = _generated_findings(case.text)
        permutations = (
            canonical,
            tuple(reversed(canonical)),
            canonical[1:] + canonical[:1],
        )

        for findings in permutations:
            assert_structural_invariant(
                normalize_findings(findings, options=options) == canonical,
                invariant="finding.canonical_normalization",
                replay=case.replay,
            )


def test_generated_results_have_deterministic_lossless_canonical_json() -> None:
    """Catch a canonical serializer or decoder losing result structure."""
    for case in generate_unicode_text_cases():
        result = AnalysisResult(text=case.text, issues=_generated_findings(case.text))
        independent_result = AnalysisResult(
            text=case.text, issues=_generated_findings(case.text)
        )
        encoded = result.to_json()
        independent_encoded = independent_result.to_json()
        decoded = AnalysisResult.from_json(encoded)
        independent_decoded = AnalysisResult.from_json(independent_encoded)

        assert_structural_invariant(
            result is not independent_result
            and result.issues is not independent_result.issues
            and len(result.issues) == len(independent_result.issues)
            and all(
                left is not right
                for left, right in zip(
                    result.issues, independent_result.issues, strict=False
                )
            )
            and result == independent_result,
            invariant="result.independent_construction",
            replay=case.replay,
        )
        assert_structural_invariant(
            encoded == independent_encoded,
            invariant="result.independent_canonical_json",
            replay=case.replay,
        )
        assert_structural_invariant(
            decoded == result
            and independent_decoded == independent_result
            and decoded.to_json() == encoded
            and independent_decoded.to_json() == independent_encoded,
            invariant="result.json_round_trip",
            replay=case.replay,
        )


def test_generated_invalid_findings_are_rejected_without_text_diagnostics() -> None:
    """Catch public results accepting invalid spans or leaking their text."""
    for case in generate_unicode_text_cases():
        out_of_bounds = _finding(
            original="",
            suggestion=".",
            start=len(case.text) + 1,
            end=len(case.text) + 1,
        )
        assert_structural_invariant(
            _rejection_hides_text(
                _result_with_finding,
                case.text,
                out_of_bounds,
                sensitive_excerpts=(case.text[-8:],),
            ),
            invariant="result.out_of_bounds_rejected",
            replay=case.replay,
        )

        if case.text:
            slice_end = min(8, len(case.text))
            actual_slice = case.text[:slice_end]
            wrong_original = _replacement_for(actual_slice[0]) + actual_slice[1:]
            invalid_slice = _finding(
                original=wrong_original,
                suggestion=actual_slice,
                start=0,
                end=slice_end,
            )
            assert_structural_invariant(
                _rejection_hides_text(
                    _result_with_finding,
                    case.text,
                    invalid_slice,
                    sensitive_excerpts=(actual_slice, wrong_original),
                ),
                invariant="result.invalid_slice_rejected",
                replay=case.replay,
            )


def _rejection_hides_text(
    operation: Callable[[str, Finding], AnalysisResult],
    text: str,
    finding: Finding,
    *,
    sensitive_excerpts: tuple[str, ...],
) -> bool:
    try:
        operation(text, finding)
    except (TypeError, ValueError) as error:
        diagnostic = str(error)
        return all(
            not excerpt or excerpt not in diagnostic
            for excerpt in (text, *sensitive_excerpts)
        )
    return False


def _result_with_finding(text: str, finding: Finding) -> AnalysisResult:
    return AnalysisResult(text=text, issues=(finding,))


def _finding(*, original: str, suggestion: str, start: int, end: int) -> Finding:
    return Finding.create(
        category=Category.PUNCTUATION,
        severity=Severity.ERROR,
        message="Generated structural finding.",
        explanation="Generated public-boundary fixture.",
        original=original,
        suggestion=suggestion,
        start=start,
        end=end,
        confidence=Confidence(0.9),
        source=Source(SourceKind.RULE, "generated_fidelity"),
    )


def _generated_findings(text: str) -> tuple[Finding, ...]:
    findings = [_finding(original="", suggestion=".", start=0, end=0)]
    if text:
        findings.append(
            _finding(
                original=text[0],
                suggestion=_replacement_for(text[0]),
                start=0,
                end=1,
            )
        )
    if len(text) > 1:
        findings.append(
            _finding(
                original=text[-1],
                suggestion="",
                start=len(text) - 1,
                end=len(text),
            )
        )
    return tuple(findings)


def _replacement_for(original: str) -> str:
    return "x" if original != "x" else "y"
