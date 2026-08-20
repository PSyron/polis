from __future__ import annotations

import _socket
import hashlib
import importlib
import json
import multiprocessing
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from scripts import spelling_provider_qualification as qualification
from scripts.morphology_provider_json import ContractError, canonical_bytes
from scripts.prepare_spelling_provider_frequency import main as prepare_frequency
from scripts.spelling_provider_qualification import _evaluate, _quality, load_dataset

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "tests/fixtures/v1/spelling_provider_qualification.json"
MANIFEST = DATASET.with_suffix(".manifest.json")
REPORT = ROOT / "docs/spelling-provider-qualification-v1.json"
REPRODUCTION = ROOT / "docs/spelling-provider-qualification-reproduction-v1.json"


def test_issue_388_publishes_reproducible_qualification_artifacts() -> None:
    for artifact in (DATASET, MANIFEST, REPORT, REPRODUCTION):
        assert artifact.is_file(), f"missing qualification artifact: {artifact}"


def test_dataset_spans_are_exact_unicode_half_open_ranges() -> None:
    dataset = load_dataset(DATASET, MANIFEST)

    assert len(dataset.cases) == 25
    assert all(case.text[case.start : case.end] for case in dataset.cases)
    assert {case.guard for case in dataset.cases} == {
        "natural_language",
        "url",
        "email",
        "literal",
        "technical",
        "numeral",
        "mixed_language",
    }


def test_corpus_covers_issue_388_error_and_guard_classes() -> None:
    dataset = load_dataset(DATASET, MANIFEST)

    assert {
        "transposition",
        "insertion",
        "substitution",
        "truncated_form",
        "missing_diacritic",
        "valid_inflection",
        "proper_name",
        "acronym",
        "url",
        "email",
        "literal",
        "technical_token",
        "numeral",
        "mixed_language",
        "ambiguous_diacritic",
        "ambiguous_suggestions",
    } <= {case.category for case in dataset.cases}
    ambiguous = next(
        case for case in dataset.cases if case.category == "ambiguous_suggestions"
    )
    assert ambiguous.expected_candidates == ("rzad", "rząd")


def test_guarded_tokens_never_reach_candidate_provider() -> None:
    class RecordingProvider:
        def __init__(self) -> None:
            self.tokens: list[str] = []

        def known(self, token: str) -> bool:
            self.tokens.append(token)
            return False

        def suggest(self, token: str, limit: int) -> tuple[str, ...]:
            del limit
            self.tokens.append(token)
            return ()

    dataset = load_dataset(DATASET, MANIFEST)
    provider = RecordingProvider()
    outcomes, durations = _evaluate(dataset, provider, limit=5)

    assert len(provider.tokens) == 32
    assert len(durations) == 16
    guarded = {case.id for case in dataset.cases if case.guard != "natural_language"}
    assert all(
        outcome.status == "guarded"
        for outcome in outcomes
        if outcome.case_id in guarded
    )


def test_quality_does_not_count_clean_abstentions_as_false_alarms() -> None:
    class AbstainingProvider:
        def known(self, token: str) -> bool:
            del token
            return False

        def suggest(self, token: str, limit: int) -> tuple[str, ...]:
            del token, limit
            return ()

    dataset = load_dataset(DATASET, MANIFEST)
    outcomes, _ = _evaluate(dataset, AbstainingProvider(), limit=5)

    quality = _quality(dataset, outcomes)

    assert quality["false_alarm_cases"] == 0
    assert quality["false_alarm_case_ids"] == []


def test_runner_rejects_non_public_fixture_before_provider_load(
    tmp_path: Path,
) -> None:
    arguments = [
        "--provider",
        "symspellpy",
        "--dataset",
        str(tmp_path / "dataset.json"),
        "--manifest",
        str(MANIFEST),
        "--output",
        str(tmp_path / "report.json"),
        "--package-artifact",
        str(tmp_path / "package.whl"),
        "--data-file",
        str(tmp_path / "frequency.txt"),
        "--frequency-file",
        str(tmp_path / "frequency.txt"),
        "--data-id",
        "unused",
        "--data-license",
        "unused",
        "--data-license-status",
        "unused",
        "--data-source",
        "unused",
        "--data-source-sha256",
        "0" * 64,
        "--expected-package-version",
        "unused",
        "--package-license",
        "unused",
        "--package-license-status",
        "unused",
    ]

    with pytest.raises(ContractError, match="committed public fixture"):
        qualification.run(arguments)


def test_runner_rejects_output_overwriting_public_fixture(tmp_path: Path) -> None:
    arguments = [
        "--provider",
        "symspellpy",
        "--dataset",
        str(DATASET),
        "--manifest",
        str(MANIFEST),
        "--output",
        str(DATASET),
        "--package-artifact",
        str(tmp_path / "package.whl"),
        "--data-file",
        str(tmp_path / "frequency.txt"),
        "--frequency-file",
        str(tmp_path / "frequency.txt"),
        "--data-id",
        "unused",
        "--data-license",
        "unused",
        "--data-license-status",
        "unused",
        "--data-source",
        "unused",
        "--data-source-sha256",
        "0" * 64,
        "--expected-package-version",
        "unused",
        "--package-license",
        "unused",
        "--package-license-status",
        "unused",
    ]

    with pytest.raises(ContractError, match="must not overwrite"):
        qualification.run(arguments)


def test_offline_guard_blocks_sendmsg_and_restores_socket_methods(
    tmp_path: Path,
) -> None:
    original_connect = socket.socket.connect
    original_sendmsg = socket.socket.sendmsg
    socket_spec = socket.__spec__
    assert socket_spec is not None
    original_loader = socket_spec.loader

    with qualification._offline_only():
        pair = socket.socketpair()
        try:
            with socket.socket() as sock:
                with pytest.raises(OSError, match="network access is disabled"):
                    sock.connect(("127.0.0.1", 9))
                with pytest.raises(OSError, match="network access is disabled"):
                    sock.sendmsg([])
                raw_sock = _socket.socket()
                try:
                    with pytest.raises(OSError, match="network access is disabled"):
                        raw_sock.connect(("127.0.0.1", 9))
                finally:
                    raw_sock.close()
                with pytest.raises(OSError, match="writing to sockets is disabled"):
                    os.write(pair[0].fileno(), b"blocked")
                with pytest.raises(OSError, match="writing to sockets is disabled"):
                    os.fdopen(pair[0].fileno(), "wb", closefd=False)
                if hasattr(os, "sendfile"):
                    payload = tmp_path / "payload.bin"
                    payload.write_bytes(b"blocked")
                    with payload.open("rb") as handle:
                        with pytest.raises(
                            OSError, match="writing to sockets is disabled"
                        ):
                            os.sendfile(
                                pair[0].fileno(),
                                handle.fileno(),
                                0,
                                payload.stat().st_size,
                            )
                if hasattr(os, "splice"):
                    read_fd, write_fd = os.pipe()
                    try:
                        with pytest.raises(
                            OSError, match="writing to sockets is disabled"
                        ):
                            os.splice(read_fd, pair[0].fileno(), 1)
                    finally:
                        os.close(read_fd)
                        os.close(write_fd)
        finally:
            pair[0].close()
            pair[1].close()
        assert socket_spec.loader is not original_loader
        assert socket_spec.loader is not None
        with pytest.raises(OSError, match="reloading socket is disabled"):
            socket_spec.loader.exec_module(socket)

    assert socket.socket.connect is original_connect
    assert socket.socket.sendmsg is original_sendmsg
    assert socket_spec.loader is original_loader


def test_offline_guard_blocks_process_creation_and_restores_subprocess() -> None:
    original_popen = subprocess.Popen
    original_process = multiprocessing.Process

    with qualification._offline_only():
        with pytest.raises(OSError, match="network access is disabled"):
            subprocess.Popen(["definitely-not-started"])
        with pytest.raises(OSError, match="network access is disabled"):
            multiprocessing.get_context("spawn").Process()

    assert subprocess.Popen is original_popen
    assert multiprocessing.Process is original_process


def test_offline_guard_preserves_contract_errors() -> None:
    with pytest.raises(ContractError, match="qualification drift"):
        with qualification._offline_only():
            raise ContractError("qualification drift")


def test_provider_import_boundary_rejects_cached_foreign_modules(
    tmp_path: Path,
) -> None:
    foreign = ModuleType("foreign_provider_dependency")
    foreign.__file__ = str(tmp_path / "foreign.py")
    sys.modules[foreign.__name__] = foreign
    try:
        with pytest.raises(ContractError, match="verified (runtime closure|wheel)"):
            with qualification._provider_import_boundary(
                "spylls", tmp_path, frozenset()
            ):
                importlib.import_module(foreign.__name__)
    finally:
        del sys.modules[foreign.__name__]


def test_manifest_rejects_dataset_hash_drift(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["canonical_sha256"] = "0" * 64
    changed = tmp_path / MANIFEST.name
    changed.write_text(json.dumps(manifest))

    with pytest.raises(ContractError, match="canonical hash mismatch"):
        load_dataset(DATASET, changed)


def test_frequency_preparation_is_digest_pinned_and_deterministic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "frequency.txt"
    source.write_text(
        "word,wordLen,urlcount,totalcount,adjFreq,deleted,whyDeleted,Rank,corrected,english\n"
        "Chmura,6,1,7,7,0,,1,,0\n"
        "123,3,1,2,2,1,Number,2,,0\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    assert (
        prepare_frequency(
            [
                "--input",
                str(source),
                "--output",
                str(output),
                "--expected-input-sha256",
                digest,
            ]
        )
        == 0
    )
    assert output.read_text() == "chmura 7\n"

    wrong_output = tmp_path / "wrong.txt"
    assert (
        prepare_frequency(
            [
                "--input",
                str(source),
                "--output",
                str(wrong_output),
                "--expected-input-sha256",
                "0" * 64,
            ]
        )
        == 2
    )
    assert not wrong_output.exists()


def test_recorded_report_contains_baseline_metrics_without_analyzed_text() -> None:
    report = json.loads(REPORT.read_text())

    assert report["decision"]["verdict"] == "NO_PROVIDER_QUALIFIED"
    assert report["protocol"]["thresholds_precommitted"] is False
    assert report["providers"]["spylls"]["quality"] == {
        "ambiguous_diacritic_abstentions": 1,
        "ambiguous_diacritic_cases": 1,
        "ambiguous_suggestion_abstentions": 0,
        "ambiguous_suggestion_cases": 1,
        "candidate_detection_rate": 1.0,
        "candidate_recall": 1.0,
        "correction_cases": 10,
        "false_alarm_case_ids": ["negative_ambiguous_suggestions"],
        "false_alarm_cases": 1,
        "false_alarm_rate": 1 / 6,
        "guarded_cases": 9,
        "guarded_provider_calls": 0,
        "negative_cases": 6,
        "top1_exactness": 1.0,
    }
    assert report["providers"]["symspellpy"]["quality"]["candidate_recall"] == 0.7
    assert report["providers"]["symspellpy"]["quality"]["top1_exactness"] == 0.7
    assert report["providers"]["symspellpy"]["quality"]["false_alarm_rate"] == 4 / 6
    assert (
        report["providers"]["symspellpy"]["quality"]["ambiguous_suggestion_cases"] == 1
    )
    assert report["protocol"]["case_counts"] == {
        "total": 25,
        "natural_language": 16,
        "correction": 10,
        "negative": 6,
        "guarded": 9,
    }
    assert report["protocol"]["platform_constraints"]["supported_platforms"] == [
        "darwin",
        "linux",
    ]
    assert report["providers"]["spylls"]["performance"]["measured_queries"] == 80
    assert (
        report["providers"]["spylls"]["performance"]["throughput_cases_per_second"]
        > 1.0
    )
    assert (
        report["providers"]["symspellpy"]["performance"]["throughput_cases_per_second"]
        > 30_000
    )
    assert '"text"' not in REPORT.read_text()


def test_report_digest_excludes_machine_and_timing_variation() -> None:
    report = json.loads(REPORT.read_text())
    providers = {
        name: {
            key: provider[key]
            for key in ("identity", "artifacts", "quality", "reproducibility")
        }
        for name, provider in report["providers"].items()
    }
    included = {
        key: report[key]
        for key in ("schema_id", "schema_version", "dataset", "protocol")
    }
    included["providers"] = providers
    included["decision"] = report["decision"]

    assert (
        report["normalized_digest"]
        == hashlib.sha256(canonical_bytes(included)).hexdigest()
    )


def test_reproduction_records_two_stable_runs_per_provider() -> None:
    reproduction = json.loads(REPRODUCTION.read_text())
    runs = reproduction["runs"]

    assert reproduction["normalized_digest_match"] is True
    assert reproduction["runtime_dependencies_changed"] is False
    assert [run["exit_code"] for run in runs] == [0, 0, 0, 0]
    assert len({run["normalized_digest"] for run in runs[:2]}) == 1
    assert len({run["normalized_digest"] for run in runs[2:]}) == 1
    assert all(run["result_repetitions_stable"] for run in runs)
