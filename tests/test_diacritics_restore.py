from collections.abc import Mapping, Sequence
from time import perf_counter_ns

import pytest

import polis.analyzer as analyzer_module
import polis.rules._morfeusz as morfeusz_module
from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.diacritics import SpellingDiacriticsRestoreRule

type _AnalysisRow = tuple[int, int, tuple[str, str, str, list[str], list[str]]]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]


def _analysis_row(
    surface: str,
    lemma: str,
    tag: str,
    labels: tuple[str, ...] = (),
    *,
    qualifiers: tuple[str, ...] = (),
    start: int = 0,
    end: int = 1,
) -> _AnalysisRow:
    return (start, end, (surface, lemma, tag, list(labels), list(qualifiers)))


class _MappedBackend:
    def __init__(self, rows: Mapping[str, tuple[_AnalysisRow, ...]]) -> None:
        self._rows = dict(rows)
        self.calls: list[str] = []

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        self.calls.append(text)
        return self._rows.get(text, (_analysis_row(text, text, "ign"),))

    def generate(self, _lemma: str) -> Sequence[_GenerationRow]:
        return ()


def _provider(backend: _MappedBackend) -> _QualifiedMorfeusz:
    return _QualifiedMorfeusz(
        backend=backend,
        identity=morfeusz_module._qualified_identity(),
    )


@pytest.mark.parametrize(
    ("source", "suggestion"),
    (("isc", "iść"), ("pojsc", "pójść"), ("zolw", "żółw")),
)
def test_default_analyzer_restores_strict_positive_as_review_only_suggestion(
    source: str, suggestion: str
) -> None:
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(source)

    assert tuple(
        (
            str(finding.source),
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        for finding in result.issues
    ) == (("rule:spelling.diacritics_restore", source, suggestion, 0, len(source)),)

    finding = result.issues[0]
    behavior = analyzer._registry.source_behavior(finding.source)
    correction = analyzer.correct(source)

    assert behavior is not None
    assert behavior.operation == "replace.diacritics_restore"
    assert behavior.behavior_version == "spelling-diacritics-restore/1.0"
    assert correction.corrected_text == source
    assert correction.applied_findings == ()
    assert correction.skipped_findings == result.issues


@pytest.mark.parametrize(
    "text",
    (
        "rade",
        "Musze",
        "sad",
        "los",
        "zle",
        "pasek",
        "Muszę",
        "Ala",
        '"isc"',
        "„isc”",
        "`isc`",
        "isc2",
        "isc_value",
        "aaaaa",
    ),
)
def test_default_analyzer_abstains_from_strict_negative_contexts(text: str) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(text)

    assert (
        tuple(
            finding
            for finding in result.issues
            if str(finding.source) == "rule:spelling.diacritics_restore"
        )
        == ()
    )


def test_default_analyzer_keeps_token_spans_in_mixed_text() -> None:
    result = Analyzer(AnalyzerConfig()).analyze("isc, pojsc. zolw")

    assert tuple(
        (finding.original, finding.suggestion, finding.start, finding.end)
        for finding in result.issues
        if str(finding.source) == "rule:spelling.diacritics_restore"
    ) == (
        ("isc", "iść", 0, 3),
        ("pojsc", "pójść", 5, 10),
        ("zolw", "żółw", 12, 16),
    )


def test_default_analyzer_does_not_duplicate_existing_literal_sources() -> None:
    result = Analyzer(AnalyzerConfig()).analyze("Jestes Zeby naprawde")

    assert tuple(
        (
            str(finding.source),
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        for finding in result.issues
    ) == (
        ("rule:spelling.jestes", "Jestes", "Jesteś", 0, 6),
        ("rule:spelling.zeby", "Zeby", "Żeby", 7, 11),
        ("rule:spelling.naprawde", "naprawde", "naprawdę", 12, 20),
    )


def test_rule_rejects_proper_name_candidate() -> None:
    backend = _MappedBackend(
        {
            "foo": (_analysis_row("foo", "foo", "ign"),),
            "fóo": (_analysis_row("fóo", "Fóo", "subst:sg:nom:f", ("imię",)),),
        }
    )

    findings = SpellingDiacriticsRestoreRule(_provider(backend)).find(
        "foo", options=AnalysisOptions()
    )

    assert findings == ()


def test_rule_rejects_candidate_available_only_as_archaic_form() -> None:
    backend = _MappedBackend(
        {
            "asc": (_analysis_row("asc", "asc", "ign"),),
            "aść": (
                _analysis_row(
                    "aść",
                    "aść",
                    "subst:sg:nom:m1",
                    qualifiers=("daw.",),
                ),
            ),
        }
    )

    findings = SpellingDiacriticsRestoreRule(_provider(backend)).find(
        "asc", options=AnalysisOptions()
    )

    assert findings == ()


def test_rule_accepts_a_valid_multi_segment_provider_form() -> None:
    backend = _MappedBackend(
        {
            "chcialbym": (_analysis_row("chcialbym", "chcialbym", "ign"),),
            "chciałbym": (
                _analysis_row("chciał", "chcieć", "praet:sg:m1.m2.m3:imperf"),
                _analysis_row("by", "by:T", "part", start=1, end=2),
                _analysis_row("m", "być", "aglt:sg:pri:imperf:nwok", start=2, end=3),
            ),
        }
    )

    findings = SpellingDiacriticsRestoreRule(_provider(backend)).find(
        "chcialbym", options=AnalysisOptions()
    )

    assert tuple(
        (finding.original, finding.suggestion, finding.start, finding.end)
        for finding in findings
    ) == (("l", "ł", 5, 6),)


def test_rule_abstains_without_provider() -> None:
    assert (
        SpellingDiacriticsRestoreRule(None).find("isc", options=AnalysisOptions()) == ()
    )


def test_analyzer_reports_unavailable_provider_and_abstains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    morfeusz_module._OBSERVED_PROVIDER_IDENTITY.set(None)
    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: None)

    analyzer = Analyzer(AnalyzerConfig())

    assert analyzer.morphology_status.state == "unavailable"
    assert analyzer.analyze("isc").issues == ()


def test_analyzer_reports_drifted_provider_and_abstains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _MappedBackend({"isc": (_analysis_row("isc", "isc", "ign"),)})
    monkeypatch.setattr(analyzer_module, "_morphology_drift_warning_emitted", False)
    identity = morfeusz_module._qualified_identity()
    drifted = _QualifiedMorfeusz(
        backend=backend,
        identity=_ProviderIdentity(
            package_version=identity.package_version,
            dictionary_id="drifted-dictionary",
            dictionary_notice_sha256=identity.dictionary_notice_sha256,
        ),
    )
    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: drifted)

    analyzer = Analyzer(AnalyzerConfig())

    assert analyzer.morphology_status.state == "drifted"
    assert analyzer.analyze("isc").issues == ()


def test_rule_does_not_query_provider_past_position_limit() -> None:
    backend = _MappedBackend({})

    findings = SpellingDiacriticsRestoreRule(_provider(backend)).find(
        "aaaaa", options=AnalysisOptions()
    )

    assert findings == ()
    assert backend.calls == []


def test_warm_public_analyzer_p95_stays_below_five_milliseconds() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    analyzer.analyze("isc")

    durations_ns = []
    for _ in range(200):
        started = perf_counter_ns()
        analyzer.analyze("isc")
        durations_ns.append(perf_counter_ns() - started)

    p95_ns = sorted(durations_ns)[int(len(durations_ns) * 0.95) - 1]
    assert p95_ns <= 5_000_000
