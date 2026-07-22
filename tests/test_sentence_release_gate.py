from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from experiments.sentence_release_gate import gate
from experiments.sentence_release_gate import run_evaluation as release

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "sentence_release_gate"
CONFIG = EXPERIMENT / "config.json"
CORPUS_JSON = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)
CORPUS_XML = CORPUS_JSON.with_suffix(".xml")
REPORT = EXPERIMENT / "report.json"


def test_gate_configuration_is_closed_sentence_only_and_pins_runtime() -> None:
    config = gate.load_gate_config(CONFIG)

    assert config.sentence_only is True
    assert config.source_policy_version == "1.1"
    assert config.corpus_sha256 == gate.sha256_path(CORPUS_JSON)
    assert config.corpus_xml_sha256 == gate.sha256_path(CORPUS_XML)
    assert config.gates.required_model_calls == 0
    assert config.gates.maximum_socket_count == 0
    assert config.automatic_sources
    assert config.reviewable_sources
    assert config.automatic_sources.isdisjoint(config.reviewable_sources)


def test_development_loader_never_materializes_holdout_text() -> None:
    seen: list[str] = []

    cases = gate.load_development_sentences(CORPUS_XML, on_materialized=seen.append)

    assert len(cases) == 69
    assert seen == [case.case_id for case in cases]
    assert all(case.split == "development" for case in cases)
    assert all(case.unit == "sentence" for case in cases)


def test_holdout_loader_requires_preexisting_valid_marker(tmp_path: Path) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen = tmp_path / "frozen.json"
    gate.freeze_gate(inputs, frozen)
    with pytest.raises(ValueError, match="reserved"):
        gate.load_reserved_holdout_sentences(
            CORPUS_JSON, tmp_path / "missing", frozen, inputs
        )


def test_holdout_loader_rejects_fabricated_marker(tmp_path: Path) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    gate.freeze_gate(inputs, frozen)
    marker.write_text(json.dumps({"fake": "a" * 64}), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        gate.load_reserved_holdout_sentences(CORPUS_JSON, marker, frozen, inputs)


def test_exact_scorer_ignores_reported_category_and_source() -> None:
    gold = gate.GoldEdit("punctuation", 4, 4, "", ",")
    actual = gate.ObservedEdit(4, 4, "", ",", "syntax", "rule:other", "finding_x")

    counts = gate.score_exact_edits((gold,), (actual,))

    assert counts == gate.EditCounts(
        true_positive=1,
        false_positive=0,
        false_negative=0,
    )


def _finding(
    *,
    start: int = 4,
    end: int = 4,
    original: str = "",
    suggestion: str = ",",
    source: str = "rule:languagetool.pl",
) -> dict[str, Any]:
    return {
        "id": "finding_" + "a" * 32,
        "category": "punctuation",
        "severity": "error",
        "original": original,
        "suggestion": suggestion,
        "start": start,
        "end": end,
        "confidence": 0.99,
        "source": source,
    }


def _response(*, finding: dict[str, Any] | None = None) -> dict[str, Any]:
    automatic = [] if finding is None else [finding]
    return {
        "schema_version": 1,
        "request_id": 1,
        "status": "complete",
        "analysis_findings": automatic,
        "automatic_findings": automatic,
        "reviewable_findings": [],
        "corrected_text": "Wiem, że.",
        "selected_text": "Wiem, że.",
        "selected_finding_ids": [],
        "suggestion_outcomes": [],
        "elapsed_ms": 1.0,
        "python_rss_bytes": 10,
        "child_rss_bytes": 20,
        "combined_rss_bytes": 30,
        "python_peak_rss_bytes": 10,
        "child_peak_rss_bytes": 20,
        "combined_peak_rss_bytes": 30,
        "model_calls": 0,
        "process_start_count": 1,
    }


def test_response_rejects_original_or_reconstruction_mismatch() -> None:
    with pytest.raises(ValueError, match="original"):
        gate.validate_runner_response(
            "Wiem że.", _response(finding=_finding(original="X"))
        )

    wrong = _response(finding=_finding())
    wrong["corrected_text"] = "Wiem że."
    with pytest.raises(ValueError, match="reconstruct"):
        gate.validate_runner_response("Wiem że.", wrong)


def test_response_rejects_same_id_with_different_payload() -> None:
    response = _response(finding=_finding())
    response["analysis_findings"] = [_finding(suggestion=";")]

    with pytest.raises(ValueError, match="identical to analyze"):
        gate.validate_runner_response("Wiem że.", response)


def _passing_split_report() -> dict[str, Any]:
    return {
        "automatic": {
            "proposed_edits": 1,
            "true_positive_edits": 1,
            "false_positive_edits": 0,
            "false_negative_edits": 0,
            "precision": 1.0,
            "recall": 1.0,
            "correction_accuracy": 1.0,
        },
        "reviewable": {
            "proposed_edits": 1,
            "true_positive_edits": 1,
            "false_positive_edits": 0,
            "false_negative_edits": 0,
            "precision": 1.0,
            "recall": 1.0,
            "correction_accuracy": 1.0,
        },
        "structured_outcome_validity": 1.0,
        "protected_automatic_changes": 0,
        "protected_reviewable_findings": 0,
        "performance": {
            "cold_e2e_ms": 3.0,
            "warm_in_process_p50_ms": 1.0,
            "warm_in_process_p95_ms": 1.0,
            "warm_e2e_p50_ms": 2.0,
            "warm_e2e_p95_ms": 2.0,
            "cases_per_second": 10.0,
            "characters_per_second": 100.0,
            "python_loaded_rss_bytes": 10,
            "child_loaded_rss_bytes": 20,
            "combined_loaded_rss_bytes": 30,
            "python_peak_rss_bytes": 10,
            "child_peak_rss_bytes": 20,
            "combined_peak_rss_bytes": 30,
            "swap_delta_bytes": 0,
            "socket_count": 0,
            "model_calls": 0,
            "process_start_count": 1,
            "stable_repetitions": 2,
        },
    }


def test_zero_proposal_channel_fails_non_vacuous_gate() -> None:
    config = gate.load_gate_config(CONFIG)
    report = _passing_split_report()

    assert gate.gate_qualifies(report, config)
    cast_reviewable = report["reviewable"]
    cast_reviewable["proposed_edits"] = 0
    assert not gate.gate_qualifies(report, config)


@pytest.mark.parametrize("process_start_count", (0, 2))
def test_gate_rejects_unmeasured_or_restarted_language_tool_process(
    process_start_count: int,
) -> None:
    config = gate.load_gate_config(CONFIG)
    report = _passing_split_report()
    report["performance"]["process_start_count"] = process_start_count

    assert not gate.gate_qualifies(report, config)


def test_report_rejects_text_and_private_paths() -> None:
    safe = {"case_evidence": [{"case_id": "syntax_001", "edit_hash": "a" * 64}]}

    assert gate.validate_privacy_safe_report(safe) == safe
    with pytest.raises(ValueError, match="raw analyzed text"):
        gate.validate_privacy_safe_report({"suggestion": "tajne"})
    with pytest.raises(ValueError, match="private path"):
        gate.validate_privacy_safe_report({"runner": "/Users/name/project"})


def _freeze_inputs(tmp_path: Path) -> gate.FreezeInputs:
    config = tmp_path / "config.json"
    evaluator = tmp_path / "evaluator.py"
    wheel = tmp_path / "polis.whl"
    sdist = tmp_path / "polis.tar.gz"
    dependencies = tmp_path / "dependencies"
    dependencies.mkdir(exist_ok=True)
    config.write_bytes(CONFIG.read_bytes())
    evaluator.write_text("evaluator", encoding="utf-8")
    wheel.write_text("wheel", encoding="utf-8")
    sdist.write_text("sdist", encoding="utf-8")
    (dependencies / "runtime.jar").write_text("runtime", encoding="utf-8")
    return gate.FreezeInputs(
        files={
            "configuration": config,
            "evaluator": evaluator,
            "wheel": wheel,
            "sdist": sdist,
        },
        directories={"dependencies": dependencies},
    )


def test_freeze_detects_every_executable_input_mutation(tmp_path: Path) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    frozen = gate.freeze_gate(inputs, frozen_path)
    assert gate.verify_frozen_gate(frozen_path, inputs) == frozen

    inputs.files["evaluator"].write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        gate.verify_frozen_gate(frozen_path, inputs)


def test_reservation_is_one_shot_and_bound_to_frozen_inputs(tmp_path: Path) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    frozen = gate.freeze_gate(inputs, frozen_path)

    gate.reserve_holdout_once(frozen_path, marker, inputs)

    assert json.loads(marker.read_text(encoding="utf-8")) == frozen.as_dict()
    with pytest.raises(FileExistsError, match="already reserved"):
        gate.reserve_holdout_once(frozen_path, marker, inputs)


def test_holdout_rejects_forged_qualified_report_before_reservation(
    tmp_path: Path,
) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    forged = {"development": {"decision": {"qualified": True}}}
    gate.freeze_gate(inputs, frozen_path, development_report=forged)

    with pytest.raises(ValueError, match="development report schema"):
        release.authorize_holdout(
            prior_report=forged,
            config=gate.load_gate_config(CONFIG),
            frozen_path=frozen_path,
            marker_path=marker,
            inputs=inputs,
        )

    assert not marker.exists()


def test_holdout_recomputes_gate_before_reservation(tmp_path: Path) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    config = gate.load_gate_config(CONFIG)
    report = _qualifying_development_report(config, inputs)
    report["development"]["performance"]["process_start_count"] = 0
    report["development"]["decision"] = {"qualified": True}
    gate.freeze_gate(inputs, frozen_path, development_report=report)

    with pytest.raises(ValueError, match="did not qualify"):
        release.authorize_holdout(
            prior_report=report,
            config=config,
            frozen_path=frozen_path,
            marker_path=marker,
            inputs=inputs,
        )

    assert not marker.exists()


def test_holdout_reservation_is_bound_to_exact_development_report(
    tmp_path: Path,
) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    config = gate.load_gate_config(CONFIG)
    report = _qualifying_development_report(config, inputs)
    gate.freeze_gate(inputs, frozen_path, development_report=report)
    mutated = json.loads(json.dumps(report))
    mutated["development"]["total_cases"] = 2

    with pytest.raises(ValueError, match="report hash mismatch"):
        release.authorize_holdout(
            prior_report=mutated,
            config=config,
            frozen_path=frozen_path,
            marker_path=marker,
            inputs=inputs,
        )
    assert not marker.exists()

    release.authorize_holdout(
        prior_report=report,
        config=config,
        frozen_path=frozen_path,
        marker_path=marker,
        inputs=inputs,
    )
    assert marker.exists()


def test_platform_preflight_failure_prevents_reservation_and_holdout_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    config = gate.load_gate_config(CONFIG)
    report = _qualifying_development_report(config, inputs)
    gate.freeze_gate(inputs, frozen_path, development_report=report)
    loaded = False

    def fail_preflight() -> None:
        raise RuntimeError("sandbox capability probe failed")

    def record_load(*_args: object, **_kwargs: object) -> tuple[gate.SentenceCase, ...]:
        nonlocal loaded
        loaded = True
        return ()

    monkeypatch.setattr(release, "preflight_release_capabilities", fail_preflight)
    monkeypatch.setattr(release, "load_reserved_holdout_sentences", record_load)

    with pytest.raises(RuntimeError, match="sandbox capability probe failed"):
        release.authorize_and_load_holdout(
            prior_report=report,
            config=config,
            frozen_path=frozen_path,
            marker_path=marker,
            inputs=inputs,
            corpus_path=CORPUS_JSON,
        )

    assert not marker.exists()
    assert loaded is False


def test_socket_audit_error_is_not_reported_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "experiments.sentence_release_gate.run_evaluation.shutil.which",
        lambda _name: "/usr/sbin/lsof",
    )

    def fake_run(command: tuple[str, ...], **_kwargs: object) -> object:
        if command[0] == "ps":
            return subprocess.CompletedProcess(command, 0, "123 0\n", "")
        return subprocess.CompletedProcess(command, 1, "", "permission denied")

    monkeypatch.setattr(
        "experiments.sentence_release_gate.run_evaluation.subprocess.run",
        fake_run,
    )

    with pytest.raises(RuntimeError, match="socket audit failed"):
        release._socket_count_tree(123)


def test_invisible_probe_socket_prevents_holdout_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    config = gate.load_gate_config(CONFIG)
    report = _qualifying_development_report(config, inputs)
    gate.freeze_gate(inputs, frozen_path, development_report=report)
    loaded = False

    class ProbeSocket:
        def __enter__(self) -> ProbeSocket:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def bind(self, _address: tuple[str, int]) -> None:
            return None

        def listen(self, _backlog: int) -> None:
            return None

    monkeypatch.setattr(release, "release_platform_profile", lambda: "test-profile")
    monkeypatch.setattr(
        "experiments.sentence_release_gate.run_evaluation.socket.socket",
        ProbeSocket,
    )
    monkeypatch.setattr(release, "_sandbox_capability_probe", lambda: None)
    monkeypatch.setattr(release, "_swap_used_bytes", lambda: 0)
    monkeypatch.setattr(release, "_resource_tree_snapshot", lambda _pid: (1, 0))
    monkeypatch.setattr(release, "_socket_count_tree", lambda _pid: 0)

    def record_load(*_args: object, **_kwargs: object) -> tuple[gate.SentenceCase, ...]:
        nonlocal loaded
        loaded = True
        return ()

    monkeypatch.setattr(release, "load_reserved_holdout_sentences", record_load)

    with pytest.raises(RuntimeError, match="socket visibility preflight failed"):
        release.authorize_and_load_holdout(
            prior_report=report,
            config=config,
            frozen_path=frozen_path,
            marker_path=marker,
            inputs=inputs,
            corpus_path=CORPUS_JSON,
        )

    assert not marker.exists()
    assert loaded is False


def test_installed_setup_failure_precedes_holdout_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _freeze_inputs(tmp_path)
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    config = gate.load_gate_config(CONFIG)
    report = _qualifying_development_report(config, inputs)
    gate.freeze_gate(inputs, frozen_path, development_report=report)
    loaded = False

    def fail_install(*_args: object, **_kwargs: object) -> Path:
        raise RuntimeError("installed setup failed")

    def record_authorize(**_kwargs: object) -> tuple[gate.SentenceCase, ...]:
        nonlocal loaded
        loaded = True
        return ()

    monkeypatch.setattr(release, "install_artifact_offline", fail_install)
    monkeypatch.setattr(release, "authorize_and_load_holdout", record_authorize)

    with pytest.raises(RuntimeError, match="installed setup failed"):
        release.run_prepared_split(
            cases=None,
            prior_report=report,
            config=config,
            freeze_inputs=inputs,
            frozen_path=frozen_path,
            marker_path=marker,
            corpus_path=CORPUS_JSON,
            wheel=inputs.files["wheel"],
            sdist=inputs.files["sdist"],
            vendored_stdio=tmp_path / "stdio",
            timeout_seconds=1.0,
        )

    assert not marker.exists()
    assert loaded is False


def _qualifying_development_report(
    config: gate.GateConfig, inputs: gate.FreezeInputs
) -> dict[str, Any]:
    hashes = gate.frozen_input_hashes(inputs)
    development = _passing_split_report()
    development.update(
        {
            "total_cases": 1,
            "categories": {},
            "sources": {},
            "case_evidence": [],
            "decision": {"qualified": True},
        }
    )
    return {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": hashes["configuration_sha256"],
        "environment": {
            "python_version": "3.13.0",
            "implementation": "CPython",
            "machine": "arm64",
            "operating_system": "macOS",
            "platform_profile": "macos-arm64-v1",
            "source_policy_version": config.source_policy_version,
            "language_tool_version": config.language_tool["version"],
            "language_tool_upstream_commit": config.language_tool["upstream_commit"],
            "language_tool_manifest_sha256": config.language_tool["manifest_sha256"],
            "language_tool_bridge_sha256": config.language_tool["bridge_sha256"],
            "language_tool_runner_sha256": config.language_tool["runner_sha256"],
            "language_tool_artifact_sha256": config.language_tool["artifact_sha256"],
            "language_tool_dependencies_sha256": config.language_tool[
                "dependencies_sha256"
            ],
            "model_calls_per_sentence": 0.0,
        },
        "artifact_audit": {
            "wheel_sha256": hashes["wheel_sha256"],
            "sdist_sha256": hashes["sdist_sha256"],
            "wheel_members": 1,
            "sdist_members": 1,
            "qualified": True,
        },
        "fallback": {
            "qualified": True,
            "status": "complete",
            "automatic_sources": ["rule:spelling.zeby"],
            "reviewable_sources": [],
            "model_calls": 0,
            "output_hash": "a" * 64,
        },
        "development": development,
        "holdout": None,
        "decision": {"qualified": False, "scope": "sentence_only"},
    }


def test_release_platform_profile_is_explicit_and_fail_closed() -> None:
    assert release.release_platform_profile("Darwin", "arm64") == "macos-arm64-v1"
    for system, machine in (("Linux", "x86_64"), ("Windows", "AMD64")):
        with pytest.raises(RuntimeError, match="does not qualify"):
            release.release_platform_profile(system, machine)

    current_system = platform.system()
    current_machine = platform.machine()
    if (current_system, current_machine) != ("Darwin", "arm64"):
        with pytest.raises(RuntimeError, match="does not qualify"):
            release.release_platform_profile()


def _observation(
    *,
    automatic: tuple[gate.ObservedEdit, ...] = (),
    reviewable: tuple[gate.ObservedEdit, ...] = (),
    corrected_text: str,
    selected_text: str,
) -> gate.RunnerObservation:
    return gate.RunnerObservation(
        request_id=1,
        automatic_edits=automatic,
        reviewable_edits=reviewable,
        analysis_finding_ids=tuple(
            item.finding_id for item in (*automatic, *reviewable)
        ),
        corrected_text=corrected_text,
        selected_text=selected_text,
        suggestion_outcomes=(),
        elapsed_ms=1.0,
        python_rss_bytes=10,
        child_rss_bytes=20,
        combined_rss_bytes=30,
        python_peak_rss_bytes=10,
        child_peak_rss_bytes=20,
        combined_peak_rss_bytes=30,
        model_calls=0,
        process_start_count=1,
    )


def test_split_summary_scores_channels_and_protected_negatives_separately() -> None:
    comma_gold = gate.GoldEdit("punctuation", 4, 4, "", ",")
    comma_actual = gate.ObservedEdit(
        4, 4, "", ",", "punctuation", "rule:languagetool.pl", "finding_a"
    )
    inflection_gold = gate.GoldEdit("inflection", 20, 25, "Nowak", "Nowakiem")
    inflection_actual = gate.ObservedEdit(
        20,
        25,
        "Nowak",
        "Nowakiem",
        "inflection",
        "rule:languagetool.contextual_inflection",
        "finding_b",
    )
    cases = (
        gate.SentenceCase(
            "punctuation_001",
            "punctuation",
            "development",
            "sentence",
            "Wiem że.",
            "Wiem, że.",
            (comma_gold,),
            (),
        ),
        gate.SentenceCase(
            "inflection_001",
            "inflection",
            "development",
            "sentence",
            "Rozmawiałem z Janem Nowak.",
            "Rozmawiałem z Janem Nowakiem.",
            (inflection_gold,),
            (),
        ),
        gate.SentenceCase(
            "hard_negative_001",
            "hard_negative",
            "development",
            "sentence",
            "Anna wróciła.",
            "Anna wróciła.",
            (),
            ("name",),
        ),
    )
    runs = (
        release.CaseRun(
            cases[0],
            _observation(
                automatic=(comma_actual,),
                corrected_text="Wiem, że.",
                selected_text="Wiem, że.",
            ),
            2.0,
            "a" * 64,
        ),
        release.CaseRun(
            cases[1],
            _observation(
                reviewable=(inflection_actual,),
                corrected_text=cases[1].source,
                selected_text=cases[1].expected_output,
            ),
            2.0,
            "b" * 64,
        ),
        release.CaseRun(
            cases[2],
            _observation(
                corrected_text=cases[2].source,
                selected_text=cases[2].source,
            ),
            2.0,
            "c" * 64,
        ),
    )
    performance = release.PerformanceEvidence(
        cold_e2e_ms=3.0,
        warm_in_process_p50_ms=1.0,
        warm_in_process_p95_ms=1.0,
        warm_e2e_p50_ms=2.0,
        warm_e2e_p95_ms=2.0,
        cases_per_second=500.0,
        characters_per_second=5_000.0,
        python_loaded_rss_bytes=10,
        child_loaded_rss_bytes=20,
        combined_loaded_rss_bytes=30,
        python_peak_rss_bytes=10,
        child_peak_rss_bytes=20,
        combined_peak_rss_bytes=30,
        swap_delta_bytes=0,
        socket_count=0,
        model_calls=0,
        process_start_count=1,
        stable_repetitions=2,
    )

    report = release.summarize_split(runs, performance)
    automatic = cast(dict[str, Any], report["automatic"])
    reviewable = cast(dict[str, Any], report["reviewable"])

    assert automatic["precision"] == 1.0
    assert automatic["correction_accuracy"] == 1.0
    assert reviewable["precision"] == 1.0
    categories = cast(dict[str, Any], report["categories"])
    punctuation = cast(dict[str, Any], categories["punctuation"])
    assert punctuation["automatic"]["recall"] == 1.0
    assert punctuation["reviewable"]["false_negative_edits"] == 1
    sources = cast(dict[str, Any], report["sources"])
    language_tool = cast(dict[str, Any], sources["rule:languagetool.pl"])
    assert language_tool["recall"] == 0.5
    assert language_tool["recall_denominator"] == "all_gold_edits"
    assert report["protected_automatic_changes"] == 0
    assert report["protected_reviewable_findings"] == 0
    assert gate.gate_qualifies(report, gate.load_gate_config(CONFIG))


class _StaticSession:
    process_id = 123

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses

    def exchange(self, request_id: int, text: str) -> tuple[dict[str, Any], float]:
        del text
        response = self.responses.pop(0)
        response["request_id"] = request_id
        return response, 2.0


def test_installed_case_run_rejects_nondeterministic_repetition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = gate.SentenceCase(
        "punctuation_001",
        "punctuation",
        "development",
        "sentence",
        "Wiem że.",
        "Wiem, że.",
        (gate.GoldEdit("punctuation", 4, 4, "", ","),),
        (),
    )
    first = _response(finding=_finding())
    second = _response(finding=_finding())
    second_finding = second["automatic_findings"][0]
    second_finding["id"] = "finding_" + "b" * 32
    monkeypatch.setattr(release, "_swap_used_bytes", lambda: 0)
    monkeypatch.setattr(release, "_socket_count_tree", lambda _pid: 0)

    with pytest.raises(ValueError, match="not stable"):
        release.run_installed_cases(
            (case,),
            _StaticSession([first, second]),
            gate.load_gate_config(CONFIG),
            repetitions=2,
        )


def test_evaluator_cli_requires_exactly_one_split_mode() -> None:
    with pytest.raises(SystemExit):
        release.parse_arguments([])


def test_evaluator_rejects_unpinned_vendored_stdio(tmp_path: Path) -> None:
    executable = tmp_path / "replacement-stdio"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)

    with pytest.raises(ValueError, match="pinned runner"):
        release._validate_vendored_stdio(executable, gate.load_gate_config(CONFIG))
    development = release.parse_arguments(
        [
            "--development",
            "--dist",
            "/tmp/dist",
            "--vendored-stdio",
            "/tmp/run_stdio.sh",
            "--output",
            "/tmp/report.json",
            "--freeze",
            "/tmp/frozen.json",
        ]
    )
    assert development.development is True
    assert development.holdout is False


def test_committed_holdout_evidence_is_private_and_records_failed_gate() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    frozen = json.loads((EXPERIMENT / "frozen_gate.json").read_text(encoding="utf-8"))
    marker = json.loads((EXPERIMENT / "holdout.started").read_text(encoding="utf-8"))
    development_report = dict(report)
    development_report["holdout"] = None
    development_report["decision"] = {
        "qualified": False,
        "scope": "sentence_only",
    }

    assert gate.validate_privacy_safe_report(report) == report
    assert report["development"]["decision"] == {"qualified": True}
    assert report["development"]["automatic"]["precision"] == 1.0
    assert report["development"]["automatic"]["correction_accuracy"] == 1.0
    assert report["development"]["automatic"]["proposed_edits"] == 6
    assert report["development"]["reviewable"]["precision"] == 1.0
    assert report["development"]["reviewable"]["proposed_edits"] == 18
    assert report["development"]["protected_automatic_changes"] == 0
    assert report["development"]["protected_reviewable_findings"] == 0
    assert report["holdout"]["decision"] == {"qualified": False}
    assert report["holdout"]["automatic"]["precision"] == 1.0
    assert report["holdout"]["automatic"]["correction_accuracy"] == 0.8
    assert report["holdout"]["reviewable"]["precision"] == 1.0
    assert report["holdout"]["reviewable"]["correction_accuracy"] == 1.0
    assert report["holdout"]["protected_automatic_changes"] == 0
    assert report["holdout"]["protected_reviewable_findings"] == 0
    assert report["decision"] == {"qualified": False, "scope": "sentence_only"}
    assert frozen["development_report_sha256"] == gate.canonical_json_sha256(
        development_report
    )
    assert marker == frozen


def test_failed_holdout_docs_do_not_overclaim() -> None:
    experiment = (EXPERIMENT / "README.md").read_text(encoding="utf-8")
    quality = (ROOT / "docs" / "quality-baseline.md").read_text(encoding="utf-8")
    limitations = (ROOT / "docs" / "limitations.md").read_text(encoding="utf-8")

    assert "automatic correction accuracy: `1.00`" in experiment
    assert "development report SHA-256" in experiment
    assert "holdout automatic correction accuracy: `0.80`" in experiment
    assert "cannot be rerun" in experiment
    assert "#76" in quality
    assert "holdout gate failed" in limitations
    assert "paragraph" in limitations
    assert "remain unqualified" in limitations
