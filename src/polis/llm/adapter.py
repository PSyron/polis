"""Local backend adapter and local transport for the selected runtime."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Protocol, TypedDict, cast

from polis.core import BackendUnavailableError, InvalidBackendResponseError
from polis.core.models import Category
from polis.llm.contracts import (
    LLM_PROMPT_VERSION,
    LLM_RESPONSE_SCHEMA_VERSION,
    build_prompt,
)


class ParsedPromptPayload(TypedDict):
    text: str
    max_findings: int
    allowed_categories: tuple[str, ...]


_PROMPT_OPEN_MARKER: Final[str] = "<INPUT_JSON_START>"
_PROMPT_CLOSE_MARKER: Final[str] = "</INPUT_JSON_END>"
_MAX_PROMPT_CHARS: Final[int] = 25_000
_MAX_RESPONSE_CHARS: Final[int] = 25_000
_DEFAULT_MAX_FINDINGS: Final[int] = 8


@dataclass(frozen=True)
class BackendRequest:
    """Transport-level request data passed to local backends."""

    prompt: str
    text: str


class LocalBackendTransport(Protocol):
    """A local transport boundary for one backend request."""

    def is_available(self) -> bool: ...

    async def request(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class MockHeuristicTransport:
    """Offline deterministic mock transport used as the selected runtime."""

    def is_available(self) -> bool:
        return True

    async def request(self, prompt: str) -> str:
        payload = _parse_prompt_payload(prompt)
        text = payload["text"]
        max_findings = payload["max_findings"]
        allowed_categories = payload["allowed_categories"]

        findings: list[dict[str, object]] = []
        findings.extend(_generate_spelling_findings(text))
        if allowed_categories:
            findings = [
                finding
                for finding in findings
                if finding["category"] in allowed_categories
            ]

        findings = findings[:max_findings]
        response = {
            "schema_version": LLM_RESPONSE_SCHEMA_VERSION,
            "findings": findings,
        }
        return json.dumps(response, ensure_ascii=False)


@dataclass(frozen=True)
class MockHeuristicBackend:
    """Adapter that routes local prompts to a selected mock backend transport."""

    transport: LocalBackendTransport
    name: str = "mock-heu"
    max_prompt_chars: int = _MAX_PROMPT_CHARS
    max_response_chars: int = _MAX_RESPONSE_CHARS
    allowed_categories: frozenset[Category] | None = None
    max_findings: int = _DEFAULT_MAX_FINDINGS

    async def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")
        if not self.transport.is_available():
            raise BackendUnavailableError(
                "local backend is unavailable",
                code="backend_unavailable",
                retryable=True,
                context={"backend": self.name},
            )

        if len(prompt) > self.max_prompt_chars:
            raise InvalidBackendResponseError(
                "prompt exceeds backend request limits",
                code="backend_bad_request",
                retryable=False,
                context={"backend": self.name},
            )

        response = await self.transport.request(prompt)
        if not isinstance(response, str):
            raise InvalidBackendResponseError(
                "backend returned a non-string response",
                code="backend_invalid_response",
                retryable=False,
                context={"backend": self.name},
            )
        if len(response) > self.max_response_chars:
            raise InvalidBackendResponseError(
                "backend response exceeds backend output limits",
                code="backend_bad_response",
                retryable=False,
                context={"backend": self.name},
            )
        return response

    async def build_request(self, text: str) -> BackendRequest:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        prompt = build_prompt(
            text,
            allowed_categories=_sorted_categories(self.allowed_categories),
            max_findings=self.max_findings,
        )
        return BackendRequest(prompt=prompt, text=text)


def _sorted_categories(
    categories: frozenset[Category] | None,
) -> frozenset[Category] | None:
    if categories is None:
        return None
    normalized = sorted(categories, key=lambda item: item.value)
    return frozenset(normalized)


def _parse_prompt_payload(prompt: str) -> ParsedPromptPayload:
    body = prompt.split(f"{_PROMPT_OPEN_MARKER}\n", 1)
    if len(body) != 2:
        raise ValueError("prompt does not contain payload markers")
    payload_block = body[1].split(f"\n{_PROMPT_CLOSE_MARKER}", 1)
    if len(payload_block) != 2:
        raise ValueError("prompt does not contain payload end marker")

    payload: object = json.loads(payload_block[0])
    if not isinstance(payload, dict):
        raise TypeError("payload must be an object")
    payload_dict = cast(dict[str, object], payload)

    required = {
        "prompt_version",
        "response_schema_version",
        "max_findings",
        "allowed_categories",
        "text",
    }
    missing = required - set(payload_dict)
    extra = set(payload_dict) - required
    if missing:
        raise ValueError(f"prompt payload missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"prompt payload has extra fields: {sorted(extra)}")
    if payload_dict["prompt_version"] != LLM_PROMPT_VERSION:
        raise ValueError("prompt version mismatch")
    if payload_dict["response_schema_version"] != LLM_RESPONSE_SCHEMA_VERSION:
        raise ValueError("response schema version mismatch")

    max_findings = _as_int(payload_dict["max_findings"], name="max_findings")
    allowed_categories = _as_allowed_categories(payload_dict["allowed_categories"])
    text = _as_text(payload_dict["text"])
    return {
        "max_findings": max_findings,
        "allowed_categories": allowed_categories,
        "text": text,
    }


def _as_allowed_categories(value: object) -> tuple[str, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise TypeError("allowed_categories must be an array")
    categories = []
    for entry in value:
        if not isinstance(entry, str):
            raise TypeError("allowed_categories entries must be strings")
        categories.append(entry)
    return tuple(categories)


def _as_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("text must be a string")
    return value


def _as_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _generate_spelling_findings(text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    lowered = text.lower()
    for needle, replacement in (
        ("zeby", "że"),
        ("jestes", "jesteś"),
        ("wlasnie", "właśnie"),
    ):
        start = 0
        while True:
            index = lowered.find(needle, start)
            if index == -1:
                break
            end = index + len(needle)
            if text[index:end].lower() == needle:
                findings.append(
                    {
                        "start": index,
                        "end": end,
                        "category": "spelling",
                        "severity": "warning",
                        "message": "Possible spelling issue.",
                        "explanation": f"`{text[index:end]}` is commonly misspelled.",
                        "original": text[index:end],
                        "suggestion": replacement,
                        "confidence": 0.92,
                    }
                )
            start = end
    return findings


def create_default_local_backend() -> MockHeuristicBackend:
    """Create the selected default local backend adapter."""

    return MockHeuristicBackend(transport=MockHeuristicTransport())


__all__ = [
    "BackendRequest",
    "LocalBackendTransport",
    "MockHeuristicBackend",
    "MockHeuristicTransport",
    "create_default_local_backend",
]
