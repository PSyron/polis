from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from polis import Analyzer, AnalyzerConfig, Category
from polis.rules.languagetool_stdio import LocalLanguageToolStdioSession

ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "third_party" / "languagetool-pl"
RUNNER = MODULE_ROOT / "scripts" / "run_stdio.sh"
QUALIFIED_RULE_IDS = {
    "BRAK_PRZECINKA_KTORY",
    "BRAK_PRZECINKA_SPOJNIK_PROSTY",
    "BRAK_PRZECINKA_ZE",
    "BRAK_PRZECINKA_ZEBY",
    "WOLACZ_BEZ_PRZECINKA",
}


def _check(
    text: str,
    *,
    operation: str | None = None,
    spans: list[dict[str, int]] | None = None,
) -> dict[str, Any]:
    request: dict[str, object] = {"text": text, "language": "pl-PL"}
    if operation is not None:
        request["operation"] = operation
    if spans is not None:
        request["spans"] = spans
    process = subprocess.run(
        [os.fspath(RUNNER)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload: Any = json.loads(process.stdout)
    assert isinstance(payload, dict)
    return payload


@pytest.mark.slow
def test_vendored_engine_finds_upstream_rule_on_unseen_sentence() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    payload = _check("Powiedział że jutro wróci.")
    matches = payload["matches"]
    assert isinstance(matches, list)
    assert matches
    assert {match["rule"]["id"] for match in matches} <= QUALIFIED_RULE_IDS
    assert any(match["rule"]["id"] == "BRAK_PRZECINKA_ZE" for match in matches)


@pytest.mark.slow
def test_vendored_engine_keeps_unseen_correct_sentence_clean() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    payload = _check("Powiedział, że jutro wróci.")
    assert payload["matches"] == []


@pytest.mark.slow
@pytest.mark.parametrize(
    ("sentence", "rule_id"),
    [
        ("Helena która mieszka obok przyniosła ciasto.", "BRAK_PRZECINKA_KTORY"),
        ("Było późno ale nikt nie wychodził.", "BRAK_PRZECINKA_SPOJNIK_PROSTY"),
        ("Wiem że jutro wrócisz.", "BRAK_PRZECINKA_ZE"),
        ("Leno proszę zamknij okno.", "WOLACZ_BEZ_PRZECINKA"),
    ],
)
def test_vendored_engine_exposes_each_newly_qualified_sentence_rule(
    sentence: str, rule_id: str
) -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    payload = _check(sentence)

    assert rule_id in {match["rule"]["id"] for match in payload["matches"]}


@pytest.mark.slow
@pytest.mark.parametrize(
    "sentence",
    [
        "Po spotkaniu wróciłem razem z Anną Kowalską.",
        "Spotkanie zaczyna się o 8.30 w sali 204.",
        "Dokumentacja jest dostępna pod adresem https://example.org/docs.",
        "Powiedziała: „Wrócę przed ósmą”.",
    ],
)
def test_vendored_engine_keeps_protected_sentences_clean(sentence: str) -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    assert _check(sentence)["matches"] == []


@pytest.mark.slow
def test_vendored_engine_opens_no_network_socket() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")
    lsof = shutil.which("lsof")
    if lsof is None:
        pytest.skip("lsof is required for the runtime socket audit")
    assert lsof is not None

    process = subprocess.Popen(
        [os.fspath(RUNNER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(
            json.dumps({"text": "To jest test.", "language": "pl-PL"}) + "\n"
        )
        process.stdin.flush()
        json.loads(process.stdout.readline())
        sockets = subprocess.run(
            [lsof, "-nP", "-a", "-p", str(process.pid), "-i"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        assert sockets.stdout.strip() == ""
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.wait(timeout=10)


@pytest.mark.slow
def test_inspection_exposes_unfiltered_rules_without_broadening_check() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    source = "To jest testt."
    inspected = _check(source, operation="inspect")
    checked = _check(source)
    inspected_ids = {match["rule"]["id"] for match in inspected["matches"]}
    checked_ids = {match["rule"]["id"] for match in checked["matches"]}

    assert inspected["operation"] == "inspect"
    assert inspected_ids - QUALIFIED_RULE_IDS
    assert checked_ids <= QUALIFIED_RULE_IDS


@pytest.mark.slow
def test_context_synthesis_preserves_tags_without_changing_synthesis_contract() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    spans = [{"start": 0, "end": 5}]
    contextual = _check("Paweł", operation="synthesize_context", spans=spans)
    existing = _check("Paweł", operation="synthesize", spans=spans)
    contextual_candidates = contextual["results"][0]["candidates"]
    existing_candidates = existing["results"][0]["candidates"]

    assert contextual["operation"] == "synthesize_context"
    assert all(
        candidate["tags"] == sorted(set(candidate["tags"]))
        for candidate in contextual_candidates
    )
    assert any(
        candidate["form"] == "Pawłowi" and "subst:sg:dat:m1" in candidate["tags"]
        for candidate in contextual_candidates
    )
    assert existing["operation"] == "synthesize"
    assert all("tags" not in candidate for candidate in existing_candidates)


@pytest.mark.slow
def test_analyzer_uses_real_context_synthesis_as_reviewable_sentence_suggestion() -> (
    None
):
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")
    analyzer = Analyzer(
        AnalyzerConfig(
            contextual_inflection_stdio_path=os.fspath(RUNNER.resolve()),
            contextual_inflection_timeout_seconds=30.0,
        )
    )
    source = "Rozmawiałem z Janem Nowak po przerwie."

    result = analyzer.correct(source)

    finding = next(
        item for item in result.skipped_findings if item.category is Category.INFLECTION
    )
    assert result.corrected_text == source
    assert finding.suggestion == "Nowakiem"
    assert result.apply_suggestions((finding.id,)) == (
        "Rozmawiałem z Janem Nowakiem po przerwie."
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("source", "expected_suggestions"),
    [
        ("Wróciła bez ciepła kurtka.", {"ciepłej", "kurtki"}),
        (
            "Przyglądam się czerwonego samochodu.",
            {"czerwonemu", "samochodowi"},
        ),
        ("Rozmawiałem z Janem Nowakiem po przerwie.", set()),
        ("Wróciła bez ciepłej kurtki.", set()),
        ("Przyglądam się czerwonemu samochodowi.", set()),
        ("Przyglądała się stary obraz.", set()),
        ("Jutro podziękuję Paweł za pomoc.", set()),
        ("Wersja 2.0 z https://example.org jest opisana jako „stabilna”.", set()),
    ],
)
def test_analyzer_preserves_frozen_contextual_inflection_behaviour(
    source: str, expected_suggestions: set[str]
) -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")
    analyzer = Analyzer(
        AnalyzerConfig(
            contextual_inflection_stdio_path=os.fspath(RUNNER.resolve()),
            contextual_inflection_timeout_seconds=30.0,
        )
    )

    result = analyzer.analyze(source)

    assert {
        item.suggestion
        for item in result.issues
        if item.category is Category.INFLECTION
    } == expected_suggestions


@pytest.mark.slow
def test_real_persistent_session_reuses_one_jvm_for_both_operations() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    with LocalLanguageToolStdioSession.from_executable(
        RUNNER.resolve(), timeout_seconds=30.0
    ) as session:
        checked = session.check(
            "Wiem że jutro wróci.",
            language="pl-PL",
            timeout_seconds=30.0,
        )
        process_id = session.process_id
        synthesized = session.synthesize_context(
            "Rozmawiałem z Janem Nowak po przerwie.",
            spans=((14, 19), (20, 25)),
            timeout_seconds=30.0,
        )

        assert process_id is not None
        assert session.process_id == process_id
        assert session.process_start_count == 1
        assert checked["software"] == {"name": "LanguageTool", "version": "6.8"}
        assert synthesized["operation"] == "synthesize_context"

    assert session.process_id is None


@pytest.mark.slow
def test_real_vendored_analyzer_preserves_source_policy_channels() -> None:
    if os.environ.get("POLIS_LT_VENDOR_INTEGRATION") != "1":
        pytest.skip("set POLIS_LT_VENDOR_INTEGRATION=1 after building the module")

    with Analyzer(
        AnalyzerConfig(
            vendored_language_tool_stdio_path=os.fspath(RUNNER.resolve()),
            vendored_language_tool_timeout_seconds=30.0,
        )
    ) as analyzer:
        punctuation = analyzer.correct("Wiem że jutro wróci.")
        inflection = analyzer.correct("Rozmawiałem z Janem Nowak po przerwie.")

    assert punctuation.corrected_text == "Wiem, że jutro wróci."
    assert {str(item.source) for item in punctuation.applied_findings} == {
        "rule:languagetool.pl"
    }
    assert inflection.corrected_text == inflection.original_text
    finding = next(
        item
        for item in inflection.skipped_findings
        if str(item.source) == "rule:languagetool.contextual_inflection"
    )
    assert inflection.apply_suggestions((finding.id,)) == (
        "Rozmawiałem z Janem Nowakiem po przerwie."
    )
