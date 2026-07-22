from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from typing import cast
from urllib.request import ProxyHandler, Request

import pytest

import polis.rules.languagetool as languagetool_module
from polis import AnalysisOptions, AnalysisResult, Category
from polis.rules.languagetool import (
    LanguageToolRuleConfig,
    LocalLanguageToolRule,
    LoopbackLanguageToolHttpTransport,
)


def _response(
    *,
    text_offset: int = 0,
    text_length: int = 7,
    rule_id: str = "BRAK_PRZECINKA_ZE",
    replacement: str = "Wiem, że",
    version: str = "6.8",
) -> dict[str, object]:
    return {
        "software": {"name": "LanguageTool", "version": version},
        "matches": [
            {
                "offset": text_offset,
                "length": text_length,
                "replacements": [{"value": replacement}],
                "rule": {"id": rule_id},
            }
        ],
    }


class FakeTransport:
    def __init__(self, responses: list[Mapping[str, object] | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def check(
        self, text: str, *, language: str, timeout_seconds: float
    ) -> Mapping[str, object]:
        self.calls.append(text)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert language == "pl-PL"
        assert timeout_seconds == 1.0
        return response


def _rule(transport: FakeTransport) -> LocalLanguageToolRule:
    return LocalLanguageToolRule(
        LanguageToolRuleConfig("http://127.0.0.1:8081"), transport
    )


def test_rule_allowlist_contains_exactly_qualified_identifiers() -> None:
    assert languagetool_module._ALLOWLIST == {
        "BRAK_PRZECINKA_KTORY",
        "BRAK_PRZECINKA_SPOJNIK_PROSTY",
        "BRAK_PRZECINKA_ZE",
        "BRAK_PRZECINKA_ZEBY",
        "WOLACZ_BEZ_PRZECINKA",
    }


@pytest.mark.parametrize(
    "rule_id",
    [
        "BRAK_PRZECINKA_KTORY",
        "BRAK_PRZECINKA_SPOJNIK_PROSTY",
        "BRAK_PRZECINKA_ZE",
        "WOLACZ_BEZ_PRZECINKA",
    ],
)
def test_rule_maps_each_qualified_identifier_to_a_comma_finding(
    rule_id: str,
) -> None:
    transport = FakeTransport(
        [
            _response(text_length=0, replacement=""),
            _response(rule_id=rule_id),
        ]
    )

    findings = _rule(transport).find("Wiem że wróciła.", options=AnalysisOptions())

    assert len(findings) == 1
    assert (findings[0].start, findings[0].end, findings[0].suggestion) == (4, 4, ",")


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8081",
        "http://localhost:8081",
        "http://example.test:8081",
        "http://127.0.0.1",
        "http://user@127.0.0.1:8081",
        "http://127.0.0.1:8081/v2",
        "http://127.0.0.1:8081/",
        "http://127.0.0.1:8081?x=1",
    ],
)
def test_config_rejects_every_nonliteral_loopback_endpoint(url: str) -> None:
    with pytest.raises(ValueError, match="LanguageTool"):
        LanguageToolRuleConfig(url)


def test_rule_normalizes_allowlisted_wide_replacement_to_comma_insertion() -> None:
    transport = FakeTransport([_response(text_length=0, replacement=""), _response()])

    findings = _rule(transport).find("Wiem że wróciła.", options=AnalysisOptions())

    assert transport.calls == ["To jest test.", "Wiem że wróciła."]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category is Category.PUNCTUATION
    assert (finding.start, finding.end, finding.original, finding.suggestion) == (
        4,
        4,
        "",
        ",",
    )
    assert finding.confidence.value == 0.85
    assert str(finding.source) == "rule:languagetool.pl"


@pytest.mark.parametrize(
    ("text", "payload", "expected_edits", "expected_output"),
    (
        (
            "Helena która mieszka obok przyniosła ciasto.",
            _response(
                text_length=len("Helena która"),
                rule_id="BRAK_PRZECINKA_KTORY",
                replacement="Helena, która",
            ),
            ((6, 6, ","), (25, 25, ",")),
            "Helena, która mieszka obok, przyniosła ciasto.",
        ),
        (
            "Leno proszę zamknij okno.",
            _response(
                text_offset=4,
                text_length=len(" proszę"),
                rule_id="WOLACZ_BEZ_PRZECINKA",
                replacement=", proszę",
            ),
            ((4, 4, ","), (11, 11, ",")),
            "Leno, proszę, zamknij okno.",
        ),
    ),
)
def test_rule_completes_reviewed_paired_comma_corrections(
    text: str,
    payload: Mapping[str, object],
    expected_edits: tuple[tuple[int, int, str], ...],
    expected_output: str,
) -> None:
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find(text, options=AnalysisOptions())

    assert (
        tuple((finding.start, finding.end, finding.suggestion) for finding in findings)
        == expected_edits
    )
    assert {str(finding.source) for finding in findings} == {"rule:languagetool.pl"}
    result = AnalysisResult(text, findings)
    assert result.apply(tuple(finding.id for finding in findings)) == expected_output


def test_rule_deduplicates_repeated_opening_without_orphaning_closing_comma() -> None:
    text = "Helena która mieszka obok przyniosła ciasto."
    response = _response(
        text_length=len("Helena która"),
        rule_id="BRAK_PRZECINKA_KTORY",
        replacement="Helena, która",
    )
    matches = response["matches"]
    assert isinstance(matches, list)
    match = matches[0]
    payload = {
        "software": {"name": "LanguageTool", "version": "6.8"},
        "matches": [match, match],
    }
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find(text, options=AnalysisOptions())

    assert [(finding.start, finding.end) for finding in findings] == [
        (6, 6),
        (25, 25),
    ]
    result = AnalysisResult(text, findings)
    assert result.apply(tuple(item.id for item in findings)) == (
        "Helena, która mieszka obok, przyniosła ciasto."
    )


def test_rule_deduplicates_same_opening_from_different_allowlisted_rules() -> None:
    text = "Helena która mieszka obok przyniosła ciasto."
    response = _response(
        text_length=len("Helena która"),
        rule_id="BRAK_PRZECINKA_KTORY",
        replacement="Helena, która",
    )
    matches = response["matches"]
    assert isinstance(matches, list)
    duplicate = dict(matches[0])
    duplicate["rule"] = {"id": "BRAK_PRZECINKA_ZE"}
    payload = {
        "software": {"name": "LanguageTool", "version": "6.8"},
        "matches": [matches[0], duplicate],
    }
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find(text, options=AnalysisOptions())

    assert [(finding.start, finding.end) for finding in findings] == [
        (6, 6),
        (25, 25),
    ]


def test_rule_deduplicates_existing_finding_at_synthesized_closing_boundary() -> None:
    text = "Helena która mieszka obok przyniosła ciasto."
    response = _response(
        text_length=len("Helena która"),
        rule_id="BRAK_PRZECINKA_KTORY",
        replacement="Helena, która",
    )
    matches = response["matches"]
    assert isinstance(matches, list)
    closing = {
        "offset": 25,
        "length": 0,
        "replacements": [{"value": ","}],
        "rule": {"id": "BRAK_PRZECINKA_ZE"},
    }
    payload = {
        "software": {"name": "LanguageTool", "version": "6.8"},
        "matches": [matches[0], closing],
    }
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find(text, options=AnalysisOptions())

    assert [(finding.start, finding.end) for finding in findings] == [
        (6, 6),
        (25, 25),
    ]


def test_rule_drops_complete_pair_when_one_boundary_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "Helena która mieszka obok przyniosła ciasto."
    response = _response(
        text_length=len("Helena która"),
        rule_id="BRAK_PRZECINKA_KTORY",
        replacement="Helena, która",
    )
    matches = response["matches"]
    assert isinstance(matches, list)
    opening = matches[0]
    competing = {
        "offset": 0,
        "length": 0,
        "replacements": [{"value": ","}],
        "rule": {"id": "BRAK_PRZECINKA_ZE"},
    }
    payload = {
        "software": {"name": "LanguageTool", "version": "6.8"},
        "matches": [opening, competing],
    }
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])
    monkeypatch.setattr(
        languagetool_module,
        "findings_conflict",
        lambda first, second: {first.start, second.start} == {0, 6},
    )

    assert _rule(transport).find(text, options=AnalysisOptions()) == ()


@pytest.mark.parametrize(
    "text",
    (
        "Helena, która mieszka obok, przyniosła ciasto.",
        "Leno, proszę, zamknij okno.",
        "Maria, która mieszka w Krakowie, jutro przyjedzie.",
        "Liczba 12,5 i adres https://example.org pozostają bez zmian.",
        "Powiedziała: „Leno, proszę, zamknij okno”.",
    ),
)
def test_rule_does_not_synthesize_paired_commas_without_qualified_match(
    text: str,
) -> None:
    transport = FakeTransport(
        [
            _response(text_length=0, replacement=""),
            {"software": {"name": "LanguageTool", "version": "6.8"}, "matches": []},
        ]
    )

    assert _rule(transport).find(text, options=AnalysisOptions()) == ()


@pytest.mark.parametrize(
    ("text", "payload", "expected_opening"),
    (
        (
            "Helena która pracuje obok przyniosła ciasto.",
            _response(
                text_length=len("Helena która"),
                rule_id="BRAK_PRZECINKA_KTORY",
                replacement="Helena, która",
            ),
            6,
        ),
        (
            "Helena która mieszka obok i pracuje zdalnie.",
            _response(
                text_length=len("Helena która"),
                rule_id="BRAK_PRZECINKA_KTORY",
                replacement="Helena, która",
            ),
            6,
        ),
        (
            "Helena która mieszka obok przynosi ciasto.",
            _response(
                text_length=len("Helena która"),
                rule_id="BRAK_PRZECINKA_KTORY",
                replacement="Helena, która",
            ),
            6,
        ),
        (
            "Leno proszę o zamknięcie okna.",
            _response(
                text_offset=4,
                text_length=len(" proszę"),
                rule_id="WOLACZ_BEZ_PRZECINKA",
                replacement=", proszę",
            ),
            4,
        ),
        (
            "Leno proszę pana o ciszę.",
            _response(
                text_offset=4,
                text_length=len(" proszę"),
                rule_id="WOLACZ_BEZ_PRZECINKA",
                replacement=", proszę",
            ),
            4,
        ),
    ),
)
def test_rule_abstains_from_unreviewed_paired_comma_shapes(
    text: str, payload: Mapping[str, object], expected_opening: int
) -> None:
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find(text, options=AnalysisOptions())

    assert [(finding.start, finding.end) for finding in findings] == [
        (expected_opening, expected_opening)
    ]


def test_rule_completes_previously_reviewed_vocative_shape() -> None:
    text = "Anno proszę zadzwoń wieczorem."
    payload = _response(
        text_offset=4,
        text_length=len(" proszę"),
        rule_id="WOLACZ_BEZ_PRZECINKA",
        replacement=", proszę",
    )
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find(text, options=AnalysisOptions())

    assert [(finding.start, finding.end) for finding in findings] == [
        (4, 4),
        (11, 11),
    ]


def test_rule_converts_utf16_offsets_after_emoji() -> None:
    transport = FakeTransport(
        [
            _response(text_length=0, replacement=""),
            _response(text_offset=3, text_length=7),
        ]
    )

    findings = _rule(transport).find("😀 Wiem że wróciła.", options=AnalysisOptions())

    assert (findings[0].start, findings[0].end) == (6, 6)


@pytest.mark.parametrize(
    "payload",
    [
        _response(rule_id="UNKNOWN"),
        _response(replacement="Wiem; że"),
        {"software": {"name": "LanguageTool", "version": "6.8"}, "matches": []},
    ],
)
def test_rule_drops_unallowlisted_or_noncomma_matches(
    payload: Mapping[str, object],
) -> None:
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    assert _rule(transport).find("Wiem że wróciła.", options=AnalysisOptions()) == ()


def test_rule_is_filtered_by_requested_categories() -> None:
    transport = FakeTransport([_response(text_length=0, replacement=""), _response()])

    findings = _rule(transport).find(
        "Wiem że wróciła.", options=AnalysisOptions(categories={"spelling"})
    )

    assert findings == ()
    assert transport.calls == []


@pytest.mark.parametrize("failure", [OSError("down"), TimeoutError("late")])
def test_expected_transport_failure_returns_no_optional_findings(
    failure: Exception,
) -> None:
    transport = FakeTransport([failure])

    assert _rule(transport).find("Wiem że wróciła.", options=AnalysisOptions()) == ()


def test_wrong_preflight_version_sends_no_user_text() -> None:
    transport = FakeTransport([_response(version="6.9")])

    assert _rule(transport).find("PRYWATNY TEKST", options=AnalysisOptions()) == ()
    assert transport.calls == ["To jest test."]


def test_successful_preflight_is_reused_but_every_result_is_verified() -> None:
    transport = FakeTransport(
        [
            _response(text_length=0, replacement=""),
            _response(),
            _response(),
        ]
    )
    rule = _rule(transport)

    assert len(rule.find("Wiem że wróciła.", options=AnalysisOptions())) == 1
    assert len(rule.find("Wiem że wróciła.", options=AnalysisOptions())) == 1
    assert transport.calls == [
        "To jest test.",
        "Wiem że wróciła.",
        "Wiem że wróciła.",
    ]


class _HttpResponse:
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self) -> _HttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.body


class _HttpOpener:
    def __init__(self, response: _HttpResponse) -> None:
        self.response = response
        self.request: Request | None = None
        self.timeout: float | None = None

    def open(self, request: Request, *, timeout: float) -> _HttpResponse:
        self.request = request
        self.timeout = timeout
        return self.response


def test_http_transport_posts_only_polish_form_to_fixed_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _HttpResponse(
        b'{"software":{"name":"LanguageTool","version":"6.8"},"matches":[]}'
    )
    opener = _HttpOpener(response)
    monkeypatch.setattr(
        languagetool_module, "_no_proxy_no_redirect_opener", lambda: opener
    )
    config = LanguageToolRuleConfig("http://127.0.0.1:8081", 0.5)

    payload = LoopbackLanguageToolHttpTransport(config).check(
        "Poufny tekst.", language="pl-PL", timeout_seconds=0.5
    )

    request = cast(Request, opener.request)
    assert request.full_url == "http://127.0.0.1:8081/v2/check"
    assert request.data == b"language=pl-PL&text=Poufny+tekst."
    assert request.get_method() == "POST"
    assert opener.timeout == 0.5
    assert payload["matches"] == []


def test_http_transport_rejects_wrong_content_type_and_large_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = LanguageToolRuleConfig("http://127.0.0.1:8081")
    transport = LoopbackLanguageToolHttpTransport(config)
    wrong_type = _HttpOpener(_HttpResponse(b"{}", "text/plain"))
    monkeypatch.setattr(
        languagetool_module, "_no_proxy_no_redirect_opener", lambda: wrong_type
    )
    with pytest.raises(ValueError, match="application/json"):
        transport.check("Tekst.", language="pl-PL", timeout_seconds=1.0)

    oversized = _HttpOpener(_HttpResponse(b"x" * 1_048_577))
    monkeypatch.setattr(
        languagetool_module, "_no_proxy_no_redirect_opener", lambda: oversized
    )
    with pytest.raises(ValueError, match="size limit"):
        transport.check("Tekst.", language="pl-PL", timeout_seconds=1.0)


def test_http_opener_has_no_proxy_and_rejects_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []
    sentinel = object()

    def fake_build_opener(*handlers: object) -> object:
        captured.extend(handlers)
        return sentinel

    monkeypatch.setattr(languagetool_module, "build_opener", fake_build_opener)
    assert languagetool_module._no_proxy_no_redirect_opener() is sentinel

    proxy_handler = next(
        handler for handler in captured if isinstance(handler, ProxyHandler)
    )
    redirect_handler = next(
        handler
        for handler in captured
        if isinstance(handler, languagetool_module._RejectRedirects)
    )

    assert vars(proxy_handler).get("proxies") == {}
    assert (
        redirect_handler.redirect_request(
            Request("http://127.0.0.1:8081/v2/check"),
            object(),
            302,
            "Found",
            object(),
            "http://example.test/",
        )
        is None
    )


def test_identical_allowlisted_findings_are_deduplicated_across_rule_ids() -> None:
    payload = _response()
    matches = payload["matches"]
    assert isinstance(matches, list)
    matches.append(
        {
            "offset": 0,
            "length": 7,
            "replacements": [{"value": "Wiem, że"}],
            "rule": {"id": "BRAK_PRZECINKA_ZEBY"},
        }
    )
    transport = FakeTransport([_response(text_length=0, replacement=""), payload])

    findings = _rule(transport).find("Wiem że wróciła.", options=AnalysisOptions())

    assert [(finding.start, finding.end) for finding in findings] == [(4, 4)]
