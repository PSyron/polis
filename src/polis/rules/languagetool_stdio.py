"""Persistent local stdio transport for the vendored LanguageTool subset."""

from __future__ import annotations

import json
import math
import os
import queue
import subprocess
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self, cast

_LANGUAGE = "pl-PL"
_MAX_REQUEST_BYTES = 65_536
_MAX_RESPONSE_BYTES = 1_048_576


class LocalLanguageToolStdioSession:
    """Serialize requests through one bounded, lazily started local process."""

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        timeout_seconds: float,
    ) -> None:
        if not command or any(
            not isinstance(item, str) or not item for item in command
        ):
            raise ValueError("LanguageTool stdio command must contain strings")
        self._validate_timeout(timeout_seconds)
        self._command = command
        self._default_timeout_seconds = float(timeout_seconds)
        self._process: subprocess.Popen[bytes] | None = None
        self._responses: queue.Queue[bytes | None] = queue.Queue(maxsize=1)
        self._exchange_lock = threading.Lock()
        self._closed = False
        self._broken = False
        self._next_request_id = 1
        self.process_start_count = 0

    @classmethod
    def from_executable(
        cls,
        executable: Path,
        *,
        timeout_seconds: float,
    ) -> LocalLanguageToolStdioSession:
        """Construct a session for one explicit absolute executable."""

        if not executable.is_absolute():
            raise ValueError("LanguageTool stdio executable must be absolute")
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("LanguageTool stdio path must be an executable file")
        return cls((os.fspath(executable),), timeout_seconds=timeout_seconds)

    @property
    def process_id(self) -> int | None:
        """Return the active child PID for diagnostics, if one exists."""

        process = self._process
        if process is None or process.poll() is not None:
            return None
        return process.pid

    def check(
        self,
        text: str,
        *,
        language: str,
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        """Run one allowlisted LanguageTool check request."""

        if language != _LANGUAGE:
            raise ValueError("LanguageTool stdio language must be pl-PL")
        return self._exchange(
            {"language": _LANGUAGE, "text": text},
            timeout_seconds=timeout_seconds,
        )

    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        """Run one tag-preserving contextual synthesis request."""

        return self._exchange(
            {
                "operation": "synthesize_context",
                "language": _LANGUAGE,
                "text": text,
                "spans": [{"start": start, "end": end} for start, end in spans],
            },
            timeout_seconds=timeout_seconds,
        )

    def close(self) -> None:
        """Stop the owned process; repeated calls are harmless."""

        with self._exchange_lock:
            if self._closed:
                return
            self._closed = True
            self._close_process_gracefully()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # pragma: no cover - interpreter shutdown safety
            pass

    def _exchange(
        self,
        request: Mapping[str, object],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self._validate_timeout(timeout_seconds)
        with self._exchange_lock:
            self._ensure_available()
            request_id = self._next_request_id
            self._next_request_id += 1
            correlated_request = dict(request)
            correlated_request["request_id"] = request_id
            encoded = (
                json.dumps(
                    correlated_request,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            if len(encoded) > _MAX_REQUEST_BYTES:
                raise ValueError("LanguageTool stdio request size exceeds the limit")
            process = self._ensure_started()
            if process.stdin is None:
                self._fail()
                raise OSError("LanguageTool stdio input is unavailable")
            try:
                process.stdin.write(encoded)
                process.stdin.flush()
            except (BrokenPipeError, OSError) as error:
                self._fail()
                raise OSError("LanguageTool stdio process failed") from error

            try:
                raw = self._responses.get(timeout=timeout_seconds)
            except queue.Empty as error:
                self._fail()
                raise TimeoutError("LanguageTool stdio request timed out") from error
            if raw is None:
                self._fail()
                raise OSError("LanguageTool stdio process ended unexpectedly")
            if len(raw) > _MAX_RESPONSE_BYTES:
                self._fail()
                raise ValueError("LanguageTool stdio response exceeds the size limit")
            try:
                payload: Any = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                self._fail()
                raise ValueError("LanguageTool stdio response is invalid") from error
            if not isinstance(payload, dict):
                self._fail()
                raise ValueError("LanguageTool stdio response must be an object")
            response_request_id = payload.pop("request_id", None)
            if (
                isinstance(response_request_id, bool)
                or not isinstance(response_request_id, int)
                or response_request_id != request_id
            ):
                self._fail()
                raise ValueError(
                    "LanguageTool stdio response request identifier is invalid"
                )
            return cast(Mapping[str, object], payload)

    def _ensure_available(self) -> None:
        if self._closed:
            raise RuntimeError("LanguageTool stdio session is closed")
        if self._broken:
            raise OSError("LanguageTool stdio session is broken")

    def _ensure_started(self) -> subprocess.Popen[bytes]:
        process = self._process
        if process is not None:
            if process.poll() is None:
                return process
            self._fail()
            raise OSError("LanguageTool stdio process is unavailable")
        try:
            process = subprocess.Popen(  # noqa: S603
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except OSError as error:
            self._broken = True
            raise OSError("LanguageTool stdio process is unavailable") from error
        self._process = process
        self.process_start_count += 1
        self._responses = queue.Queue(maxsize=1)
        reader = threading.Thread(
            target=self._read_responses,
            args=(process, self._responses),
            name="polis-languagetool-stdio-reader",
            daemon=True,
        )
        reader.start()
        return process

    @staticmethod
    def _read_responses(
        process: subprocess.Popen[bytes],
        responses: queue.Queue[bytes | None],
    ) -> None:
        stdout = process.stdout
        if stdout is None:
            responses.put(None)
            return
        while True:
            try:
                raw = stdout.readline(_MAX_RESPONSE_BYTES + 1)
            except OSError:
                responses.put(None)
                return
            if not raw:
                responses.put(None)
                return
            responses.put(raw)

    def _fail(self) -> None:
        self._broken = True
        self._terminate_process()

    def _terminate_process(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=self._default_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=self._default_timeout_seconds)

    def _close_process_gracefully(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=self._default_timeout_seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=self._default_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=self._default_timeout_seconds)

    @staticmethod
    def _validate_timeout(value: float) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError("LanguageTool stdio timeout must be positive and finite")


__all__ = ["LocalLanguageToolStdioSession"]
