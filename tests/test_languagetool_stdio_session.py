from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from polis.rules.languagetool_stdio import LocalLanguageToolStdioSession

ROOT = Path(__file__).resolve().parents[1]
FAKE_SERVER = ROOT / "tests" / "fixtures" / "fake_languagetool_stdio.py"


@pytest.fixture
def fake_command() -> tuple[str, ...]:
    return (sys.executable, str(FAKE_SERVER))


def test_session_starts_lazily_and_reuses_one_process(
    fake_command: tuple[str, ...],
) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0)
    assert session.process_start_count == 0

    first = session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)
    second = session.check("Wiem że wróci.", language="pl-PL", timeout_seconds=1.0)

    assert session.process_start_count == 1
    assert first["process_id"] == second["process_id"]
    assert second["request_sequence"] == first["request_sequence"] + 1
    session.close()


def test_session_serves_context_synthesis(fake_command: tuple[str, ...]) -> None:
    with LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0) as session:
        payload = session.synthesize_context(
            "Paweł",
            spans=((0, 5),),
            timeout_seconds=1.0,
        )

    assert payload["operation"] == "synthesize_context"
    assert payload["results"][0]["surface"] == "Paweł"


def test_session_serializes_concurrent_requests(fake_command: tuple[str, ...]) -> None:
    with LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0) as session:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(
                    session.check,
                    f"Zdanie {index}.",
                    language="pl-PL",
                    timeout_seconds=1.0,
                )
                for index in range(8)
            ]
        payloads = [future.result() for future in futures]

    assert session.process_start_count == 1
    assert sorted(payload["request_sequence"] for payload in payloads) == list(
        range(1, 9)
    )
    assert len({payload["process_id"] for payload in payloads}) == 1


@pytest.mark.parametrize(
    ("text", "error"),
    (
        ("__invalid_json__", ValueError),
        ("__array__", ValueError),
        ("__oversized__", ValueError),
        ("__exit__", OSError),
    ),
)
def test_invalid_response_breaks_session_without_leaking_payload(
    fake_command: tuple[str, ...],
    text: str,
    error: type[Exception],
) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0)

    with pytest.raises(error) as captured:
        session.check(text, language="pl-PL", timeout_seconds=1.0)

    assert text not in str(captured.value)
    with pytest.raises(OSError, match="broken"):
        session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)
    session.close()


def test_timeout_terminates_and_breaks_session(fake_command: tuple[str, ...]) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=0.05)

    with pytest.raises(TimeoutError, match="timed out"):
        session.check("__timeout__", language="pl-PL", timeout_seconds=0.05)

    assert session.process_id is None
    with pytest.raises(OSError, match="broken"):
        session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)
    session.close()


def test_unsolicited_extra_response_cannot_satisfy_the_next_request(
    fake_command: tuple[str, ...],
) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0)

    session.check(
        "__double_response__",
        language="pl-PL",
        timeout_seconds=1.0,
    )
    with pytest.raises(ValueError, match="request identifier"):
        session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)

    with pytest.raises(OSError, match="broken"):
        session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)
    session.close()


def test_session_rejects_invalid_requests_before_start(
    fake_command: tuple[str, ...],
) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0)

    with pytest.raises(ValueError, match="pl-PL"):
        session.check("Tekst.", language="en-US", timeout_seconds=1.0)
    with pytest.raises(ValueError, match="request size"):
        session.check("x" * 70_000, language="pl-PL", timeout_seconds=1.0)

    assert session.process_start_count == 0
    session.close()


def test_close_is_idempotent_and_prevents_reuse(fake_command: tuple[str, ...]) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0)
    session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)

    session.close()
    session.close()

    assert session.process_id is None
    with pytest.raises(RuntimeError, match="closed"):
        session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)


def test_executable_factory_validates_local_path(tmp_path: Path) -> None:
    relative = Path("run_stdio.sh")
    with pytest.raises(ValueError, match="absolute"):
        LocalLanguageToolStdioSession.from_executable(relative, timeout_seconds=1.0)

    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="executable"):
        LocalLanguageToolStdioSession.from_executable(missing, timeout_seconds=1.0)
