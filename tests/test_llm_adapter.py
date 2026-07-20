from __future__ import annotations

import asyncio

import pytest

from polis.core import (
    BackendUnavailableError,
    InvalidBackendResponseError,
    LocalGenerationBackend,
)
from polis.core.models import Category
from polis.llm import (
    BackendRequest,
    MockHeuristicBackend,
    MockHeuristicTransport,
    create_default_local_backend,
)


class FakeTransport:
    def __init__(self, response: str, available: bool = True) -> None:
        self.response = response
        self.available = available
        self.requested_prompt: str | None = None

    def is_available(self) -> bool:
        return self.available

    async def request(self, prompt: str) -> str:
        self.requested_prompt = prompt
        return self.response


def test_default_backend_uses_the_mock_runtime() -> None:
    backend = create_default_local_backend()

    assert backend.name == "mock-heu"
    assert isinstance(backend, LocalGenerationBackend)
    assert isinstance(backend.transport, MockHeuristicTransport)


def test_build_request_marks_allowed_categories_and_limits() -> None:
    backend = MockHeuristicBackend(
        transport=MockHeuristicTransport(),
        allowed_categories=frozenset((Category.SPELLING, Category.AGREEMENT)),
        max_findings=2,
    )
    request = asyncio.run(backend.build_request("To jestes i zeby."))

    assert isinstance(request, BackendRequest)
    assert request.text == "To jestes i zeby."
    assert "<INPUT_JSON_START>" in request.prompt
    assert '"max_findings":2' in request.prompt
    assert '"spelling"' in request.prompt
    assert '"agreement"' in request.prompt


def test_generate_passes_prompt_and_captures_response() -> None:
    transport = FakeTransport('{"schema_version": 1, "findings": []}')
    backend = MockHeuristicBackend(transport=transport)

    payload = asyncio.run(backend.generate('{"input":"To jest test"}'))

    assert payload == '{"schema_version": 1, "findings": []}'
    assert transport.requested_prompt is not None


def test_generate_raises_when_backend_unavailable() -> None:
    transport = FakeTransport('{"schema_version":1,"findings": []}', available=False)
    backend = MockHeuristicBackend(transport=transport)

    with pytest.raises(BackendUnavailableError):
        asyncio.run(backend.generate('{"input":"abc"}'))


def test_generate_validates_response_bound() -> None:
    transport = FakeTransport("x" * 40_000)
    backend = MockHeuristicBackend(transport=transport, max_response_chars=10)

    with pytest.raises(InvalidBackendResponseError):
        asyncio.run(backend.generate('{"input":"abc"}'))


def test_mock_transport_generates_deterministic_local_response() -> None:
    transport = MockHeuristicTransport()
    backend = MockHeuristicBackend(transport=transport, max_findings=2)
    request = asyncio.run(backend.build_request("Zeby zeby zeby. To jestes."))
    response = asyncio.run(backend.generate(request.prompt))
    assert "schema_version" in response
    assert "jestes" in request.text


@pytest.mark.model
def test_local_smoke_default_backend_generates_structured_findings() -> None:
    backend = create_default_local_backend()
    request = asyncio.run(backend.build_request("Mam zeby."))
    response = asyncio.run(backend.generate(request.prompt))
    assert "schema_version" in response
    assert '"zeby"' in response
