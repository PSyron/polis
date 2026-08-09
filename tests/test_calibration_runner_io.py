from __future__ import annotations

import importlib.util
import inspect
import json
import os
import socket
import stat
import tempfile
from pathlib import Path
from typing import Literal, NoReturn, assert_never

import pytest
from tests.calibration_runner_test_helpers import (
    RecordingAnalyzer,
    RecordingFactory,
    SyntheticAnalyzerError,
    output_paths,
    synthetic_run_inputs,
    write_workspace,
)
from tests.calibration_test_helpers import canonical_bytes, synthetic_manifest

from polis.core import Finding
from polis.evaluation.calibration_models import CalibrationContractError
from polis.evaluation.calibration_sources import SOURCE_ROWS

if importlib.util.find_spec("polis.evaluation.calibration_runner") is None:

    def test_planned_calibration_file_runner_is_available() -> None:
        pytest.fail("planned calibration runner module is absent")


else:
    import polis.evaluation.calibration_runner_io as runner_io
    from polis.evaluation.calibration_models import (
        CalibrationIntegrityError,
        CalibrationOutputError,
    )
    from polis.evaluation.calibration_runner import (
        _run_calibration_for_test,
        run_calibration,
    )

    def test_public_runner_exposes_only_the_canonical_config_path() -> None:
        assert tuple(inspect.signature(run_calibration).parameters) == ("config_path",)

    def test_public_runner_rejects_alias_before_any_file_read(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        reads: list[Path] = []
        monkeypatch.chdir(tmp_path)

        def forbidden_read(path: Path) -> bytes:
            reads.append(path)
            raise SyntheticAnalyzerError("unexpected file read")

        monkeypatch.setattr(Path, "read_bytes", forbidden_read)

        with pytest.raises(CalibrationContractError):
            run_calibration(Path("copied.json"))

        assert reads == []

    def test_io_module_has_no_public_factory_override() -> None:
        assert not hasattr(runner_io, "run_calibration_files")

    @pytest.fixture(autouse=True)
    def _stable_runner_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(runner_io, "validate_live_sources", lambda: SOURCE_ROWS)

    @pytest.mark.parametrize("boundary", ["config", "manifest", "denominator"])
    def test_file_admission_failure_never_constructs_analyzer(
        tmp_path: Path,
        boundary: str,
    ) -> None:
        config_path = write_workspace(tmp_path)
        if boundary == "config":
            config_path.write_bytes(b"{}\n")
        elif boundary == "manifest":
            manifest_path = config_path.parent / "calibration.dataset.manifest.json"
            manifest_path.write_bytes(b"{}\n")
        else:
            dataset_path = tmp_path / ".omo/sealed/a-b-calibration-v2-v1/cases.json"
            raw = json.loads(dataset_path.read_bytes())
            first = raw["cases"][0]
            first["id"] = "correct-00-extra"
            first["role"] = "correct"
            first["expected_findings"] = []
            dataset_bytes = canonical_bytes(raw)
            dataset_path.write_bytes(dataset_bytes)
            manifest_bytes = canonical_bytes(synthetic_manifest(dataset_bytes))
            (config_path.parent / "calibration.dataset.manifest.json").write_bytes(
                manifest_bytes
            )
        _, _, _, findings = synthetic_run_inputs()
        factory = RecordingFactory(RecordingAnalyzer(findings))

        with pytest.raises(CalibrationContractError):
            _run_calibration_for_test(config_path, factory, tmp_path)

        assert factory.calls == 0
        assert all(not path.exists() for path in output_paths(tmp_path))

    def test_source_drift_fails_before_factory(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = write_workspace(tmp_path)
        _, _, _, findings = synthetic_run_inputs()
        factory = RecordingFactory(RecordingAnalyzer(findings))

        def drift() -> NoReturn:
            raise CalibrationContractError("synthetic source drift")

        monkeypatch.setattr(runner_io, "validate_live_sources", drift)

        with pytest.raises(CalibrationContractError, match="synthetic source drift"):
            _run_calibration_for_test(config_path, factory, tmp_path)

        assert factory.calls == 0

    def test_execution_failure_creates_no_partial_outputs(
        tmp_path: Path,
    ) -> None:
        config_path = write_workspace(tmp_path)
        _, _, _, findings = synthetic_run_inputs()
        factory = RecordingFactory(RecordingAnalyzer(findings, failure_call=1201))

        with pytest.raises(SyntheticAnalyzerError):
            _run_calibration_for_test(config_path, factory, tmp_path)

        assert all(not path.exists() for path in output_paths(tmp_path))

    @pytest.mark.parametrize(
        "socket_api",
        (
            "connect",
            "connect_ex",
            "create_connection",
            "send",
            "sendall",
            "sendto",
            "sendmsg",
            "sendfile",
        ),
    )
    def test_runner_owned_offline_boundary_blocks_a_real_socket_attempt(
        tmp_path: Path,
        socket_api: Literal[
            "connect",
            "connect_ex",
            "create_connection",
            "send",
            "sendall",
            "sendto",
            "sendmsg",
            "sendfile",
        ],
    ) -> None:
        config_path = write_workspace(tmp_path)

        class SocketAnalyzer:
            def __call__(self, text: str) -> tuple[Finding, ...]:
                match socket_api:
                    case "connect":
                        with socket.socket(
                            socket.AF_UNIX, socket.SOCK_STREAM
                        ) as client:
                            client.connect("absent.sock")
                    case "connect_ex":
                        with socket.socket(
                            socket.AF_UNIX, socket.SOCK_STREAM
                        ) as client:
                            client.connect_ex("absent.sock")
                    case "create_connection":
                        with socket.create_connection(("127.0.0.1", 0)):
                            pass
                    case "send" | "sendall" | "sendmsg" | "sendfile":
                        client, peer = socket.socketpair()
                        with client, peer, tempfile.TemporaryFile() as payload:
                            if socket_api == "send":
                                client.send(b"synthetic")
                            elif socket_api == "sendall":
                                client.sendall(b"synthetic")
                            elif socket_api == "sendmsg":
                                client.sendmsg([b"synthetic"])
                            else:
                                client.sendfile(payload)
                    case "sendto":
                        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
                            client.sendto(b"synthetic", "absent.sock")
                    case unreachable:
                        assert_never(unreachable)
                raise SyntheticAnalyzerError("socket operation escaped offline guard")

        factory = RecordingFactory(SocketAnalyzer())

        with pytest.raises(
            CalibrationIntegrityError, match="calibration network access is forbidden"
        ):
            _run_calibration_for_test(config_path, factory, tmp_path)

        assert factory.calls == 1
        assert all(not path.exists() for path in output_paths(tmp_path))

    def test_fifth_repetition_drift_creates_no_outputs(tmp_path: Path) -> None:
        config_path = write_workspace(tmp_path)
        _, _, _, findings = synthetic_run_inputs()
        factory = RecordingFactory(RecordingAnalyzer(findings, drift_call=6001))

        with pytest.raises(CalibrationIntegrityError):
            _run_calibration_for_test(config_path, factory, tmp_path)

        assert all(not path.exists() for path in output_paths(tmp_path))

    def test_reports_are_exclusive_and_file_and_parent_are_fsynced(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = write_workspace(tmp_path)
        _, _, _, findings = synthetic_run_inputs()
        factory = RecordingFactory(RecordingAnalyzer(findings))
        modes: list[int] = []
        real_fsync = os.fsync

        def observe_fsync(descriptor: int) -> None:
            modes.append(os.fstat(descriptor).st_mode)
            real_fsync(descriptor)

        monkeypatch.setattr(os, "fsync", observe_fsync)

        assert _run_calibration_for_test(config_path, factory, tmp_path) == 0
        assert sum(stat.S_ISREG(mode) for mode in modes) == 3
        assert sum(stat.S_ISDIR(mode) for mode in modes) == 3
        assert all(path.exists() for path in output_paths(tmp_path))
        assert all(
            "Błąd🙂".encode() not in path.read_bytes()
            for path in output_paths(tmp_path)
        )

        second = RecordingFactory(RecordingAnalyzer(findings))
        with pytest.raises(CalibrationOutputError):
            _run_calibration_for_test(config_path, second, tmp_path)
        assert second.calls == 0
