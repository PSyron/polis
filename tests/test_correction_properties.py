"""Bounded structural properties for correction conflict and application."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations, permutations

import pytest
from tests.generative import (
    SyntheticTextCase,
    assert_structural_invariant,
    generate_unicode_text_cases,
)

from polis import (
    CorrectionConflictError,
    CorrectionSelectionError,
    UncorrectableFindingError,
    UnknownFindingError,
)
from polis.core.models import (
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
)
from polis.correction import findings_conflict, sort_findings_for_application


@dataclass(frozen=True, slots=True)
class _Edit:
    start: int
    end: int
    suggestion: str | None


def test_generated_conflicts_are_symmetric_and_match_the_adr_oracle() -> None:
    for case in generate_unicode_text_cases():
        findings = tuple(_finding(case.text, edit) for edit in _conflict_edits(case))
        for first, second in permutations(findings, 2):
            expected = _adr_conflict(first, second)
            observed = findings_conflict(first, second)
            reverse = findings_conflict(second, first)
            assert_structural_invariant(
                observed == expected,
                invariant="correction.conflict.oracle",
                replay=case.replay,
            )
            assert_structural_invariant(
                observed == reverse,
                invariant="correction.conflict.symmetry",
                replay=case.replay,
            )


def test_generated_non_conflicting_edits_normalize_and_reconstruct_exactly() -> None:
    for case in generate_unicode_text_cases():
        edits = _non_conflicting_edits(case)
        findings = tuple(_finding(case.text, edit) for edit in edits)
        edits_by_id = {
            finding.id: edit for finding, edit in zip(findings, edits, strict=True)
        }
        result = AnalysisResult(text=case.text, issues=findings)

        for count in range(1, len(findings) + 1):
            for selected in combinations(findings, count):
                selected_edits = tuple(edits_by_id[finding.id] for finding in selected)
                expected_ids = tuple(
                    finding.id
                    for finding in _findings_in_right_to_left_order(
                        case.text, selected_edits
                    )
                )
                expected_text = _reconstruct_right_to_left(case.text, selected_edits)

                for selected_permutation in permutations(selected):
                    normalized = sort_findings_for_application(selected_permutation)
                    assert_structural_invariant(
                        tuple(finding.id for finding in normalized) == expected_ids,
                        invariant="correction.normalize.deterministic",
                        replay=case.replay,
                    )
                    assert_structural_invariant(
                        result.apply(finding.id for finding in selected_permutation)
                        == expected_text,
                        invariant="correction.apply.reconstruction",
                        replay=case.replay,
                    )


def test_generated_invalid_selections_fail_closed_without_mutating_results() -> None:
    for case in generate_unicode_text_cases()[1:]:
        replacement = _finding(case.text, _Edit(0, 1, "replacement"))
        insertion = _finding(case.text, _Edit(0, 0, "insertion"))
        uncorrectable = _finding(case.text, _Edit(0, 1, None))

        _assert_fail_closed(
            case,
            AnalysisResult(text=case.text, issues=(replacement, insertion)),
            (replacement.id, insertion.id),
            CorrectionConflictError,
        )
        _assert_fail_closed(
            case,
            AnalysisResult(text=case.text, issues=(replacement,)),
            ("unknown_finding",),
            UnknownFindingError,
        )
        _assert_fail_closed(
            case,
            AnalysisResult(text=case.text, issues=(replacement,)),
            (replacement.id, replacement.id),
            UnknownFindingError,
        )
        _assert_fail_closed(
            case,
            AnalysisResult(text=case.text, issues=(uncorrectable,)),
            (uncorrectable.id,),
            UncorrectableFindingError,
        )

        stale = AnalysisResult(text=case.text, issues=(replacement,))
        stale_text = "@" * len(case.text)
        object.__setattr__(stale, "text", stale_text)
        _assert_fail_closed(
            case,
            stale,
            (replacement.id,),
            UncorrectableFindingError,
        )


def test_generated_correction_failure_messages_are_replayable_and_private() -> None:
    case = generate_unicode_text_cases(count=2)[1]

    with pytest.raises(AssertionError) as error:
        assert_structural_invariant(
            False,
            invariant="correction.failure.privacy",
            replay=case.replay,
        )

    message = str(error.value)
    assert_structural_invariant(
        "correction.failure.privacy" in message,
        invariant="correction.failure.invariant",
        replay=case.replay,
    )
    assert_structural_invariant(
        str(case.replay) in message,
        invariant="correction.failure.replay",
        replay=case.replay,
    )
    assert_structural_invariant(
        case.text not in message,
        invariant="correction.failure.private",
        replay=case.replay,
    )


def _conflict_edits(case: SyntheticTextCase) -> tuple[_Edit, ...]:
    length = len(case.text)
    if length == 0:
        return (_Edit(0, 0, "first"), _Edit(0, 0, "second"))

    edits = [
        _Edit(0, 1, "replacement-a"),
        _Edit(0, 1, "replacement-b"),
        _Edit(0, 0, "at-start"),
        _Edit(1, 1, "at-end"),
        _Edit(1, 1, "at-end-duplicate"),
    ]
    if length > 1:
        edits.extend(
            (
                _Edit(0, 2, "wide-replacement"),
                _Edit(1, 1, "inside"),
                _Edit(1, 2, "touching-replacement"),
            )
        )
    return tuple(edits)


def _non_conflicting_edits(case: SyntheticTextCase) -> tuple[_Edit, ...]:
    length = len(case.text)
    digest = _edit_digest(case)
    if length == 0:
        return (_Edit(0, 0, "empty-insertion"),)
    replacement_start = digest[0] % length
    replacement = _Edit(
        replacement_start,
        replacement_start + 1,
        f"replacement-{digest[3]}",
    )
    if length == 1:
        return (replacement,)

    for offset in range(length):
        deletion_start = (digest[1] + offset) % length
        if deletion_start == replacement_start:
            continue
        deletion = _Edit(deletion_start, deletion_start + 1, "")
        insertion_offsets = _allowed_insertion_offsets(replacement, deletion, length)
        if insertion_offsets:
            insertion_start = insertion_offsets[digest[2] % len(insertion_offsets)]
            return (
                replacement,
                deletion,
                _Edit(insertion_start, insertion_start, f"insertion-{digest[4]}"),
            )

    deletion_start = (replacement_start + 1) % length
    return (replacement, _Edit(deletion_start, deletion_start + 1, ""))


def _edit_digest(case: SyntheticTextCase) -> bytes:
    replay = case.replay
    return sha256(
        f"correction-properties-v1:{replay.generator_version}:{replay.seed}:"
        f"{replay.case_index}".encode("ascii")
    ).digest()


def _allowed_insertion_offsets(
    replacement: _Edit, deletion: _Edit, text_length: int
) -> tuple[int, ...]:
    blocked = {
        replacement.start,
        replacement.end,
        deletion.start,
        deletion.end,
    }
    interior = tuple(
        offset for offset in range(1, text_length) if offset not in blocked
    )
    if interior:
        return interior
    return tuple(offset for offset in range(text_length + 1) if offset not in blocked)


def _finding(text: str, edit: _Edit) -> Finding:
    return Finding.create(
        category=Category.STYLE,
        severity=Severity.ERROR,
        message="Synthetic structural finding.",
        explanation="Generated correction-property fixture.",
        original=text[edit.start : edit.end],
        suggestion=edit.suggestion,
        start=edit.start,
        end=edit.end,
        confidence=Confidence(0.9),
        source=Source.parse("rule:correction-property"),
    )


def _adr_conflict(first: Finding, second: Finding) -> bool:
    first_is_insertion = first.start == first.end
    second_is_insertion = second.start == second.end
    if not first_is_insertion and not second_is_insertion:
        return bool(max(first.start, second.start) < min(first.end, second.end))
    if first_is_insertion and second_is_insertion:
        return bool(first.start == second.start)
    insertion, replacement = (first, second) if first_is_insertion else (second, first)
    return bool(replacement.start <= insertion.start <= replacement.end)


def _findings_in_right_to_left_order(
    text: str, edits: tuple[_Edit, ...]
) -> tuple[Finding, ...]:
    return tuple(
        _finding(text, edit)
        for edit in sorted(edits, key=lambda edit: edit.start, reverse=True)
    )


def _reconstruct_right_to_left(text: str, edits: tuple[_Edit, ...]) -> str:
    cursor = len(text)
    reconstructed = ""
    for edit in sorted(edits, key=lambda edit: edit.start, reverse=True):
        reconstructed = (
            (edit.suggestion or "") + text[edit.end : cursor] + reconstructed
        )
        cursor = edit.start
    return text[:cursor] + reconstructed


def _assert_fail_closed(
    case: SyntheticTextCase,
    result: AnalysisResult,
    issue_ids: tuple[str, ...],
    expected_error: type[CorrectionSelectionError],
) -> None:
    original_text = result.text
    original_issues = result.issues
    try:
        result.apply(issue_ids)
    except expected_error:
        raised_expected_error = True
    else:
        raised_expected_error = False

    assert_structural_invariant(
        raised_expected_error,
        invariant="correction.selection.fail-closed",
        replay=case.replay,
    )
    assert_structural_invariant(
        result.text == original_text and result.issues == original_issues,
        invariant="correction.selection.atomic",
        replay=case.replay,
    )
