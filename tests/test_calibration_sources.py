from __future__ import annotations

import hashlib
import importlib.util
import math
from collections.abc import Callable

import pytest

_MODULE_NAME = "polis.evaluation.calibration_sources"
_MODULE_SPEC = importlib.util.find_spec(_MODULE_NAME)
pytestmark = pytest.mark.filterwarnings(
    "ignore:builtin type .* has no __module__ attribute:DeprecationWarning"
)


if _MODULE_SPEC is None:

    def test_planned_calibration_sources_module_is_available() -> None:
        pytest.fail("planned calibration sources module is absent")


else:
    import polis.evaluation.calibration_sources as calibration_sources
    from polis.evaluation.calibration_models import (
        CalibrationContractError,
        CalibrationSourceIdentity,
        JsonValue,
    )
    from polis.evaluation.calibration_sources import (
        SOURCE_ROWS,
        SOURCE_SNAPSHOT_SHA256,
        canonical_source_bytes,
        parse_source_rows,
        validate_live_sources,
    )
    from polis.evaluation.holdout_models import SourceIdentity

    type RowScalar = str | float | bool
    type RowMutation = Callable[[list[list[RowScalar]]], None]

    def _raw_rows() -> list[list[RowScalar]]:
        return [list(row.as_tuple()) for row in SOURCE_ROWS]

    def _without_last(rows: list[list[RowScalar]]) -> None:
        rows.pop()

    def _duplicate_first(rows: list[list[RowScalar]]) -> None:
        rows[-1] = list(rows[0])

    def _reverse_first_two(rows: list[list[RowScalar]]) -> None:
        rows[0], rows[1] = rows[1], rows[0]

    def test_source_snapshot_is_the_approved_ordered_20_by_7_contract() -> None:
        assert len(SOURCE_ROWS) == 20
        assert all(len(row.as_tuple()) == 7 for row in SOURCE_ROWS)
        assert hashlib.sha256(canonical_source_bytes()).hexdigest() == (
            "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
        )
        assert SOURCE_SNAPSHOT_SHA256 == (
            "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
        )
        assert sum(row.current_policy_state == "automatic" for row in SOURCE_ROWS) == 8
        assert (
            sum(row.current_policy_state == "review-only" for row in SOURCE_ROWS) == 12
        )

    @pytest.mark.parametrize(
        "mutate",
        [_without_last, _duplicate_first, _reverse_first_two],
        ids=["missing", "duplicate", "reordered"],
    )
    def test_source_parser_rejects_structural_snapshot_drift(
        mutate: RowMutation,
    ) -> None:
        rows = _raw_rows()
        mutate(rows)

        with pytest.raises(CalibrationContractError):
            parse_source_rows(rows)

    def test_source_parser_rejects_extra_twenty_first_row() -> None:
        rows = _raw_rows()
        rows.append(list(rows[-1]))

        with pytest.raises(CalibrationContractError):
            parse_source_rows(rows)

    @pytest.mark.parametrize(
        ("field_index", "replacement"),
        [
            (0, "rule:drifted.source"),
            (1, "spelling"),
            (2, "replace.drifted"),
            (3, "drifted/1.0"),
            (4, "9.9"),
            (5, 0.123),
            (6, "automatic"),
        ],
        ids=[
            "source",
            "category",
            "operation",
            "behavior",
            "policy",
            "confidence",
            "state",
        ],
    )
    def test_source_parser_rejects_field_drift(
        field_index: int,
        replacement: RowScalar,
    ) -> None:
        rows = _raw_rows()
        rows[1][field_index] = replacement

        with pytest.raises(CalibrationContractError):
            parse_source_rows(rows)

    @pytest.mark.parametrize(
        "invalid_confidence",
        [True, math.nan, math.inf, -math.inf],
        ids=["bool", "nan", "positive-infinity", "negative-infinity"],
    )
    def test_source_parser_rejects_nonfinite_or_boolean_confidence(
        invalid_confidence: float | bool,
    ) -> None:
        rows = _raw_rows()
        rows[0][5] = invalid_confidence

        with pytest.raises(CalibrationContractError):
            parse_source_rows(rows)

    def test_source_parser_returns_immutable_typed_rows() -> None:
        parsed = parse_source_rows(_raw_rows())

        assert parsed == SOURCE_ROWS
        assert all(isinstance(row, CalibrationSourceIdentity) for row in parsed)

    def test_live_source_validation_accepts_the_current_first_five_fields() -> None:
        assert validate_live_sources() == SOURCE_ROWS

    def test_live_source_validation_rejects_runtime_drift(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        current = tuple(SourceIdentity(*row.as_tuple()[:5]) for row in SOURCE_ROWS)
        drifted = current[:-1]

        monkeypatch.setattr(calibration_sources, "current_sources", lambda: drifted)

        with pytest.raises(CalibrationContractError):
            validate_live_sources()

    def test_live_source_validation_rejects_extra_runtime_source(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        current = tuple(SourceIdentity(*row.as_tuple()[:5]) for row in SOURCE_ROWS)
        extra = SourceIdentity(
            source="rule:agreement.unqualified_extra",
            category="agreement",
            operation="replace.unqualified_extra",
            behavior_version="agreement-unqualified-extra/1.0",
            source_policy_version="policy/absent-from-frozen-cohort",
        )

        monkeypatch.setattr(
            calibration_sources,
            "current_sources",
            lambda: (*current, extra),
        )

        with pytest.raises(CalibrationContractError):
            validate_live_sources()

    def test_live_source_validation_translates_snapshot_failure(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def unavailable() -> tuple[SourceIdentity, ...]:
            raise OSError(5, "synthetic source provider failure")

        monkeypatch.setattr(calibration_sources, "current_sources", unavailable)

        with pytest.raises(CalibrationContractError):
            validate_live_sources()

    def test_live_source_validation_translates_provider_type_error(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def invalid_provider_shape() -> tuple[SourceIdentity, ...]:
            raise TypeError

        monkeypatch.setattr(
            calibration_sources,
            "current_sources",
            invalid_provider_shape,
        )

        with pytest.raises(CalibrationContractError) as captured:
            validate_live_sources()

        assert isinstance(captured.value.__cause__, TypeError)

    def test_live_source_validation_translates_arbitrary_provider_exception(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class UnexpectedProviderError(Exception):
            pass

        def failing_provider() -> tuple[SourceIdentity, ...]:
            raise UnexpectedProviderError

        monkeypatch.setattr(
            calibration_sources,
            "current_sources",
            failing_provider,
        )

        with pytest.raises(CalibrationContractError) as captured:
            validate_live_sources()

        assert isinstance(captured.value.__cause__, UnexpectedProviderError)

    @pytest.mark.parametrize(
        "interruption",
        [KeyboardInterrupt, SystemExit],
        ids=["keyboard-interrupt", "system-exit"],
    )
    def test_live_source_validation_does_not_catch_process_interruptions(
        monkeypatch: pytest.MonkeyPatch,
        interruption: type[KeyboardInterrupt] | type[SystemExit],
    ) -> None:
        def interrupted_provider() -> tuple[SourceIdentity, ...]:
            raise interruption

        monkeypatch.setattr(
            calibration_sources,
            "current_sources",
            interrupted_provider,
        )

        with pytest.raises(interruption):
            validate_live_sources()

    def test_source_parser_rejects_non_list_root() -> None:
        invalid: JsonValue = "not-a-row-list"

        with pytest.raises(CalibrationContractError):
            parse_source_rows(invalid)
