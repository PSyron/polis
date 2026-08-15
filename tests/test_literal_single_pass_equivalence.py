"""F0.3 finding-level equivalence for the single-pass closed-literal scanner."""

from __future__ import annotations

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category, Finding
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset
from polis.rules.spelling import (
    SpellingJestesRule,
    SpellingNapewnoRule,
    SpellingNarazieRule,
    SpellingWlasnieRule,
    SpellingWogoleRule,
    SpellingWziascRule,
    SpellingZebyRule,
    _CasePatternRule,
    collect_closed_literal_findings,
    should_abstain_literal_context,
)


def _all_literal_rules() -> tuple[_CasePatternRule, ...]:
    return (
        SpellingZebyRule(),
        SpellingWlasnieRule(),
        SpellingJestesRule(),
        SpellingNapewnoRule(),
        SpellingWogoleRule(),
        SpellingNarazieRule(),
        SpellingWziascRule(),
    )


def _finding_key(finding: Finding) -> tuple[str, int, int, str, str | None]:
    return (
        str(finding.source),
        finding.start,
        finding.end,
        finding.original,
        finding.suggestion,
    )


def scan_closed_literals_multipass(
    text: str, rules: tuple[_CasePatternRule, ...]
) -> dict[object, tuple[Finding, ...]]:
    """Historical per-rule pattern scan used as the F0.3 equivalence oracle."""
    buckets: dict[object, list[Finding]] = {rule.source: [] for rule in rules}
    for rule in rules:
        for match in rule._pattern.finditer(text):
            start = match.start()
            end = match.end()
            if should_abstain_literal_context(text, start, end):
                continue
            observed = match.group()
            candidate = rule._apply_case(observed, rule._corrected)
            if candidate == observed:
                continue
            buckets[rule.source].append(
                Finding.create(
                    category=rule._CATEGORY,
                    severity=rule._severity(),
                    message=rule._message(observed),
                    explanation=rule._explanation(observed, candidate),
                    original=observed,
                    suggestion=candidate,
                    start=start,
                    end=end,
                    confidence=rule._confidence,
                    source=rule.source,
                )
            )
    return {source: tuple(items) for source, items in buckets.items()}


def test_single_pass_matches_multipass_oracle_on_v2_case_texts() -> None:
    """Full v2 texts: single-pass and multipass agree on source/span/suggestion."""
    rules = _all_literal_rules()
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)

    for case in dataset.cases:
        single = collect_closed_literal_findings(case.text, rules)
        multi = scan_closed_literals_multipass(case.text, rules)
        assert {
            str(source): [_finding_key(item) for item in items]
            for source, items in single.items()
        } == {
            str(source): [_finding_key(item) for item in items]
            for source, items in multi.items()
        }, case.id


def test_single_pass_matches_multipass_on_hard_negative_and_mixed_contexts() -> None:
    rules = _all_literal_rules()
    texts = (
        "Zeby wogole napewno wlasnie jestes. Narazie wziasc.",
        "https://example.org/wogole/index.html",
        "Napisz do mnie: wogole@example.org",
        "Cytat: „Zdanie to jest wogole dziwne, jak pisano w 1925 r.” tak brzmi.",
        "example.org/wogole/index.html",
        "http://example.org/path?x=wogole",
        "Kontakt: admin@wogole.example.org",
        "Identyfikator foo-wogole-bar nie jest literówką zdaniową.",
        "Kod: wogole_v2 w konfiguracji.",
        "https://example.org/zeby/docs",
        "ŁÓDŹ: WOGOLE; Wogole, wogole.",
        "Ona jestem gotowa.Jestes pewna?",
    )
    for text in texts:
        single = collect_closed_literal_findings(text, rules)
        multi = scan_closed_literals_multipass(text, rules)
        assert {
            str(source): [_finding_key(item) for item in items]
            for source, items in single.items()
        } == {
            str(source): [_finding_key(item) for item in items]
            for source, items in multi.items()
        }, text


def test_standalone_rule_find_matches_single_pass_bucket() -> None:
    rules = _all_literal_rules()
    text = (
        "Zeby wogole napewno wlasnie jestes. "
        "Narazie wziasc. "
        "https://example.org/wogole/index.html "
        "wogole@example.org"
    )
    buckets = collect_closed_literal_findings(text, rules)
    options = AnalysisOptions()
    for rule in rules:
        assert buckets.get(rule.source, ()) == rule.find(text, options=options)


def test_default_analyzer_literal_findings_match_single_pass_on_v2() -> None:
    """Default profile: Analyzer spelling findings equal the shared scanner."""
    rules = _all_literal_rules()
    sources = {str(rule.source) for rule in rules}
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    analyzer = Analyzer(AnalyzerConfig())
    options = AnalysisOptions(categories={Category.SPELLING})

    for case in dataset.cases:
        analyzer_views = [
            _finding_key(finding)
            for finding in analyzer.analyze(case.text, options=options).issues
            if str(finding.source) in sources
        ]
        scanner_views = [
            _finding_key(finding)
            for rule in rules
            for finding in collect_closed_literal_findings(case.text, rules).get(
                rule.source, ()
            )
        ]
        # Analyzer emits in registration order; flatten scanner in the same order.
        ordered_scanner = [
            _finding_key(finding)
            for rule in rules
            for finding in collect_closed_literal_findings(case.text, (rule,)).get(
                rule.source, ()
            )
        ]
        assert analyzer_views == ordered_scanner, case.id
        assert sorted(analyzer_views) == sorted(scanner_views), case.id
