from __future__ import annotations

import asyncio

import pytest

from polis.core import (
    AnalysisTimeoutError,
    BackendUnavailableError,
    InvalidBackendResponseError,
    LocalGenerationBackend,
)
from polis.core.models import Category
from polis.llm import (
    BackendRequest,
    BackendRetryPolicy,
    MockHeuristicBackend,
    MockHeuristicTransport,
    create_default_local_backend,
)


class FakeTransport:
    def __init__(
        self,
        responses: list[str] | str,
        availabilities: list[bool] | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._responses = (
            list(responses) if isinstance(responses, list) else [responses]
        )
        self._availabilities = availabilities
        self._availability_calls = 0
        self.delay_seconds = delay_seconds
        self.request_calls = 0
        self.requested_prompt: str | None = None

    def is_available(self) -> bool:
        if self._availabilities is None:
            return True
        index = min(self._availability_calls, len(self._availabilities) - 1)
        self._availability_calls += 1
        return self._availabilities[index]

    async def request(self, prompt: str) -> str:
        self.request_calls += 1
        self.requested_prompt = prompt
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        response = self._responses[0]
        if len(self._responses) > 1:
            self._responses = self._responses[1:]
        return response


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
    transport = FakeTransport(
        '{"schema_version":1,"findings": []}',
        availabilities=[False],
    )
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
    assert "zeby" in response


@pytest.mark.model
def test_local_smoke_default_backend_generates_structured_findings() -> None:
    backend = create_default_local_backend()
    findings = asyncio.run(
        backend.generate_findings(
            "Mam zeby.",
            policy=BackendRetryPolicy(max_attempts=1, retry_delays=(0.0,)),
        )
    )
    assert findings


def test_generate_findings_retries_on_transient_unavailability() -> None:
    transport = FakeTransport(
        responses=["{bad json"],
        availabilities=[False, False, True],
    )
    backend = MockHeuristicBackend(
        transport=transport,
        max_findings=1,
    )
    policy = BackendRetryPolicy(max_attempts=3, retry_delays=(0.0, 0.0, 0.0))

    with pytest.raises(InvalidBackendResponseError):
        asyncio.run(
            backend.generate_findings(
                "zeby",
                policy=policy,
            )
        )
    assert transport.request_calls == 1
    assert transport._availability_calls >= 3


def test_generate_findings_retries_success_after_one_unavailable_attempt() -> None:
    transport = FakeTransport(
        responses=['{"schema_version": 1, "findings": []}'],
        availabilities=[False, True],
    )
    backend = MockHeuristicBackend(transport=transport)
    policy = BackendRetryPolicy(max_attempts=2, retry_delays=(0.0, 0.0))

    findings = asyncio.run(backend.generate_findings("zeby", policy=policy))

    assert findings == ()
    assert transport._availability_calls == 2


def test_generate_findings_exhausts_retry_budget_with_transient_unavailability() -> (
    None
):
    transport = FakeTransport(
        responses=['{"schema_version": 1, "findings": []}'],
        availabilities=[False, False, False],
    )
    backend = MockHeuristicBackend(transport=transport)
    policy = BackendRetryPolicy(max_attempts=2, retry_delays=(0.0, 0.0))

    with pytest.raises(BackendUnavailableError):
        asyncio.run(backend.generate_findings("zeby", policy=policy))

    assert transport._availability_calls == 2


def test_generate_findings_uses_deterministic_backoff_delays() -> None:
    transport = FakeTransport(
        responses=['{"schema_version": 1, "findings": []}'],
        availabilities=[False, False, True],
    )
    backend = MockHeuristicBackend(transport=transport)
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    policy = BackendRetryPolicy(
        max_attempts=3,
        retry_delays=(0.2, 0.4, 0.6),
    )

    asyncio.run(backend.generate_findings("zeby", policy=policy, sleep=fake_sleep))
    assert delays == [0.2, 0.4]


def test_generate_findings_timeout_maps_to_contract_exception() -> None:
    transport = FakeTransport(
        responses=['{"schema_version": 1, "findings": []}'],
        delay_seconds=0.2,
    )
    backend = MockHeuristicBackend(transport=transport)

    with pytest.raises(AnalysisTimeoutError) as info:
        asyncio.run(
            backend.generate_findings(
                "zeby",
                policy=BackendRetryPolicy(
                    max_attempts=1,
                    timeout_seconds=0.01,
                    retry_delays=(0.0,),
                ),
            )
        )
    assert info.value.code == "analysis.timeout"


def test_generate_findings_reports_invalid_json_and_schema_without_text() -> None:
    transport = FakeTransport(
        responses=[
            "{bad json",
            '{"schema_version": 1, "findings": [{"start": 0}]}',
        ],
        availabilities=[True, True],
    )
    backend = MockHeuristicBackend(transport=transport)
    secret = "szyfr sekretny: zeby"

    with pytest.raises(InvalidBackendResponseError) as info:
        asyncio.run(
            backend.generate_findings(
                secret,
                policy=BackendRetryPolicy(
                    max_attempts=1,
                    retry_delays=(0.0,),
                ),
            )
        )

    assert info.value.code == "backend.invalid_response"
    assert "secret" not in str(info.value)
    assert "zeby" not in str(info.value.context)


def test_generate_findings_reports_schema_error_on_missing_fields() -> None:
    transport = FakeTransport(
        responses=[
            '{"schema_version": 1, "findings": [{"start": 0, "end": 4}]}',
        ]
    )
    backend = MockHeuristicBackend(transport=transport)

    with pytest.raises(InvalidBackendResponseError) as info:
        asyncio.run(
            backend.generate_findings(
                "zeby",
                policy=BackendRetryPolicy(max_attempts=1, retry_delays=(0.0,)),
            )
        )
    assert info.value.code == "backend.invalid_response"
