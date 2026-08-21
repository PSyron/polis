"""F0.3 finding-level equivalence for the single-pass closed-literal scanner."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from polis import Analyzer, AnalyzerConfig
from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
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
    ("「", "」"),
    ("『", "』"),
    ("〈", "〉"),
    ("《", "》"),
)
_ORACLE_DIALOGUE_RE = re.compile(
    r"(?:^|[\s(\[{:;,.!?])(?:powiedział|powiedziała|powiedzieli|"
    r"rzekł|rzekła|zapytał|zapytała|krzyknął|krzyknęła|odparł|odparła)"
    r"(?:\s+\w+){0,4}\s*(?:(?::|[-–—])\s*)?$",
    flags=re.IGNORECASE,
)
_ORACLE_SAFE_BOUNDARIES = frozenset(".,;:!?…()[]{}<>-'\"`„”“«»‘’‹›「」『』〈〉《》-–—")
_ORACLE_MENTION_WRAPPERS = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)
_ORACLE_HOST_EDGE_TRIM = frozenset(".,;:!?)]}\"»”'„“«")
_ORACLE_SCHEME_RE = re.compile(r"(?i)\b(?:https?|ftp)://")
_ORACLE_DOMAINISH_RE = re.compile(
    r"(?i)\b(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b"
)
_ORACLE_HOST_CHARS = frozenset("./:@?#%&+~_=-")
_ORACLE_SYMMETRIC_QUOTES = frozenset({'"', "'", "`"})
_ORACLE_OPERATOR_CHARACTERS = frozenset("=|^+*/%<>→←⇐⇒↔±×÷&~")
_ORACLE_PROPER_NAME_CUE_RE = re.compile(
    r"(?:^|[\s(\[{:;,.!?])(?:marka|markę|nazwa\s+produktu|"
    r"produkt(?:u|owa|owej)?)\s*$",
    flags=re.IGNORECASE,
)
_ORACLE_LITERAL_SPECS = {
    "rule:spelling.zeby": ("zeby", "żeby", 0.98),
    "rule:spelling.wlasnie": ("wlasnie", "właśnie", 0.97),
    "rule:spelling.jestes": ("jestes", "jesteś", 0.96),
    "rule:spelling.napewno": ("napewno", "na pewno", 0.98),
    "rule:spelling.wogole": ("wogole", "w ogóle", 0.98),
    "rule:spelling.narazie": ("narazie", "na razie", 0.98),
    "rule:spelling.wziasc": ("wziasc", "wziąć", 0.98),
    "rule:spelling.co_niemiara": ("coniemiara", "co niemiara", 0.98),
}


def _oracle_host_span(text: str, start: int, end: int) -> tuple[int, int]:
    left = start
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    right = end
    while right < len(text) and not text[right].isspace():
        right += 1
    while left < start and text[left] in _ORACLE_HOST_EDGE_TRIM:
        left += 1
    while right > end and text[right - 1] in _ORACLE_HOST_EDGE_TRIM:
        right -= 1
    return left, right


def _oracle_wrapped_mention(text: str, start: int, end: int) -> bool:
    if start <= 0 or end >= len(text):
        return False
    left = text[start - 1]
    if (left, text[end]) in _ORACLE_MENTION_WRAPPERS:
        return True
    return left == "`" and (text[end:].startswith("`") or text[end:].startswith("()`"))


def _oracle_quoted_position(text: str, position: int) -> bool:
    for opening, closing in (('"', '"'), ("„", "”"), ("“", "”"), ("«", "»")):
        before = text[:position]
        if opening == closing:
            if before.count(opening) % 2 == 1:
                return True
        elif before.rfind(opening) > before.rfind(closing):
            return True
    return False


def _oracle_symmetric_quote_is_ambiguous(text: str, index: int) -> bool:
    if index + 1 >= len(text):
        return False
    next_character = text[index + 1]
    return next_character.isalnum() or next_character in _ORACLE_SYMMETRIC_QUOTES


def _oracle_email_context(text: str, start: int, end: int) -> bool:
    if end < len(text) and text[end] == "@":
        return bool(re.match(r"[^\s@]+", text[end + 1 : end + 255]))
    if start > 0 and text[start - 1] == "@":
        return True
    left, right = _oracle_host_span(text, start, end)
    return "@" in text[left:right]


def _oracle_url_context(text: str, start: int, end: int) -> bool:
    left, right = _oracle_host_span(text, start, end)
    host = text[left:right]
    if _ORACLE_SCHEME_RE.search(host):
        return True
    if any(marker in host for marker in ("/", "?", "#")):
        if "://" in host or _ORACLE_DOMAINISH_RE.search(host):
            return True
        if "." in host and "/" in host:
            return True
        return False
    if (
        start >= 2
        and text[start - 1] == "."
        and text[start - 2].isalpha()
        and not any(marker in host for marker in ("/", "?", "#", "://"))
    ):
        return False
    if _ORACLE_DOMAINISH_RE.fullmatch(host) or _ORACLE_DOMAINISH_RE.search(host):
        return host != text[start:end]
    if start > 0 and text[start - 1] in {"/", "?", "#"}:
        return True
    return end < len(text) and text[end] in {"/", "?", "#"}


def _oracle_identifier_context(text: str, start: int, end: int) -> bool:
    left, right = _oracle_host_span(text, start, end)
    if left == start and right == end:
        return False
    host = text[left:right]
    if re.fullmatch(r"[\w]+\.[\w]+", host, flags=re.UNICODE):
        left_part, right_part = host.split(".", 1)
        if left_part.isalpha() and right_part.isalpha():
            return False
    if any(ch.isdigit() or ch == "_" for ch in host):
        return True
    if "-" in host and not _ORACLE_DOMAINISH_RE.search(host):
        return True
    return any(
        ch in _ORACLE_HOST_CHARS
        for index, ch in enumerate(host)
        if not (start <= left + index < end)
    )


def _oracle_base_abstains(text: str, start: int, end: int) -> bool:
    return (
        _oracle_wrapped_mention(text, start, end)
        or _oracle_quoted_position(text, start)
        or _oracle_email_context(text, start, end)
        or _oracle_url_context(text, start, end)
        or _oracle_identifier_context(text, start, end)
    )


def _oracle_question_operator(text: str, index: int) -> bool:
    left = index - 1
    while left >= 0 and text[left].isspace():
        left -= 1
    right = index + 1
    while right < len(text) and text[right].isspace():
        right += 1
    if left < 0 or right >= len(text):
        return False
    return (text[left].isalnum() or text[left] in "_)]}") and (
        text[right].isalnum() or text[right] in "_([{`"
    )


def _oracle_operator_context(text: str, start: int, end: int) -> bool:
    for index, step in ((start - 1, -1), (end, 1)):
        skipped = 0
        while 0 <= index < len(text) and text[index].isspace():
            skipped += 1
            if skipped > 256:
                return True
            index += step
        if 0 <= index < len(text):
            if text[index] in _ORACLE_OPERATOR_CHARACTERS:
                return True
            if text[index] == "?" and _oracle_question_operator(text, index):
                return True
    return False


def _oracle_sentence_initial(text: str, start: int) -> bool:
    prefix = text[:start].rstrip()
    return not prefix or prefix[-1] in ".!?…"


@dataclass
class _OracleFrame:
    opening: str
    closing: str
    opening_index: int
    closing_index: int | None = None
    valid: bool = True


def _oracle_quote_context(
    text: str, start: int
) -> tuple[tuple[_OracleFrame, ...], bool] | None:
    pairs = {opening: closing for opening, closing in _ORACLE_QUOTE_WRAPPERS}
    closing_characters = {
        closing for opening, closing in _ORACLE_QUOTE_WRAPPERS if opening != closing
    }
    closing_frames: list[_OracleFrame] = []
    stack: list[_OracleFrame] = []
    uncertain = False
    target_stack: tuple[_OracleFrame, ...] | None = None
    target_uncertain = False
    for index, character in enumerate(text):
        if index == start:
            target_stack = tuple(stack)
            target_uncertain = uncertain
        if (
            character == "'"
            and index > 0
            and index + 1 < len(text)
            and text[index - 1].isalnum()
            and text[index + 1].isalnum()
        ):
            continue
        closing = pairs.get(character)
        if closing is not None:
            if closing == character and stack and stack[-1].closing == character:
                if _oracle_symmetric_quote_is_ambiguous(text, index):
                    for frame in stack:
                        frame.valid = False
                    stack.clear()
                    uncertain = True
                else:
                    frame = stack.pop()
                    frame.closing_index = index
                    closing_frames.append(frame)
            else:
                stack.append(_OracleFrame(character, closing, index))
            continue
        if character in closing_characters:
            if stack and stack[-1].closing == character:
                frame = stack.pop()
                frame.closing_index = index
                closing_frames.append(frame)
            else:
                for frame in stack:
                    frame.valid = False
                stack.clear()
                uncertain = True
    if stack:
        uncertain = True
    if target_stack is None:
        return None
    active = tuple(
        frame
        for frame in (*closing_frames, *stack)
        if frame.opening_index < start
        and (frame.closing_index is None or frame.closing_index > start)
    )
    return active, target_uncertain or uncertain


def _oracle_co_niemiara_abstains(text: str, start: int, end: int) -> bool:
    for character in (
        text[start - 1] if start > 0 else "",
        text[end] if end < len(text) else "",
    ):
        category = unicodedata.category(character) if character else ""
        if category.startswith(("M", "Cf", "S")) or (
            category.startswith("P") and character not in _ORACLE_SAFE_BOUNDARIES
        ):
            return True
    left = start
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    right = end
    while right < len(text) and not text[right].isspace():
        right += 1
    edge_trim = frozenset(".,;:!?)]}\"»”'„“«")
    while left < start and text[left] in edge_trim:
        left += 1
    while right > end and text[right - 1] in edge_trim:
        right -= 1
    host = text[left:right]
    if any(
        character in host[: start - left] + host[end - left :]
        for character in "./:@?#%&+~_-=\\.$()[]{}|^"
    ):
        return True
    for index, step in ((start - 1, -1), (end, 1)):
        skipped = 0
        while 0 <= index < len(text) and text[index].isspace():
            skipped += 1
            if skipped > 256:
                return True
            index += step
        if 0 <= index < len(text):
            character = text[index]
            if character in _ORACLE_OPERATOR_CHARACTERS:
                return True
            if character == "?" and _oracle_question_operator(text, index):
                return True
    if (
        _oracle_email_context(text, start, end)
        or (
            _oracle_url_context(text, start, end)
            and not (
                end < len(text)
                and text[end] == "?"
                and (
                    end + 1 == len(text)
                    or text[end + 1].isspace()
                    or text[end + 1] in _ORACLE_HOST_EDGE_TRIM
                )
            )
        )
        or _oracle_identifier_context(text, start, end)
    ):
        return True
    context = _oracle_quote_context(text, start)
    if context is None:
        return False
    frames, uncertain = context
    if uncertain or not frames:
        if uncertain:
            return True
        return bool(
            re.search(
                r"(?:^|[\s(\[{:;,.!?])(?:napis|napisano|napisy|słowo|wyraz|"
                r"forma|termin|przykład|przyklad|pisownia)\s*(?:(?:[:;,!.?]|[-–—])\s*)?$",
                text[:start],
                flags=re.IGNORECASE,
            )
            or _ORACLE_PROPER_NAME_CUE_RE.search(text[max(0, start - 256) : start])
            or (
                text[start:end][:1].isupper()
                and text[start:end][1:].islower()
                and not _oracle_sentence_initial(text, start)
            )
        )
    return any(
        frame.closing_index is None
        or not frame.valid
        or frame.opening == "`"
        or not _ORACLE_DIALOGUE_RE.search(text[: frame.opening_index])
        for frame in frames
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


def _oracle_apply_case(observed: str, replacement: str) -> str:
    if observed.isupper():
        return replacement.upper()
    letters = [character for character in observed if character.isalpha()]
    lower_letters = [character for character in letters if character.islower()]
    if (
        letters
        and sum(character.isupper() for character in letters) > len(lower_letters)
        and lower_letters
        and all(ord(character) > 127 for character in lower_letters)
        and not (observed[:1].isupper() and observed[1:].islower())
    ):
        return replacement.upper()
    if observed[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def scan_closed_literals_multipass(
    text: str, rules: tuple[_CasePatternRule, ...]
) -> dict[object, tuple[Finding, ...]]:
    """Historical per-rule pattern scan used as the F0.3 equivalence oracle."""
    buckets: dict[object, list[Finding]] = {rule.source: [] for rule in rules}
    for rule in rules:
        source_name = str(rule.source)
        typed, corrected, confidence = _ORACLE_LITERAL_SPECS[source_name]
        pattern = re.compile(rf"(?<!\w){re.escape(typed)}(?!\w)", re.IGNORECASE)
        source = Source(SourceKind.RULE, source_name.removeprefix("rule:"))
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()
            is_co_niemiara = source_name == "rule:spelling.co_niemiara"
            if is_co_niemiara:
                if _oracle_co_niemiara_abstains(text, start, end):
                    continue
            else:
                if _oracle_base_abstains(text, start, end):
                    continue
            observed = match.group()
            if is_co_niemiara and not (
                observed.islower()
                or observed.isupper()
                or (observed[:1].isupper() and observed[1:].islower())
            ):
                continue
            candidate = _oracle_apply_case(observed, corrected)
            if candidate == observed:
                continue
            buckets[rule.source].append(
                Finding.create(
                    category=Category.SPELLING,
                    severity=Severity.SUGGESTION,
                    message=f"oracle: {observed}",
                    explanation=f"oracle: {observed} -> {candidate}",
                    original=observed,
                    suggestion=candidate,
                    start=start,
                    end=end,
                    confidence=Confidence(confidence),
                    source=source,
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
