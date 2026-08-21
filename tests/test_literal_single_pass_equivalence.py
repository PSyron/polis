"""F0.3 finding-level equivalence for the single-pass closed-literal scanner."""

from __future__ import annotations

import re
import unicodedata

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category, Finding
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset
from polis.rules.spelling import (
    SpellingCoNiemiaraRule,
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

_ORACLE_QUOTE_WRAPPERS = (
    ('"', '"'),
    ("'", "'"),
    ("`", "`"),
    ("„", "”"),
    ("“", "”"),
    ("‘", "’"),
    ("‚", "’"),
    ("«", "»"),
    ("‹", "›"),
    ("<", ">"),
)
_ORACLE_DIALOGUE_RE = re.compile(
    r"(?:^|[\s(\[{:;,.!?])(?:powiedział|powiedziała|powiedzieli|"
    r"rzekł|rzekła|zapytał|zapytała|krzyknął|krzyknęła|odparł|odparła)"
    r"(?:\s+\w+){0,4}\s*(?:(?::|[-–—])\s*)?$",
    flags=re.IGNORECASE,
)
_ORACLE_SAFE_BOUNDARIES = frozenset(".,;:!?…()[]{}<>-'\"`„”“«»‘’‹›「」『』〈〉《》-–—")


def _oracle_quote_context(text: str, start: int) -> tuple[str, int] | None:
    pairs = {opening: closing for opening, closing in _ORACLE_QUOTE_WRAPPERS}
    closing_characters = {
        closing for opening, closing in _ORACLE_QUOTE_WRAPPERS if opening != closing
    }
    stack: list[tuple[str, str, int]] = []
    for index, character in enumerate(text[:start]):
        closing = pairs.get(character)
        if closing is not None:
            if closing == character and stack and stack[-1][0] == character:
                stack.pop()
            else:
                stack.append((character, closing, index))
            continue
        if character in closing_characters:
            if not stack or stack[-1][1] != character:
                return "", index
            stack.pop()
    return (stack[-1][0], stack[-1][2]) if stack else None


def _oracle_co_niemiara_abstains(text: str, start: int, end: int) -> bool:
    for character in (
        text[start - 1] if start > 0 else "",
        text[end] if end < len(text) else "",
    ):
        category = unicodedata.category(character) if character else ""
        if category.startswith(("M", "Cf")) or (
            category.startswith("P") and character not in _ORACLE_SAFE_BOUNDARIES
        ):
            return True
    left = start
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    right = end
    while right < len(text) and not text[right].isspace():
        right += 1
    host = text[left:right]
    if any(
        character in host[: start - left] + host[end - left :]
        for character in "\\$()[]{}"
    ):
        return True
    context = _oracle_quote_context(text, start)
    if context is None:
        return False
    opening, opening_index = context
    if opening in {"", "`"}:
        return True
    return not bool(_ORACLE_DIALOGUE_RE.search(text[:opening_index]))


def _all_literal_rules() -> tuple[_CasePatternRule, ...]:
    return (
        SpellingZebyRule(),
        SpellingWlasnieRule(),
        SpellingJestesRule(),
        SpellingNapewnoRule(),
        SpellingWogoleRule(),
        SpellingNarazieRule(),
        SpellingWziascRule(),
        SpellingCoNiemiaraRule(),
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
            is_co_niemiara = str(rule.source) == "rule:spelling.co_niemiara"
            if is_co_niemiara and _oracle_co_niemiara_abstains(text, start, end):
                continue
            quote_context = _oracle_quote_context(text, start)
            allow_dialogue = bool(
                is_co_niemiara
                and quote_context is not None
                and _ORACLE_DIALOGUE_RE.search(text[: quote_context[1]])
            )
            if should_abstain_literal_context(
                text,
                start,
                end,
                quoted_position=False if is_co_niemiara else None,
                allow_dialogue=allow_dialogue,
            ):
                continue
            observed = match.group()
            if is_co_niemiara and not (
                observed.islower()
                or observed.isupper()
                or (observed[:1].isupper() and observed[1:].islower())
            ):
                continue
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
        'Powiedział: "Coniemiara".',
        "Powiedział: «Coniemiara?»",
        'Napis, "Mamy coniemiara problemów."',
        "Kod: `coniemiara + x`.",
        r"Path docs\coniemiara\index.",
        "Mamy problemów coniemiara‿wariant.",
        "Napis: „tekst “cytat” coniemiara”.",
        "Powiedział do Jana: „Mamy problemów coniemiara”.",
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
