from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import cast
from urllib.request import Request

import pytest
from experiments.languagetool_spike.benchmark import (
    BenchmarkCase,
    GoldEdit,
    LanguageToolMatch,
    RuntimeConfig,
    load_cases,
    parse_response,
    report_as_json,
    score_case,
    summarize,
    utf16_offset_to_codepoint,
)
from experiments.languagetool_spike.run_benchmark import LanguageToolClient

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
RESPONSE = ROOT / "tests" / "fixtures" / "languagetool" / "pl_response.json"


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(
        language="pl-PL",
        timeout_seconds=30.0,
        endpoint_policy="numeric-loopback-no-proxy",
        runtime_command="languagetool-server --port 8081",
        artifact="homebrew:languagetool@6.8",
        artifact_sha256="b" * 64,
        java_version="17.0.19",
    )


def _case(
    *,
    source: str = "Wiem że wróciła.",
    expected: str = "Wiem, że wróciła.",
    verification: str = "llm_planned",
) -> BenchmarkCase:
    return BenchmarkCase(
        case_id="comma",
        source=source,
        expected_output=expected,
        verification=verification,
        expected_edits=(GoldEdit("punctuation", 4, 4, "", ","),),
    )


def _match(
    *,
    start: int = 4,
    end: int = 4,
    replacements: tuple[str, ...] = (",",),
    rule_id: str = "PRZECINEK_PRZED_ZE",
    category: str = "punctuation",
) -> LanguageToolMatch:
    return LanguageToolMatch(
        start=start,
        end=end,
        original="",
        replacements=replacements,
        rule_id=rule_id,
        category=category,
    )


def test_utf16_offsets_are_converted_to_python_codepoints() -> None:
    text = "😀Wiem że"

    assert utf16_offset_to_codepoint(text, 2) == 1
    assert utf16_offset_to_codepoint(text, 6) == 5
    with pytest.raises(ValueError, match="surrogate"):
        utf16_offset_to_codepoint(text, 1)


def test_parser_validates_fixture_and_preserves_replacement_alternatives() -> None:
    payload = json.loads(RESPONSE.read_text(encoding="utf-8"))
    payload["matches"][0]["replacements"].append({"value": ";"})

    matches = parse_response("Wiem że wróciła.", payload)

    assert matches == (
        LanguageToolMatch(
            start=4,
            end=4,
            original="",
            replacements=(",", ";"),
            rule_id="PRZECINEK_PRZED_ZE",
            category="punctuation",
        ),
    )


def test_parser_keeps_unknown_category_unmapped_and_rejects_invalid_span() -> None:
    payload = json.loads(RESPONSE.read_text(encoding="utf-8"))
    payload["matches"][0]["rule"]["category"]["id"] = "FUTURE_CATEGORY"
    assert parse_response("Wiem że wróciła.", payload)[0].category == "unmapped"

    payload["matches"][0]["offset"] = 999
    with pytest.raises(ValueError, match="offset"):
        parse_response("Wiem że wróciła.", payload)


@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "matches list"),
        ({"matches": ["bad"]}, "match must be an object"),
        (
            {"matches": [{"offset": 0, "length": 0, "replacements": []}]},
            "rule metadata",
        ),
        (
            {
                "matches": [
                    {
                        "offset": 0,
                        "length": 0,
                        "replacements": None,
                        "rule": {"id": "RULE"},
                    }
                ]
            },
            "replacements must be a list",
        ),
    ],
)
def test_parser_rejects_malformed_response_shapes(
    payload: dict[str, object], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        parse_response("Tekst.", payload)


def test_parser_deduplicates_replacement_values() -> None:
    payload = json.loads(RESPONSE.read_text(encoding="utf-8"))
    payload["matches"][0]["replacements"].append({"value": ","})

    assert parse_response("Wiem że wróciła.", payload)[0].replacements == (",",)


def test_gold_can_be_second_replacement_without_being_top_output() -> None:
    score = score_case(_case(), (_match(replacements=(";", ",")),), latency_ms=5.0)

    assert score.true_positives == 1
    assert score.false_positives == 0
    assert score.false_negatives == 0
    assert score.gold_reachable is True
    assert score.top_output_exact is False


def test_gold_output_is_reachable_when_tool_uses_a_different_edit_span() -> None:
    case = BenchmarkCase(
        "spacing",
        "A.B",
        "A. B",
        "rules",
        (GoldEdit("punctuation", 2, 2, "", " "),),
    )
    match = LanguageToolMatch(
        1, 3, ".B", (". B",), "SENTENCE_WHITESPACE", "punctuation"
    )

    score = score_case(case, (match,), latency_ms=1)

    assert score.true_positives == 0
    assert score.top_output_exact is True
    assert score.gold_reachable is True


def test_duplicate_prediction_and_wrong_replacement_are_scored_strictly() -> None:
    duplicate = score_case(_case(), (_match(), _match(rule_id="DUP")), latency_ms=1)
    wrong = score_case(_case(), (_match(replacements=(";",)),), latency_ms=1)

    assert (duplicate.true_positives, duplicate.false_positives) == (1, 1)
    assert (wrong.false_positives, wrong.false_negatives) == (1, 1)


def test_exact_edit_requires_the_gold_category() -> None:
    score = score_case(_case(), (_match(category="syntax"),), latency_ms=1)

    assert score.true_positives == 0
    assert (score.false_positives, score.false_negatives) == (1, 1)


def test_overlapping_matches_are_skipped_deterministically() -> None:
    case = BenchmarkCase(
        case_id="overlap",
        source="abcd",
        expected_output="aXd",
        verification="llm_planned",
        expected_edits=(GoldEdit("syntax", 1, 3, "bc", "X"),),
    )
    matches = (
        LanguageToolMatch(1, 3, "bc", ("X",), "A", "syntax"),
        LanguageToolMatch(2, 4, "cd", ("Y",), "B", "syntax"),
    )

    score = score_case(case, matches, latency_ms=1)

    assert score.top_output_exact is True
    assert score.skipped_conflicts == 1


def test_insertion_at_replacement_end_conflicts_like_production() -> None:
    case = BenchmarkCase("boundary", "abc", "Abc", "rules", ())
    matches = (
        LanguageToolMatch(0, 1, "a", ("A",), "A", "spelling"),
        LanguageToolMatch(1, 1, "", ("!",), "B", "punctuation"),
    )

    score = score_case(case, matches, latency_ms=1)

    assert score.top_output_exact is True
    assert score.skipped_conflicts == 1


def test_any_changing_match_fails_negative_safety() -> None:
    case = BenchmarkCase("negative", "Dobrze.", "Dobrze.", "negative", ())
    match = LanguageToolMatch(0, 6, "Dobrze", ("Lepiej",), "STYLE", "style")

    score = score_case(case, (match,), latency_ms=2)

    assert score.negative_changed is True


def test_match_without_replacements_is_diagnostic_but_does_not_change_text() -> None:
    case = BenchmarkCase("negative", "Dobrze.", "Dobrze.", "negative", ())
    match = LanguageToolMatch(0, 6, "Dobrze", (), "DIAGNOSTIC", "style")

    score = score_case(case, (match,), latency_ms=2)

    assert score.false_positives == 1
    assert score.top_output_exact is True
    assert score.negative_changed is False


def test_summary_reports_percentiles_and_private_deterministic_json() -> None:
    scores = (
        score_case(_case(), (_match(),), latency_ms=10),
        score_case(_case(), (), latency_ms=20),
        score_case(_case(), (), latency_ms=30),
    )

    report = summarize(
        scores,
        tool_version="6.8",
        corpus_sha256="a" * 64,
        startup_ms=120.0,
        rss_kib=256000,
        runtime=_runtime(),
    )
    serialized = report_as_json(report)
    payload = json.loads(serialized)

    assert payload["summary"]["latency_p50_ms"] == 20
    assert payload["summary"]["latency_p95_ms"] == 30
    assert payload["tool"]["version"] == "6.8"
    assert payload["runtime"]["language"] == "pl-PL"
    assert payload["runtime"]["endpoint_policy"] == "numeric-loopback-no-proxy"
    assert "Wiem" not in serialized
    assert serialized == report_as_json(report)


def test_report_rejects_invalid_hashes_and_measurements() -> None:
    score = score_case(_case(), (), latency_ms=1)

    with pytest.raises(ValueError, match="SHA-256"):
        summarize(
            (score,),
            tool_version="6.8",
            corpus_sha256="z" * 64,
            startup_ms=1.0,
            rss_kib=1,
            runtime=_runtime(),
        )
    with pytest.raises(ValueError, match="startup"):
        summarize(
            (score,),
            tool_version="6.8",
            corpus_sha256="a" * 64,
            startup_ms=float("nan"),
            rss_kib=1,
            runtime=_runtime(),
        )
    with pytest.raises(ValueError, match="latency"):
        summarize(
            (replace(score, latency_ms=-1),),
            tool_version="6.8",
            corpus_sha256="a" * 64,
            startup_ms=1.0,
            rss_kib=1,
            runtime=_runtime(),
        )


def test_loader_includes_every_corpus_case_with_explicit_gold() -> None:
    cases = load_cases(CORPUS)

    assert len(cases) == 33
    assert {case.verification for case in cases} == {
        "rules",
        "llm_planned",
        "negative",
    }
    assert all(case.expected_edits for case in cases if case.verification != "negative")


def test_client_rejects_non_loopback_and_posts_polish_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="loopback"):
        LanguageToolClient("https://example.test", timeout_seconds=2)
    with pytest.raises(ValueError, match="numeric loopback"):
        LanguageToolClient("http://localhost:8081", timeout_seconds=2)

    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"software":{"version":"6.8"},"matches":[]}'

    class FakeOpener:
        def open(self, request: object, *, timeout: float) -> FakeResponse:
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

    monkeypatch.setattr(
        "experiments.languagetool_spike.run_benchmark._no_proxy_opener",
        lambda: FakeOpener(),
    )
    client = LanguageToolClient("http://127.0.0.1:8081", timeout_seconds=3)

    payload, elapsed = client.check("To jest test.")

    request = cast(Request, captured["request"])
    assert request.full_url == "http://127.0.0.1:8081/v2/check"
    assert request.data == b"language=pl-PL&text=To+jest+test."
    assert captured["timeout"] == 3
    software = payload["software"]
    assert isinstance(software, dict)
    assert software["version"] == "6.8"
    assert elapsed >= 0


@pytest.mark.slow
def test_local_languagetool_68_preserves_non_bmp_offsets() -> None:
    base_url = os.environ.get("POLIS_LANGUAGETOOL_URL")
    if base_url is None:
        pytest.skip("set POLIS_LANGUAGETOOL_URL for the local 6.8 integration test")
    assert base_url is not None
    source = "😀 Wiem że Anna wróciła."

    payload, _ = LanguageToolClient(base_url, timeout_seconds=30).check(source)
    software = payload.get("software")
    assert isinstance(software, dict)
    assert software.get("version") == "6.8"
    matches = parse_response(source, payload)

    comma_match = next(
        match for match in matches if match.rule_id == "BRAK_PRZECINKA_ZE"
    )
    assert (comma_match.start, comma_match.end, comma_match.original) == (
        2,
        9,
        "Wiem że",
    )
