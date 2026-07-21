"""Optional, allowlisted local LanguageTool 6.8 punctuation rule."""

from __future__ import annotations

import ipaddress
import json
import math
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast
from urllib.parse import urlencode, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    OpenerDirector,
    ProxyHandler,
    Request,
    build_opener,
)

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
from polis.correction import findings_conflict

_EXPECTED_NAME = "LanguageTool"
_EXPECTED_VERSION = "6.8"
_LANGUAGE = "pl-PL"
_PROBE_TEXT = "To jest test."
_MAX_RESPONSE_BYTES = 1_048_576
_ALLOWLIST = frozenset({"BRAK_PRZECINKA_ZE", "BRAK_PRZECINKA_ZEBY"})
_SOURCE = Source(SourceKind.RULE, "languagetool.pl")


class LanguageToolTransport(Protocol):
    def check(
        self, text: str, *, language: str, timeout_seconds: float
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class LanguageToolRuleConfig:
    base_url: str
    timeout_seconds: float = 1.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http":
            raise ValueError("LanguageTool endpoint must use plain loopback HTTP")
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError as error:
            raise ValueError(
                "LanguageTool endpoint must use a numeric loopback address"
            ) from error
        if not address.is_loopback:
            raise ValueError("LanguageTool endpoint must use a loopback address")
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError(
                "LanguageTool endpoint must contain a valid port"
            ) from error
        if port is None:
            raise ValueError("LanguageTool endpoint must contain an explicit port")
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.path != ""
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("LanguageTool endpoint must not contain extra URL parts")
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, (int, float)
        ):
            raise ValueError("LanguageTool timeout must be a positive finite number")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("LanguageTool timeout must be a positive finite number")


@dataclass(frozen=True, slots=True)
class LoopbackLanguageToolHttpTransport:
    config: LanguageToolRuleConfig

    def check(
        self, text: str, *, language: str, timeout_seconds: float
    ) -> Mapping[str, object]:
        if language != _LANGUAGE:
            raise ValueError("LanguageTool language must be pl-PL")
        body = urlencode({"language": language, "text": text}).encode("utf-8")
        request = Request(
            f"{self.config.base_url.rstrip('/')}/v2/check",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with _no_proxy_no_redirect_opener().open(
            request, timeout=timeout_seconds
        ) as response:  # noqa: S310
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise ValueError("LanguageTool response must use application/json")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ValueError("LanguageTool response exceeds the size limit")
        payload: Any = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("LanguageTool response must be an object")
        return cast(Mapping[str, object], payload)


@dataclass(frozen=True, slots=True)
class LocalLanguageToolRule:
    config: LanguageToolRuleConfig
    transport: LanguageToolTransport
    source: Source = _SOURCE
    _preflight_complete: bool = field(
        default=False, init=False, repr=False, compare=False
    )
    _preflight_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False
    )

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if (
            options.categories is not None
            and Category.PUNCTUATION not in options.categories
        ):
            return ()
        try:
            self._ensure_preflight()
            payload = self.transport.check(
                text,
                language=_LANGUAGE,
                timeout_seconds=self.config.timeout_seconds,
            )
            _require_compatible_server(payload)
            findings = _parse_allowlisted_findings(text, payload)
            return _drop_conflicting_findings(findings)
        except (OSError, TimeoutError, UnicodeError, ValueError, json.JSONDecodeError):
            return ()

    def _ensure_preflight(self) -> None:
        if self._preflight_complete:
            return
        with self._preflight_lock:
            if self._preflight_complete:
                return
            probe = self.transport.check(
                _PROBE_TEXT,
                language=_LANGUAGE,
                timeout_seconds=self.config.timeout_seconds,
            )
            _require_compatible_server(probe)
            object.__setattr__(self, "_preflight_complete", True)


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


def _no_proxy_no_redirect_opener() -> OpenerDirector:
    return build_opener(ProxyHandler({}), _RejectRedirects())


def _require_compatible_server(payload: Mapping[str, object]) -> None:
    software = payload.get("software")
    if not isinstance(software, dict):
        raise ValueError("LanguageTool response lacks software metadata")
    if (
        software.get("name") != _EXPECTED_NAME
        or software.get("version") != _EXPECTED_VERSION
    ):
        raise ValueError("LanguageTool server identity or version is unsupported")


def _parse_allowlisted_findings(
    text: str, payload: Mapping[str, object]
) -> tuple[Finding, ...]:
    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        raise ValueError("LanguageTool response must contain a matches list")
    findings: list[Finding] = []
    for raw_match in raw_matches:
        if not isinstance(raw_match, dict):
            raise ValueError("LanguageTool match must be an object")
        rule = raw_match.get("rule")
        if not isinstance(rule, dict) or rule.get("id") not in _ALLOWLIST:
            continue
        offset = _integer(raw_match.get("offset"), "offset")
        length = _integer(raw_match.get("length"), "length")
        start = _utf16_offset_to_codepoint(text, offset)
        end = _utf16_offset_to_codepoint(text, offset + length)
        original = text[start:end]
        replacements = raw_match.get("replacements")
        if not isinstance(replacements, list):
            raise ValueError("LanguageTool replacements must be a list")
        normalized: set[tuple[int, int, str, str]] = set()
        for replacement in replacements:
            if not isinstance(replacement, dict) or not isinstance(
                replacement.get("value"), str
            ):
                raise ValueError("LanguageTool replacement must contain text")
            edit = _minimal_edit(start, original, replacement["value"])
            if edit is not None:
                normalized.add(edit)
        if len(normalized) != 1:
            continue
        edit_start, edit_end, edit_original, suggestion = normalized.pop()
        if edit_start != edit_end or edit_original != "" or suggestion != ",":
            continue
        findings.append(
            Finding.create(
                category=Category.PUNCTUATION,
                severity=Severity.SUGGESTION,
                message="Brak przecinka przed spójnikiem podrzędnym.",
                explanation="Reguła wskazuje bezpieczną minimalną wstawkę przecinka.",
                original="",
                suggestion=",",
                start=edit_start,
                end=edit_end,
                confidence=Confidence(0.85),
                source=_SOURCE,
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.start, item.end, item.id)))


def _minimal_edit(
    start: int, original: str, replacement: str
) -> tuple[int, int, str, str] | None:
    prefix = 0
    while (
        prefix < len(original)
        and prefix < len(replacement)
        and original[prefix] == replacement[prefix]
    ):
        prefix += 1
    original_tail = len(original)
    replacement_tail = len(replacement)
    while (
        original_tail > prefix
        and replacement_tail > prefix
        and original[original_tail - 1] == replacement[replacement_tail - 1]
    ):
        original_tail -= 1
        replacement_tail -= 1
    old = original[prefix:original_tail]
    new = replacement[prefix:replacement_tail]
    if old == new:
        return None
    return start + prefix, start + original_tail, old, new


def _drop_conflicting_findings(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    return tuple(
        finding
        for index, finding in enumerate(findings)
        if not any(
            findings_conflict(finding, other)
            for other_index, other in enumerate(findings)
            if other_index != index
        )
    )


def _utf16_offset_to_codepoint(text: str, offset: int) -> int:
    units = 0
    for index, character in enumerate(text):
        if units == offset:
            return index
        width = 2 if ord(character) > 0xFFFF else 1
        if units < offset < units + width:
            raise ValueError("LanguageTool offset splits a surrogate pair")
        units += width
    if units == offset:
        return len(text)
    raise ValueError("LanguageTool offset is outside the input")


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"LanguageTool {label} must be a non-negative integer")
    return value


__all__ = [
    "LanguageToolRuleConfig",
    "LanguageToolTransport",
    "LocalLanguageToolRule",
    "LoopbackLanguageToolHttpTransport",
]
