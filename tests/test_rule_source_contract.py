from __future__ import annotations

import re
from pathlib import Path

import pytest

from polis import Analyzer, AnalyzerConfig

ROOT = Path(__file__).resolve().parents[1]
RULE_TABLE_HEADER = re.compile(r"^\|\s*Źródło\s*\|\s*Kategoria\s*\|\s*Zakres\s*\|\s*$")
RULE_TABLE_ROW = re.compile(r"^\|\s*`(rule:[^`|]+)`\s*\|")


def _runtime_source_identifiers() -> frozenset[str]:
    return frozenset(
        identity.source
        for identity in Analyzer(AnalyzerConfig()).source_identity_snapshot
    )


def _documented_source_identifiers(markdown: str) -> frozenset[str]:
    rows = iter(markdown.splitlines())
    for row in rows:
        if RULE_TABLE_HEADER.fullmatch(row.strip()):
            break
    else:
        return frozenset()

    identifiers: set[str] = set()
    for row in rows:
        if not row.strip():
            break
        match = RULE_TABLE_ROW.match(row.strip())
        if match is not None:
            identifiers.add(match.group(1))
    return frozenset(identifiers)


def _assert_source_identifiers_match(
    runtime_identifiers: frozenset[str], documented_identifiers: frozenset[str]
) -> None:
    missing = sorted(documented_identifiers - runtime_identifiers)
    extra = sorted(runtime_identifiers - documented_identifiers)

    assert runtime_identifiers == documented_identifiers, (
        f"missing from runtime: {missing}; extra in runtime: {extra}"
    )


def _maintained_documented_source_identifiers() -> frozenset[str]:
    return _documented_source_identifiers(
        (ROOT / "docs/rules.md").read_text(encoding="utf-8")
    )


def test_runtime_and_documented_source_identifiers_match() -> None:
    _assert_source_identifiers_match(
        _runtime_source_identifiers(), _maintained_documented_source_identifiers()
    )


def test_runtime_source_removal_reports_missing_identifier() -> None:
    runtime_identifiers = _runtime_source_identifiers()
    documented_identifiers = _maintained_documented_source_identifiers()
    removed_identifier = min(documented_identifiers)

    with pytest.raises(
        AssertionError,
        match=re.escape(f"missing from runtime: ['{removed_identifier}']"),
    ):
        _assert_source_identifiers_match(
            runtime_identifiers - {removed_identifier}, documented_identifiers
        )


def test_runtime_source_addition_reports_extra_identifier() -> None:
    runtime_identifiers = _runtime_source_identifiers()
    documented_identifiers = _maintained_documented_source_identifiers()
    extra_identifier = "rule:synthetic.runtime_only"

    with pytest.raises(
        AssertionError,
        match=re.escape(f"extra in runtime: ['{extra_identifier}']"),
    ):
        _assert_source_identifiers_match(
            runtime_identifiers | {extra_identifier}, documented_identifiers
        )


def test_documented_source_removal_reports_extra_identifier() -> None:
    runtime_identifiers = _runtime_source_identifiers()
    documented_identifiers = _maintained_documented_source_identifiers()
    removed_identifier = min(runtime_identifiers)

    with pytest.raises(
        AssertionError,
        match=re.escape(f"extra in runtime: ['{removed_identifier}']"),
    ):
        _assert_source_identifiers_match(
            runtime_identifiers, documented_identifiers - {removed_identifier}
        )


def test_documented_source_addition_reports_missing_identifier() -> None:
    runtime_identifiers = _runtime_source_identifiers()
    documented_identifiers = _maintained_documented_source_identifiers()
    missing_identifier = "rule:synthetic.documented_only"

    with pytest.raises(
        AssertionError,
        match=re.escape(f"missing from runtime: ['{missing_identifier}']"),
    ):
        _assert_source_identifiers_match(
            runtime_identifiers, documented_identifiers | {missing_identifier}
        )


def test_source_identifier_diagnostics_are_sorted_deterministically() -> None:
    runtime_identifiers = frozenset(("rule:runtime.zeta", "rule:runtime.alpha"))
    documented_identifiers = frozenset(
        ("rule:documented.gamma", "rule:documented.beta")
    )

    with pytest.raises(AssertionError) as error:
        _assert_source_identifiers_match(runtime_identifiers, documented_identifiers)

    assert str(error.value).splitlines()[0] == (
        "missing from runtime: ['rule:documented.beta', "
        "'rule:documented.gamma']; extra in runtime: ['rule:runtime.alpha', "
        "'rule:runtime.zeta']"
    )


def test_documented_source_identifier_parser_ignores_prose_whitespace_and_order() -> (
    None
):
    markdown = (
        "Dowolny opis sprzed tabeli.\n\n"
        "  | Źródło | Kategoria | Zakres |\n"
        "  | --- | --- | --- |\n"
        "  | `rule:syntax.zeta` | `syntax` | opis |\n"
        "  |    `rule:agreement.alpha`    | `agreement` | opis |\n\n"
        "Zmieniony opis po tabeli zawiera `rule:ignored.prose`.\n"
    )

    assert _documented_source_identifiers(markdown) == {
        "rule:agreement.alpha",
        "rule:syntax.zeta",
    }
