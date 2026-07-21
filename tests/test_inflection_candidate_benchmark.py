from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from experiments.inflection_candidates.benchmark import (
    BenchmarkCase,
    BenchmarkObservation,
    CandidateBenchmarkReport,
    CandidateClass,
    CandidateSpanResult,
    InflectionCandidate,
    TimedCandidateResponse,
    UnsupportedReason,
    build_request_payload,
    load_authored_cases,
    load_corpus_cases,
    report_as_json,
    run_cases,
    stable_candidate_id,
    summarize_observations,
    validate_response,
)
from experiments.inflection_candidates.run_benchmark import LocalStdioClient

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "experiments" / "inflection_candidates" / "cases.json"
CORPUS_PATH = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)
MODULE_ROOT = ROOT / "third_party" / "languagetool-pl"


def _response_payload() -> dict[str, object]:
    first_id = stable_candidate_id(
        start=17,
        end=22,
        lemma="Paweł",
        form="Pawłowi",
        features=("dat", "m1", "sg", "subst"),
    )
    unchanged_id = stable_candidate_id(
        start=17,
        end=22,
        lemma="Paweł",
        form="Paweł",
        features=("m1", "nom", "sg", "subst"),
    )
    return {
        "operation": "synthesize",
        "language": "pl-PL",
        "results": [
            {
                "start": 17,
                "end": 22,
                "surface": "Paweł",
                "unsupported_reason": None,
                "candidates": [
                    {
                        "candidate_id": first_id,
                        "start": 17,
                        "end": 22,
                        "lemma": "Paweł",
                        "form": "Pawłowi",
                        "features": ["dat", "m1", "sg", "subst"],
                    },
                    {
                        "candidate_id": unchanged_id,
                        "start": 17,
                        "end": 22,
                        "lemma": "Paweł",
                        "form": "Paweł",
                        "features": ["m1", "nom", "sg", "subst"],
                    },
                ],
            }
        ],
    }


def test_validate_response_returns_narrow_auditable_candidates() -> None:
    result = validate_response(
        json.dumps(_response_payload(), ensure_ascii=False),
        source_text="Jutro podziękuję Paweł za pomoc.",
        requested_spans=((17, 22),),
    )

    assert result[0].surface == "Paweł"
    assert result[0].unsupported_reason is None
    assert result[0].candidates[0] == InflectionCandidate(
        candidate_id=stable_candidate_id(
            start=17,
            end=22,
            lemma="Paweł",
            form="Pawłowi",
            features=("dat", "m1", "sg", "subst"),
        ),
        start=17,
        end=22,
        lemma="Paweł",
        form="Pawłowi",
        features=("dat", "m1", "sg", "subst"),
    )
    assert any(candidate.form == "Paweł" for candidate in result[0].candidates)


def test_validate_response_rejects_unstable_or_duplicate_candidate_records() -> None:
    payload = _response_payload()
    results = payload["results"]
    assert isinstance(results, list)
    candidates = results[0]["candidates"]
    assert isinstance(candidates, list)
    candidates.append(dict(candidates[0]))

    with pytest.raises(ValueError, match="duplicate candidate_id"):
        validate_response(
            json.dumps(payload, ensure_ascii=False),
            source_text="Jutro podziękuję Paweł za pomoc.",
            requested_spans=((17, 22),),
        )


def test_validate_response_checks_original_offsets_and_sorted_features() -> None:
    payload = _response_payload()
    results = payload["results"]
    assert isinstance(results, list)
    candidates = results[0]["candidates"]
    assert isinstance(candidates, list)
    candidates[0]["features"] = ["subst", "dat"]

    with pytest.raises(ValueError, match="features must be sorted"):
        validate_response(
            json.dumps(payload, ensure_ascii=False),
            source_text="Jutro podziękuję Paweł za pomoc.",
            requested_spans=((17, 22),),
        )


def test_validate_response_rejects_candidate_id_not_derived_from_record() -> None:
    payload = _response_payload()
    results = payload["results"]
    assert isinstance(results, list)
    candidates = results[0]["candidates"]
    assert isinstance(candidates, list)
    candidates[0]["candidate_id"] = "ltpl:" + ("0" * 64)

    with pytest.raises(ValueError, match="candidate_id does not match"):
        validate_response(
            json.dumps(payload, ensure_ascii=False),
            source_text="Jutro podziękuję Paweł za pomoc.",
            requested_spans=((17, 22),),
        )


def test_authored_cases_cover_required_inflection_classes_and_edges() -> None:
    cases = load_authored_cases(CASES_PATH)

    assert {case.candidate_class for case in cases} == {
        "ordinary",
        "first_name",
        "surname",
    }
    covered = {tag for case in cases for tag in case.coverage}
    assert {
        "noun",
        "adjective",
        "capitalization",
        "diacritics",
        "indeclinable",
        "unknown",
        "already-inflected",
        "duplicate-form",
    } <= covered
    for case in cases:
        assert case.source[case.start : case.end] == case.surface
        assert case.surface in case.expected_forms


def test_corpus_cases_use_gold_only_as_oracle_not_candidate_input() -> None:
    cases = load_corpus_cases(CORPUS_PATH, split="development")

    assert cases
    assert {case.candidate_class for case in cases} == {
        "ordinary",
        "first_name",
        "surname",
    }
    for case in cases:
        assert case.source[case.start : case.end] == case.surface
        payload = build_request_payload(case)
        assert payload == {
            "operation": "synthesize",
            "language": "pl-PL",
            "text": case.source,
            "spans": [{"start": case.start, "end": case.end}],
        }
        for expected in case.expected_forms:
            if expected != case.surface:
                assert expected not in json.dumps(payload, ensure_ascii=False)


def _candidate(
    candidate_id: str, form: str, *, start: int = 0, end: int = 5
) -> InflectionCandidate:
    return InflectionCandidate(
        candidate_id=candidate_id,
        start=start,
        end=end,
        lemma=None,
        form=form,
        features=("subst",),
    )


def _observation(
    *,
    case_id: str,
    candidate_class: CandidateClass,
    expected: str,
    forms: tuple[str, ...],
    elapsed_ms: float,
    unsupported_reason: UnsupportedReason | None = None,
) -> BenchmarkObservation:
    case = BenchmarkCase(
        case_id=case_id,
        source="obraz",
        start=0,
        end=5,
        surface="obraz",
        candidate_class=candidate_class,
        expected_forms=(expected,),
        split="development",
    )
    result = CandidateSpanResult(
        start=0,
        end=5,
        surface="obraz",
        unsupported_reason=unsupported_reason,
        candidates=tuple(
            _candidate(f"ltpl:{index:064x}", form)
            for index, form in enumerate(forms, start=1)
        ),
    )
    return BenchmarkObservation(case=case, result=result, elapsed_ms=elapsed_ms)


def test_summary_separates_recall_ambiguity_and_unsupported_by_class() -> None:
    observations = (
        _observation(
            case_id="ordinary",
            candidate_class="ordinary",
            expected="obrazowi",
            forms=("obraz", "obrazu", "obrazowi"),
            elapsed_ms=1.0,
        ),
        _observation(
            case_id="first_name",
            candidate_class="first_name",
            expected="obraz",
            forms=("obraz",),
            elapsed_ms=3.0,
            unsupported_reason="no-alternatives",
        ),
        _observation(
            case_id="surname",
            candidate_class="surname",
            expected="obrazowi",
            forms=("obraz", "obrazu"),
            elapsed_ms=2.0,
        ),
    )

    report = summarize_observations(observations)

    assert isinstance(report, CandidateBenchmarkReport)
    assert report.total_cases == 3
    assert report.classes["ordinary"].expected_form_recall == 1.0
    assert report.classes["ordinary"].mean_ambiguity == 3.0
    assert report.classes["first_name"].unsupported_cases == 1
    assert report.classes["surname"].expected_form_recall == 0.0
    assert report.unchanged_coverage == 1.0
    assert report.warm_p50_ms == 2.0
    assert report.warm_p95_ms == 3.0


def test_summary_excludes_only_first_latency_from_warm_metrics() -> None:
    observations = (
        _observation(
            case_id="cold",
            candidate_class="ordinary",
            expected="obraz",
            forms=("obraz",),
            elapsed_ms=500.0,
        ),
        _observation(
            case_id="warm-1",
            candidate_class="ordinary",
            expected="obraz",
            forms=("obraz",),
            elapsed_ms=2.0,
        ),
        _observation(
            case_id="warm-2",
            candidate_class="ordinary",
            expected="obraz",
            forms=("obraz",),
            elapsed_ms=3.0,
        ),
    )

    report = summarize_observations(observations, exclude_first_latency=True)

    assert report.total_cases == 3
    assert len(report.cases) == 3
    assert report.warm_p50_ms == 2.5
    assert report.warm_p95_ms == 3.0


def test_report_json_contains_ids_and_metrics_but_no_source_text() -> None:
    observation = _observation(
        case_id="ordinary",
        candidate_class="ordinary",
        expected="obrazowi",
        forms=("obraz", "obrazowi"),
        elapsed_ms=2.0,
    )

    payload = json.loads(report_as_json(summarize_observations((observation,))))

    assert payload["cases"][0]["id"] == "ordinary"
    assert "source" not in payload["cases"][0]
    assert "expected_form_count" in payload["cases"][0]
    assert "obraz" not in json.dumps(payload, ensure_ascii=False)


def test_run_cases_preserves_order_and_records_local_latency() -> None:
    cases = (
        BenchmarkCase(
            case_id="first",
            source="obraz",
            start=0,
            end=5,
            surface="obraz",
            candidate_class="ordinary",
            expected_forms=("obrazowi",),
            split="development",
        ),
        BenchmarkCase(
            case_id="second",
            source="Nowak",
            start=0,
            end=5,
            surface="Nowak",
            candidate_class="surname",
            expected_forms=("Nowakiem",),
            split="development",
        ),
    )

    class FakeClient:
        def generate(self, case: BenchmarkCase) -> TimedCandidateResponse:
            result = CandidateSpanResult(
                start=case.start,
                end=case.end,
                surface=case.surface,
                unsupported_reason=None,
                candidates=(
                    InflectionCandidate(
                        candidate_id=f"ltpl:{len(case.case_id):064x}",
                        start=case.start,
                        end=case.end,
                        lemma=None,
                        form=case.surface,
                        features=("unchanged",),
                    ),
                ),
            )
            return TimedCandidateResponse(result=result, elapsed_ms=2.5)

    observations = run_cases(FakeClient(), cases)

    assert [item.case.case_id for item in observations] == ["first", "second"]
    assert all(item.elapsed_ms == 2.5 for item in observations)


@pytest.mark.slow
def test_real_stdio_client_generates_deduplicated_unicode_safe_candidates() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")
    case = BenchmarkCase(
        case_id="real_name",
        source="🙂 Paweł",
        start=2,
        end=7,
        surface="Paweł",
        candidate_class="first_name",
        expected_forms=("Pawłowi",),
        split="authored",
    )

    with LocalStdioClient(
        command=(os.fspath(MODULE_ROOT / "scripts" / "run_stdio.sh"),),
        cwd=MODULE_ROOT,
        timeout_seconds=30.0,
    ) as client:
        first = client.generate(case)
        second = client.generate(case)

    forms = [candidate.form for candidate in first.result.candidates]
    assert "Paweł" in forms
    assert "Pawłowi" in forms
    assert len(forms) == len(set(forms))
    assert first.result == second.result
    assert client.cold_start_ms > 0
    assert client.peak_rss_bytes > 0
