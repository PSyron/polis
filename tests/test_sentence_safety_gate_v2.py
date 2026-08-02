"""Synthetic contracts for the v2 sentence safety gate."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
import tomllib
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any, TextIO, cast

import pytest
from experiments.sentence_safety_gate.gate import (
    FreezeInputs,
    GoldEdit,
    ObservedEdit,
    RunnerObservation,
    freeze_gate,
)
from experiments.sentence_safety_gate_v2 import gate, run_evaluation
from experiments.sentence_safety_gate_v2.gate import (
    QualityGates,
    load_development_sentences,
    load_gate_config,
)
from experiments.sentence_safety_gate_v2.run_evaluation import (
    CaseRun,
    InstalledRunnerSession,
    PerformanceEvidence,
    audit_release_artifacts,
    install_artifact_offline,
    summarize_split,
    validate_privacy_safe_report,
)

from polis.evaluation.correction_corpus import (
    CaseReview,
    CorpusProvenance,
    CorrectionCorpusCase,
)

pytestmark = pytest.mark.research


def test_v2_gate_exports_only_its_public_loader_contract() -> None:
    assert gate.__all__ == [
        "GateConfig",
        "QualityGates",
        "SentenceCase",
        "load_development_sentences",
        "load_gate_config",
        "load_reserved_holdout_sentences",
        "reserve_holdout_once",
    ]


def _synthetic_reviewed_xml(*, holdout_count: int = 160) -> str:
    records = ['<?xml version="1.0" encoding="UTF-8"?>', "<corpus>"]
    for split, count in (("development", 80), ("holdout", holdout_count)):
        prefix = "dev" if split == "development" else "holdout"
        for index in range(count):
            identifier = f"{prefix}-{index:03d}"
            records.extend(
                (
                    f'<case id="{identifier}" stratum="hard_negative" '
                    f'split="{split}" unit="sentence">',
                    f"<input>Poprawne zdanie syntetyczne {index}.</input>",
                    (
                        "<expected_output>Poprawne zdanie syntetyczne "
                        f"{index}.</expected_output>"
                    ),
                    '<review status="human-reviewed" '
                    'reviewer="Polis architecture owner" '
                    'reviewed_at="2026-08-02" '
                    'checklist_version="safety-corpus-review-v2"/>',
                    "</case>",
                )
            )
    records.append("</corpus>")
    return "\n".join(records)


def _valid_config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "experiment_id": "polis_sentence_safety_gate_v2_2026_08_02",
        "sentence_only": True,
        "platform_profile": "macos-arm64-v1",
        "source_policy_version": "1.2",
        "corpus": {
            "id": "polis_polish_correction_safety_corpus_v2",
            "candidate_digest": (
                "c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53"
            ),
            "frozen_digest": (
                "53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29"
            ),
            "json_path": (
                "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.json"
            ),
            "json_sha256": (
                "9c9b1cf1103dfaa096dd113948e0b47bfb26d5722ebe5edce1250e9889a59f69"
            ),
            "xml_path": (
                "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.xml"
            ),
            "xml_sha256": (
                "676bc630e6644aecd30daf166c50ebe9c8558fd5714e74081722b0c4123ecb3a"
            ),
            "approval_path": (
                "tests/fixtures/evaluation/"
                "polish_correction_safety_corpus_v2.approval.json"
            ),
            "approval_sha256": (
                "8a21b3d291eb0542b484db318350678bde39cbf549451eb6f35cfd995ba39d77"
            ),
        },
        "sources": {
            "automatic": [
                "rule:agreement.copula",
                "rule:languagetool.pl",
                "rule:spelling.jestes",
                "rule:spelling.wlasnie",
                "rule:spelling.zeby",
                "rule:syntax.comma_space",
                "rule:syntax.list_space",
                "rule:syntax.quote_space",
                "rule:syntax.sentence_space",
            ],
            "reviewable": [
                "rule:languagetool.contextual_inflection",
                "rule:syntax.missing_correlative",
                "rule:syntax.missing_reflexive",
            ],
        },
        "language_tool": {
            "version": "6.8",
            "upstream_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "manifest_sha256": (
                "d5871e8173addb96cc93e2f8ce6833737f08a20c4fc47e99596b4d82b8f3f6e8"
            ),
            "bridge_sha256": (
                "c946c3ddfab36e45dab1716ca66ccfd61d0a6bfaa14b2e69926cb1b3da964c3d"
            ),
            "runner_sha256": (
                "32b2d9bccdfccd1efc94939530de70f05040295861509b72b8b91752435b2fca"
            ),
            "artifact_sha256": (
                "6959bbebad93c028552c21bae4d2524a0c08d09c1753c9a3fdf646ec1d645421"
            ),
            "dependencies_sha256": (
                "de97bed1193abbed914ef23dd99757204aa3bcef29d3cfa8f1ea485178566a99"
            ),
        },
        "gates": {
            "automatic_minimum_precision": 1.0,
            "automatic_minimum_correction_accuracy": 1.0,
            "reviewable_minimum_precision": 0.9,
            "minimum_structured_outcome_validity": 1.0,
            "maximum_protected_automatic_changes": 0,
            "maximum_protected_reviewable_findings": 0,
            "maximum_warm_in_process_p95_ms": 100,
            "maximum_warm_e2e_p95_ms": 500,
            "maximum_combined_peak_rss_bytes": 1_073_741_824,
            "maximum_swap_delta_bytes": 0,
            "maximum_socket_count": 0,
            "required_model_calls": 0,
            "required_process_start_count": 1,
            "required_stable_repetitions": 2,
        },
    }


def test_v2_config_enforces_closed_frozen_identities_and_gates(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")

    config = load_gate_config(config_path)

    assert config.experiment_id == "polis_sentence_safety_gate_v2_2026_08_02"
    assert config.source_policy_version == "1.2"
    assert config.corpus_id == "polis_polish_correction_safety_corpus_v2"
    assert config.candidate_corpus_digest == (
        "c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53"
    )
    assert config.frozen_corpus_digest == (
        "53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29"
    )
    assert config.corpus_approval_path.endswith("corpus_v2.approval.json")
    assert config.corpus_approval_sha256 == (
        "8a21b3d291eb0542b484db318350678bde39cbf549451eb6f35cfd995ba39d77"
    )
    assert config.gates == QualityGates(
        automatic_minimum_precision=1.0,
        automatic_minimum_correction_accuracy=1.0,
        reviewable_minimum_precision=0.9,
        minimum_structured_outcome_validity=1.0,
        maximum_protected_automatic_changes=0,
        maximum_protected_reviewable_findings=0,
        maximum_warm_in_process_p95_ms=100.0,
        maximum_warm_e2e_p95_ms=500.0,
        maximum_combined_peak_rss_bytes=1_073_741_824,
        maximum_swap_delta_bytes=0,
        maximum_socket_count=0,
        required_model_calls=0,
        required_process_start_count=1,
        required_stable_repetitions=2,
    )

    invalid = _valid_config()
    invalid["unexpected"] = True
    config_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly the frozen keys"):
        load_gate_config(config_path)


def test_v2_config_exposes_an_immutable_language_tool_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")

    config = load_gate_config(config_path)

    with pytest.raises(TypeError):
        config.language_tool["version"] = "changed"  # type: ignore[index]


def test_v2_development_loader_never_materializes_holdout(tmp_path: Path) -> None:
    corpus_xml = tmp_path / "synthetic-v2.xml"
    corpus_xml.write_text(_synthetic_reviewed_xml(), encoding="utf-8")
    materialized: list[str] = []

    cases = load_development_sentences(
        corpus_xml,
        on_materialized=materialized.append,
    )

    assert len(cases) == 80
    assert {case.split for case in cases} == {"development"}
    assert materialized == [f"dev-{index:03d}" for index in range(80)]
    assert not any(identifier.startswith("holdout-") for identifier in materialized)


def test_v2_development_loader_rejects_noncanonical_holdout_boundaries(
    tmp_path: Path,
) -> None:
    corpus_xml = tmp_path / "synthetic-v2.xml"
    corpus_xml.write_text(
        _synthetic_reviewed_xml(holdout_count=159).replace(
            "</case>\n</corpus>",
            '<edit start="not-an-integer" end="0" original="" suggestion="" />'
            "</case>\n</corpus>",
            1,
        ),
        encoding="utf-8",
    )
    materialized: list[str] = []

    with pytest.raises(ValueError, match="holdout split must contain exactly 160"):
        load_development_sentences(corpus_xml, on_materialized=materialized.append)

    assert materialized == [f"dev-{index:03d}" for index in range(80)]


def test_v2_development_loader_rejects_paweł_cyroń_as_owner_role(
    tmp_path: Path,
) -> None:
    corpus_xml = tmp_path / "synthetic-v2.xml"
    corpus_xml.write_text(
        _synthetic_reviewed_xml().replace(
            'reviewer="Polis architecture owner"',
            'reviewer="Paweł Cyroń"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="owner-reviewed"):
        load_development_sentences(corpus_xml)


def _synthetic_raw() -> dict[str, object]:
    return {
        "schema_version": 3,
        "id": "synthetic_v2",
        "candidate_digest": "candidate-v1",
        "frozen_digest": "frozen-v1",
    }


def _synthetic_approval() -> dict[str, object]:
    return {
        "candidate_digest": "candidate-v1",
        "frozen_digest": "frozen-v1",
        "reviewed_at": "2026-08-02",
    }


def _synthetic_holdout_cases(count: int = 160) -> tuple[CorrectionCorpusCase, ...]:
    provenance = CorpusProvenance(
        source="synthetic",
        license="CC0-1.0",
        created="2026-08-02",
        method="generated test fixture",
        notes="contains no committed corpus material",
    )
    review = CaseReview(
        status="human-reviewed",
        reviewer="Synthetic reviewer",
        reviewed_at="2026-08-02",
        checklist_version="synthetic-review-v1",
    )
    return tuple(
        CorrectionCorpusCase(
            id=f"synthetic_holdout_{index:03d}",
            stratum="hard_negative",
            split="holdout",
            unit="sentence",
            input=f"Syntetyczne zdanie {index}.",
            expected_output=f"Syntetyczne zdanie {index}.",
            description="Synthetic holdout case.",
            tags=("synthetic",),
            normalized_template=f"syntetyczne zdanie {index}.",
            entity_ids=(),
            entity_spans=(),
            protected_phenomenon="synthetic_safety",
            provenance=provenance,
            review=review,
            edits=(),
        )
        for index in range(count)
    )


def _prepare_valid_synthetic_freeze(
    tmp_path: Path,
    marker: Path,
) -> tuple[Path, FreezeInputs, Any]:
    frozen_path = tmp_path / "gate.freeze.json"
    frozen_input = tmp_path / "synthetic-input.txt"
    frozen_input.write_text("synthetic frozen input\n", encoding="utf-8")
    inputs = FreezeInputs(files={"synthetic_input": frozen_input}, directories={})
    freeze_gate(inputs, frozen_path)
    reservation = gate.reserve_holdout_once(frozen_path, marker, inputs)
    return frozen_path, inputs, reservation


def _write_synthetic_evidence(
    tmp_path: Path,
    *,
    raw: object | None = None,
    approval: object | None = None,
) -> tuple[Path, Path]:
    corpus_path = tmp_path / "synthetic-v2.json"
    approval_path = tmp_path / "synthetic-v2.approval.json"
    corpus_path.write_text(
        json.dumps(_synthetic_raw() if raw is None else raw),
        encoding="utf-8",
    )
    approval_path.write_text(
        json.dumps(_synthetic_approval() if approval is None else approval),
        encoding="utf-8",
    )
    return corpus_path, approval_path


def _load_synthetic_reserved_holdout(
    tmp_path: Path,
    marker: Path,
    frozen_path: Path,
    inputs: FreezeInputs,
    reservation: Any,
) -> tuple[gate.SentenceCase, ...]:
    corpus_path, approval_path = _write_synthetic_evidence(tmp_path)
    return gate.load_reserved_holdout_sentences(
        corpus_path,
        approval_path,
        marker,
        frozen_path,
        inputs,
        reservation=reservation,
    )


def _bind_synthetic_validation(monkeypatch: pytest.MonkeyPatch) -> object:
    corpus = object()
    monkeypatch.setattr(gate, "validate_safety_corpus", lambda raw: corpus)
    return corpus


def test_v2_reservation_is_durable_before_quality_gate_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    observed: list[bool] = []

    def guarded_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        observed.append(marker.is_file())
        return ()

    _bind_synthetic_validation(monkeypatch)
    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", guarded_selector)
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)

    with pytest.raises(ValueError, match="160"):
        _load_synthetic_reserved_holdout(
            tmp_path,
            marker,
            frozen_path,
            inputs,
            reservation,
        )

    assert observed == [True]
    assert marker.is_file()


def test_v2_admission_requires_persisted_approval_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    corpus_path = tmp_path / "synthetic-v2.json"
    corpus_path.write_text(json.dumps(_synthetic_raw()), encoding="utf-8")
    selection_called = False

    def forbidden_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        nonlocal selection_called
        selection_called = True
        return ()

    _bind_synthetic_validation(monkeypatch)
    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden_selector)

    with pytest.raises(FileNotFoundError):
        gate.load_reserved_holdout_sentences(
            corpus_path,
            tmp_path / "missing-approval.json",
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )

    assert selection_called is False
    assert marker.is_file()
    with pytest.raises(ValueError, match="already consumed"):
        _load_synthetic_reserved_holdout(
            tmp_path,
            marker,
            frozen_path,
            inputs,
            reservation,
        )
    assert selection_called is False


@pytest.mark.parametrize("digest_name", ["candidate_digest", "frozen_digest"])
def test_v2_admission_rejects_approval_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    digest_name: str,
) -> None:
    marker = tmp_path / "holdout.started"
    corpus = _bind_synthetic_validation(monkeypatch)
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    approval = _synthetic_approval()
    approval[digest_name] = "drifted"
    corpus_path, approval_path = _write_synthetic_evidence(
        tmp_path,
        approval=approval,
    )

    def evidence_selector(
        selected_corpus: object,
        *,
        purpose: str,
        raw: object,
        approval_manifest: object,
    ) -> tuple[CorrectionCorpusCase, ...]:
        assert selected_corpus is corpus
        assert purpose == "quality_gate"
        assert raw == _synthetic_raw()
        if approval_manifest != _synthetic_approval():
            raise ValueError("approval manifest drift")
        return _synthetic_holdout_cases()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", evidence_selector)

    with pytest.raises(ValueError, match="approval manifest drift"):
        gate.load_reserved_holdout_sentences(
            corpus_path,
            approval_path,
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )

    assert marker.is_file()


def test_v2_admission_rejects_changed_review_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    _bind_synthetic_validation(monkeypatch)
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    approval = _synthetic_approval()
    approval["reviewed_at"] = "2026-08-03"
    corpus_path, approval_path = _write_synthetic_evidence(
        tmp_path,
        approval=approval,
    )

    def evidence_selector(
        corpus: object,
        *,
        purpose: str,
        raw: object,
        approval_manifest: object,
    ) -> tuple[CorrectionCorpusCase, ...]:
        del corpus, purpose, raw
        if approval_manifest != _synthetic_approval():
            raise ValueError("review date drift")
        return _synthetic_holdout_cases()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", evidence_selector)

    with pytest.raises(ValueError, match="review date drift"):
        gate.load_reserved_holdout_sentences(
            corpus_path,
            approval_path,
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )

    assert marker.is_file()


def test_v2_admission_rejects_mismatched_marker_before_opening_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    marker.write_text(json.dumps({"synthetic_input_sha256": "0" * 64}))
    selection_called = False

    def forbidden_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        nonlocal selection_called
        selection_called = True
        return ()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden_selector)

    with pytest.raises(ValueError, match="reservation does not match"):
        gate.load_reserved_holdout_sentences(
            tmp_path / "missing-corpus.json",
            tmp_path / "missing-approval.json",
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )

    assert selection_called is False


def test_v2_admission_rejects_frozen_input_drift_before_opening_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    next(iter(inputs.files.values())).write_text("drifted\n", encoding="utf-8")
    selection_called = False

    def forbidden_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        nonlocal selection_called
        selection_called = True
        return ()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden_selector)

    with pytest.raises(ValueError, match="frozen gate hash mismatch"):
        gate.load_reserved_holdout_sentences(
            tmp_path / "missing-corpus.json",
            tmp_path / "missing-approval.json",
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )

    assert selection_called is False


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory fsync contract")
def test_v2_reservation_fsyncs_file_then_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path = tmp_path / "gate.freeze.json"
    frozen_input = tmp_path / "synthetic-input.txt"
    frozen_input.write_text("synthetic frozen input\n", encoding="utf-8")
    inputs = FreezeInputs(files={"synthetic_input": frozen_input}, directories={})
    frozen = freeze_gate(inputs, frozen_path)
    real_fsync = os.fsync
    fsynced: list[str] = []

    def observing_fsync(file_descriptor: int) -> None:
        mode = os.fstat(file_descriptor).st_mode
        kind = "directory" if stat.S_ISDIR(mode) else "file"
        if kind == "file":
            assert json.loads(marker.read_text(encoding="utf-8")) == frozen.as_dict()
        fsynced.append(kind)
        real_fsync(file_descriptor)

    monkeypatch.setattr(
        "experiments.sentence_safety_gate_v2.gate.os.fsync",
        observing_fsync,
    )

    reservation = gate.reserve_holdout_once(frozen_path, marker, inputs)

    assert fsynced == ["file", "directory"]
    assert reservation is not None


@pytest.mark.parametrize("failed_call", [1, 2], ids=["file", "parent-directory"])
def test_v2_reservation_fsync_failure_is_permanent_and_never_selects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_call: int,
) -> None:
    if failed_call == 2 and os.name != "posix":
        pytest.skip("parent-directory fsync is POSIX-only")
    marker = tmp_path / "holdout.started"
    frozen_path = tmp_path / "gate.freeze.json"
    frozen_input = tmp_path / "synthetic-input.txt"
    frozen_input.write_text("synthetic frozen input\n", encoding="utf-8")
    inputs = FreezeInputs(files={"synthetic_input": frozen_input}, directories={})
    freeze_gate(inputs, frozen_path)
    selection_called = False
    fsync_calls = 0
    real_fsync = os.fsync

    def failed_fsync(file_descriptor: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == failed_call:
            raise OSError("synthetic fsync failure")
        real_fsync(file_descriptor)

    def forbidden_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        nonlocal selection_called
        selection_called = True
        return ()

    monkeypatch.setattr(
        "experiments.sentence_safety_gate_v2.gate.os.fsync",
        failed_fsync,
    )
    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden_selector)

    reservation = None
    with pytest.raises(OSError, match="synthetic fsync failure"):
        reservation = gate.reserve_holdout_once(frozen_path, marker, inputs)

    assert marker.is_file()
    assert reservation is None
    assert selection_called is False
    with pytest.raises(ValueError, match="reservation capability"):
        gate.load_reserved_holdout_sentences(
            tmp_path / "missing-corpus.json",
            tmp_path / "missing-approval.json",
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )
    assert selection_called is False
    with pytest.raises(FileExistsError, match="already reserved"):
        gate.reserve_holdout_once(frozen_path, marker, inputs)


def test_v2_reservation_rejects_existing_marker_without_replacing_it(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "holdout.started"
    marker.write_text("existing marker\n", encoding="utf-8")
    frozen_path = tmp_path / "gate.freeze.json"
    frozen_input = tmp_path / "synthetic-input.txt"
    frozen_input.write_text("synthetic frozen input\n", encoding="utf-8")
    inputs = FreezeInputs(files={"synthetic_input": frozen_input}, directories={})
    freeze_gate(inputs, frozen_path)

    with pytest.raises(FileExistsError, match="already reserved"):
        gate.reserve_holdout_once(frozen_path, marker, inputs)

    assert marker.read_text(encoding="utf-8") == "existing marker\n"


def test_v2_reservation_interruption_leaves_marker_and_denies_repeat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path = tmp_path / "gate.freeze.json"
    frozen_input = tmp_path / "synthetic-input.txt"
    frozen_input.write_text("synthetic frozen input\n", encoding="utf-8")
    inputs = FreezeInputs(files={"synthetic_input": frozen_input}, directories={})
    freeze_gate(inputs, frozen_path)

    def interrupted_dump(value: object, destination: TextIO, **kwargs: object) -> None:
        del value, kwargs
        destination.write('{"partial":')
        raise KeyboardInterrupt

    with monkeypatch.context() as interruption:
        interruption.setattr(
            "experiments.sentence_safety_gate_v2.gate.json.dump",
            interrupted_dump,
        )
        with pytest.raises(KeyboardInterrupt):
            gate.reserve_holdout_once(frozen_path, marker, inputs)

    assert marker.read_text(encoding="utf-8") == '{"partial":'
    with pytest.raises(FileExistsError, match="already reserved"):
        gate.reserve_holdout_once(frozen_path, marker, inputs)


def test_v2_admission_rejects_manually_created_matching_marker_without_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path = tmp_path / "gate.freeze.json"
    frozen_input = tmp_path / "synthetic-input.txt"
    frozen_input.write_text("synthetic frozen input\n", encoding="utf-8")
    inputs = FreezeInputs(files={"synthetic_input": frozen_input}, directories={})
    frozen = freeze_gate(inputs, frozen_path)
    marker.write_text(
        json.dumps(frozen.as_dict(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    selection_called = False

    def forbidden_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        nonlocal selection_called
        selection_called = True
        return ()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden_selector)

    with pytest.raises(ValueError, match="reservation capability"):
        gate.load_reserved_holdout_sentences(
            tmp_path / "missing-corpus.json",
            tmp_path / "missing-approval.json",
            marker,
            frozen_path,
            inputs,
            reservation=None,  # type: ignore[arg-type]
        )

    assert marker.is_file()
    assert selection_called is False


def test_v2_admission_rejects_capability_copied_to_different_pid_before_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    issuer_pid = os.getpid()
    accessed: list[str] = []

    def forbidden_access(*args: object, **kwargs: object) -> object:
        del args, kwargs
        accessed.append("forbidden")
        raise AssertionError("PID drift reached persisted evidence")

    with monkeypatch.context() as child:
        child.setattr(
            "experiments.sentence_safety_gate_v2.gate.os.getpid",
            lambda: issuer_pid + 1,
        )
        child.setattr(Path, "resolve", forbidden_access)
        child.setattr(Path, "is_file", forbidden_access)
        child.setattr(Path, "read_text", forbidden_access)
        child.setattr(gate, "verify_frozen_gate", forbidden_access)
        child.setattr(gate, "select_safety_cases_for_purpose", forbidden_access)

        with pytest.raises(ValueError, match="issuing process"):
            gate.load_reserved_holdout_sentences(
                tmp_path / "missing-corpus.json",
                tmp_path / "missing-approval.json",
                marker,
                frozen_path,
                inputs,
                reservation=reservation,
            )

    assert accessed == []

    _bind_synthetic_validation(monkeypatch)
    monkeypatch.setattr(
        gate,
        "select_safety_cases_for_purpose",
        lambda *args, **kwargs: _synthetic_holdout_cases(),
    )
    selected = _load_synthetic_reserved_holdout(
        tmp_path,
        marker,
        frozen_path,
        inputs,
        reservation,
    )
    assert len(selected) == 160


def test_v2_admission_success_still_permanently_denies_repeat_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    corpus = _bind_synthetic_validation(monkeypatch)
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)

    def synthetic_selector(
        selected_corpus: object,
        *,
        purpose: str,
        raw: object,
        approval_manifest: object,
    ) -> tuple[CorrectionCorpusCase, ...]:
        assert selected_corpus is corpus
        assert purpose == "quality_gate"
        assert raw == _synthetic_raw()
        assert approval_manifest == _synthetic_approval()
        return _synthetic_holdout_cases()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", synthetic_selector)

    selected = _load_synthetic_reserved_holdout(
        tmp_path,
        marker,
        frozen_path,
        inputs,
        reservation,
    )

    assert len(selected) == 160
    assert {case.split for case in selected} == {"holdout"}
    assert selected[0].case_id == "synthetic_holdout_000"
    selection_called = False

    def forbidden_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        nonlocal selection_called
        selection_called = True
        return ()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden_selector)
    with pytest.raises(ValueError, match="already consumed"):
        gate.load_reserved_holdout_sentences(
            tmp_path / "missing-corpus.json",
            tmp_path / "missing-approval.json",
            marker,
            frozen_path,
            inputs,
            reservation=reservation,
        )
    assert selection_called is False
    with pytest.raises(FileExistsError, match="already reserved"):
        gate.reserve_holdout_once(frozen_path, marker, inputs)


@pytest.mark.parametrize("invalid_case", ["development", "pending-review"])
def test_v2_admission_requires_every_selected_case_to_be_reviewed_holdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    marker = tmp_path / "holdout.started"
    _bind_synthetic_validation(monkeypatch)
    frozen_path, inputs, reservation = _prepare_valid_synthetic_freeze(tmp_path, marker)
    selected = list(_synthetic_holdout_cases())
    first = selected[0]
    if invalid_case == "development":
        selected[0] = replace(first, split="development")
    else:
        selected[0] = replace(
            first,
            review=replace(
                first.review,
                status="pending-human-review",
                reviewer=None,
                reviewed_at=None,
            ),
        )
    monkeypatch.setattr(
        gate,
        "select_safety_cases_for_purpose",
        lambda *args, **kwargs: tuple(selected),
    )

    with pytest.raises(ValueError, match="160 reviewed holdout"):
        _load_synthetic_reserved_holdout(
            tmp_path,
            marker,
            frozen_path,
            inputs,
            reservation,
        )


def _write_archive_pair(
    tmp_path: Path,
    *,
    wheel_extra: tuple[str, bytes] | None = None,
    sdist_extra: tuple[str, bytes] | None = None,
) -> tuple[Path, Path]:
    wheel = tmp_path / "polis-0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("polis/__init__.py", b"SENTINEL = 'installed-only'\n")
        archive.writestr("polis-0.0.dist-info/METADATA", b"Name: polis\nVersion: 0.0\n")
        if wheel_extra is not None:
            archive.writestr(*wheel_extra)

    sdist = tmp_path / "polis-0.0.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        members = {
            "polis-0.0/PKG-INFO": b"Name: polis\nVersion: 0.0\n",
            "polis-0.0/src/polis/__init__.py": b"SENTINEL = 'installed-only'\n",
        }
        if sdist_extra is not None:
            members[sdist_extra[0]] = sdist_extra[1]
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return wheel, sdist


@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
@pytest.mark.parametrize(
    "name",
    [
        "tests/fixtures/evaluation/synthetic-research.json",
        "polis/synthetic-model.gguf",
        "polis/synthetic-runtime.jar",
        "polis/.env",
    ],
)
def test_v2_artifact_audit_rejects_research_models_jars_and_private_files(
    tmp_path: Path,
    archive_kind: str,
    name: str,
) -> None:
    member = (name, b"synthetic")
    wheel, sdist = _write_archive_pair(
        tmp_path,
        wheel_extra=member if archive_kind == "wheel" else None,
        sdist_extra=(f"polis-0.0/{name}", member[1])
        if archive_kind == "sdist"
        else None,
    )

    with pytest.raises(ValueError, match="distribution contains"):
        audit_release_artifacts(wheel, sdist)


@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
def test_v2_artifact_audit_rejects_private_paths_in_file_content(
    tmp_path: Path,
    archive_kind: str,
) -> None:
    member = ("polis/private.txt", os.fspath(Path.home()).encode("utf-8"))
    wheel, sdist = _write_archive_pair(
        tmp_path,
        wheel_extra=member if archive_kind == "wheel" else None,
        sdist_extra=("polis-0.0/src/polis/private.txt", member[1])
        if archive_kind == "sdist"
        else None,
    )

    with pytest.raises(ValueError, match="private home path"):
        audit_release_artifacts(wheel, sdist)


def _write_installable_synthetic_wheel(tmp_path: Path) -> Path:
    wheel = tmp_path / "polis-0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("polis/__init__.py", "SENTINEL = 'installed-only'\n")
        archive.writestr(
            "polis-0.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: polis\nVersion: 0.0\n",
        )
        archive.writestr(
            "polis-0.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: synthetic\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr("polis-0.0.dist-info/RECORD", "")
    return wheel


def test_v2_offline_install_imports_only_from_temporary_installation(
    tmp_path: Path,
) -> None:
    wheel = _write_installable_synthetic_wheel(tmp_path)
    destination = tmp_path / "clean-install"

    python = install_artifact_offline(wheel, destination)
    completed = subprocess.run(
        (
            os.fspath(python),
            "-c",
            "import pathlib, polis; "
            "print(pathlib.Path(polis.__file__).resolve()); "
            "print(polis.SENTINEL)",
        ),
        cwd=tmp_path,
        env={"PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
        check=True,
    )

    origin, sentinel = completed.stdout.splitlines()
    assert Path(origin).is_relative_to(destination)
    assert sentinel == "installed-only"


class _SyntheticInput:
    def __init__(self) -> None:
        self.payload = ""
        self.closed = False

    def write(self, payload: str) -> int:
        self.payload += payload
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _SyntheticProcess:
    def __init__(self, output: str) -> None:
        self.pid = 4242
        self.stdin = _SyntheticInput()
        self.stdout = io.StringIO(output)
        self.stderr = io.StringIO("")
        self.returncode = 0

    def wait(self, timeout: float) -> int:
        del timeout
        return 0

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None


def test_v2_installed_runner_request_contains_source_visible_fields_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python = tmp_path / "python"
    runner = tmp_path / "runner.py"
    vendored = tmp_path / "run_stdio.sh"
    for path in (python, runner, vendored):
        path.write_text("synthetic", encoding="utf-8")
    scorer_gold = "SCORER-GOLD-MUST-STAY-LOCAL"
    process = _SyntheticProcess('{"status":"complete"}\n')
    startup: dict[str, object] = {}

    def synthetic_popen(command: object, **kwargs: object) -> _SyntheticProcess:
        startup["command"] = command
        startup["environment"] = kwargs["env"]
        return process

    historical = "experiments.sentence_safety_gate.run_evaluation"
    monkeypatch.setattr(f"{historical}._installed_package_root", lambda *args: tmp_path)
    monkeypatch.setattr(f"{historical}._network_denial_prefix", lambda: ())
    monkeypatch.setattr(f"{historical}._wait_readable", lambda *args: True)
    monkeypatch.setattr(f"{historical}._resource_tree_snapshot", lambda *args: (1, 2))
    monkeypatch.setattr(f"{historical}.subprocess.Popen", synthetic_popen)

    with InstalledRunnerSession(
        python=python,
        runner=runner,
        vendored_stdio=vendored,
        working_directory=tmp_path / "work",
        timeout_seconds=1.0,
    ) as session:
        session.exchange(7, "Zdanie widoczne dla analizatora.")

    request = json.loads(process.stdin.payload)
    assert request == {
        "schema_version": 2,
        "request_id": 7,
        "operation": "analyze_sentence",
        "text": "Zdanie widoczne dla analizatora.",
    }
    captured = json.dumps(startup, default=str, ensure_ascii=False)
    assert scorer_gold not in captured
    assert scorer_gold not in process.stdin.payload


def test_v2_installed_runner_errors_do_not_echo_scorer_gold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python = tmp_path / "python"
    runner = tmp_path / "runner.py"
    vendored = tmp_path / "run_stdio.sh"
    for path in (python, runner, vendored):
        path.write_text("synthetic", encoding="utf-8")
    scorer_gold = "SCORER-GOLD-MUST-STAY-LOCAL"
    process = _SyntheticProcess(scorer_gold + "\n")
    historical = "experiments.sentence_safety_gate.run_evaluation"
    monkeypatch.setattr(f"{historical}._installed_package_root", lambda *args: tmp_path)
    monkeypatch.setattr(f"{historical}._network_denial_prefix", lambda: ())
    monkeypatch.setattr(f"{historical}._wait_readable", lambda *args: True)
    monkeypatch.setattr(
        f"{historical}.subprocess.Popen",
        lambda *args, **kwargs: process,
    )

    with InstalledRunnerSession(
        python=python,
        runner=runner,
        vendored_stdio=vendored,
        working_directory=tmp_path / "work",
        timeout_seconds=1.0,
    ) as session:
        with pytest.raises(ValueError) as captured:
            session.exchange(1, "Zdanie widoczne dla analizatora.")

    assert scorer_gold not in str(captured.value)
    assert scorer_gold not in process.stdin.payload


def _synthetic_runner_response(request_id: int, source: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "request_id": request_id,
        "status": "complete",
        "source_policy_version": "1.2",
        "analysis_findings": [],
        "automatic_findings": [],
        "reviewable_findings": [],
        "corrected_text": source,
        "selected_text": source,
        "selected_finding_ids": [],
        "suggestion_outcomes": [],
        "elapsed_ms": 1.0,
        "python_rss_bytes": 1,
        "child_rss_bytes": 2,
        "combined_rss_bytes": 3,
        "python_peak_rss_bytes": 1,
        "child_peak_rss_bytes": 2,
        "combined_peak_rss_bytes": 3,
        "model_calls": 0,
        "process_start_count": 1,
    }


def test_v2_scorer_gold_never_crosses_actual_installed_runner_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    python = tmp_path / "python"
    runner = tmp_path / "runner.py"
    vendored = tmp_path / "run_stdio.sh"
    for path in (python, runner, vendored):
        path.write_text("synthetic", encoding="utf-8")
    source = "Zdanie widoczne dla analizatora."
    scorer_gold = "SCORER_GOLD_EXPECTED_OUTPUT_AND_EDIT"
    raw_output = "".join(
        json.dumps(_synthetic_runner_response(request_id, source)) + "\n"
        for request_id in (1, 2)
    )
    process = _SyntheticProcess(raw_output)
    startup: dict[str, object] = {}

    def synthetic_popen(command: object, **kwargs: object) -> _SyntheticProcess:
        startup["command"] = command
        startup["environment"] = kwargs["env"]
        return process

    historical = "experiments.sentence_safety_gate.run_evaluation"
    monkeypatch.setattr(f"{historical}._installed_package_root", lambda *args: tmp_path)
    monkeypatch.setattr(f"{historical}._network_denial_prefix", lambda: ())
    monkeypatch.setattr(f"{historical}._wait_readable", lambda *args: True)
    monkeypatch.setattr(f"{historical}._resource_tree_snapshot", lambda *args: (1, 2))
    monkeypatch.setattr(f"{historical}._swap_used_bytes", lambda: 0)
    monkeypatch.setattr(f"{historical}._socket_count_tree", lambda *args: 0)
    monkeypatch.setattr(f"{historical}.subprocess.Popen", synthetic_popen)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    config = load_gate_config(config_path)
    case = gate.SentenceCase(
        case_id=scorer_gold,
        stratum="synthetic-private-stratum",
        split="development",
        source=source,
        expected_output=scorer_gold,
        gold_edits=(GoldEdit("spelling", 0, 0, scorer_gold, scorer_gold),),
        tags=(scorer_gold,),
    )

    with InstalledRunnerSession(
        python=python,
        runner=runner,
        vendored_stdio=vendored,
        working_directory=tmp_path / "work",
        timeout_seconds=1.0,
    ) as session:
        generic_runner = cast(Any, run_evaluation.run_installed_cases)
        runs, performance = generic_runner(
            (case,),
            session,
            config,
            repetitions=2,
        )

    requests = [json.loads(line) for line in process.stdin.payload.splitlines()]
    assert requests == [
        {
            "schema_version": 2,
            "request_id": 1,
            "operation": "analyze_sentence",
            "text": source,
        },
        {
            "schema_version": 2,
            "request_id": 2,
            "operation": "analyze_sentence",
            "text": source,
        },
    ]
    boundary = json.dumps(startup, default=str, ensure_ascii=False)
    assert scorer_gold not in boundary
    assert scorer_gold not in process.stdin.payload
    assert scorer_gold not in caplog.text
    assert runs[0].case.expected_output == scorer_gold
    assert performance.stable_repetitions == 2


def test_v2_scorer_gold_is_absent_from_actual_adapter_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    python = tmp_path / "python"
    runner = tmp_path / "runner.py"
    vendored = tmp_path / "run_stdio.sh"
    for path in (python, runner, vendored):
        path.write_text("synthetic", encoding="utf-8")
    source = "Zdanie widoczne dla analizatora."
    scorer_gold = "SCORER_GOLD_MUST_NOT_ENTER_ADAPTER_ERROR"
    process = _SyntheticProcess(scorer_gold + "\n")
    historical = "experiments.sentence_safety_gate.run_evaluation"
    monkeypatch.setattr(f"{historical}._installed_package_root", lambda *args: tmp_path)
    monkeypatch.setattr(f"{historical}._network_denial_prefix", lambda: ())
    monkeypatch.setattr(f"{historical}._wait_readable", lambda *args: True)
    monkeypatch.setattr(f"{historical}._swap_used_bytes", lambda: 0)
    monkeypatch.setattr(
        f"{historical}.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    config = load_gate_config(config_path)
    case = gate.SentenceCase(
        case_id=scorer_gold,
        stratum="synthetic-private-stratum",
        split="development",
        source=source,
        expected_output=scorer_gold,
        gold_edits=(GoldEdit("spelling", 0, 0, scorer_gold, scorer_gold),),
        tags=(scorer_gold,),
    )

    with InstalledRunnerSession(
        python=python,
        runner=runner,
        vendored_stdio=vendored,
        working_directory=tmp_path / "work",
        timeout_seconds=1.0,
    ) as session:
        with pytest.raises(ValueError) as captured:
            generic_runner = cast(Any, run_evaluation.run_installed_cases)
            generic_runner(
                (case,),
                session,
                config,
                repetitions=2,
            )

    assert scorer_gold not in str(captured.value)
    assert scorer_gold not in process.stdin.payload
    assert scorer_gold not in caplog.text
    assert json.loads(process.stdin.payload) == {
        "schema_version": 2,
        "request_id": 1,
        "operation": "analyze_sentence",
        "text": source,
    }


def _performance() -> PerformanceEvidence:
    return PerformanceEvidence(
        cold_e2e_ms=2.0,
        warm_in_process_p50_ms=1.0,
        warm_in_process_p95_ms=1.0,
        warm_e2e_p50_ms=2.0,
        warm_e2e_p95_ms=2.0,
        cases_per_second=500.0,
        characters_per_second=5_000.0,
        python_loaded_rss_bytes=100,
        child_loaded_rss_bytes=200,
        combined_loaded_rss_bytes=300,
        python_peak_rss_bytes=110,
        child_peak_rss_bytes=220,
        combined_peak_rss_bytes=330,
        swap_delta_bytes=0,
        socket_count=0,
        model_calls=0,
        process_start_count=1,
        stable_repetitions=2,
    )


def _observation(
    *,
    request_id: int,
    automatic: tuple[ObservedEdit, ...] = (),
    reviewable: tuple[ObservedEdit, ...] = (),
) -> RunnerObservation:
    return RunnerObservation(
        request_id=request_id,
        source_policy_version="1.2",
        automatic_edits=automatic,
        reviewable_edits=reviewable,
        analysis_finding_ids=tuple(
            item.finding_id for item in (*automatic, *reviewable)
        ),
        corrected_text="Syntetyczne zdanie.",
        selected_text="Syntetyczne zdanie.",
        suggestion_outcomes=(),
        elapsed_ms=1.0,
        python_rss_bytes=100,
        child_rss_bytes=200,
        combined_rss_bytes=300,
        python_peak_rss_bytes=110,
        child_peak_rss_bytes=220,
        combined_peak_rss_bytes=330,
        model_calls=0,
        process_start_count=1,
    )


def test_v2_aggregate_summary_retains_exact_counts_and_stability_digest() -> None:
    automatic = ObservedEdit(
        start=0,
        end=1,
        original="X",
        suggestion="S",
        category="spelling",
        source="rule:automatic",
        finding_id="automatic-1",
    )
    reviewable = ObservedEdit(
        start=0,
        end=1,
        original="X",
        suggestion="S",
        category="syntax",
        source="rule:reviewable",
        finding_id="reviewable-1",
    )
    cases = (
        gate.SentenceCase(
            "synthetic-a",
            "positive",
            "development",
            "Xyntetyczne zdanie.",
            "Syntetyczne zdanie.",
            (GoldEdit("spelling", 0, 1, "X", "S"),),
            (),
        ),
        gate.SentenceCase(
            "synthetic-b",
            "positive",
            "development",
            "Xyntetyczne zdanie.",
            "Syntetyczne zdanie.",
            (GoldEdit("syntax", 0, 1, "X", "S"),),
            (),
        ),
    )
    case_run = cast(Any, CaseRun)
    runs = (
        case_run(
            cases[0],
            _observation(request_id=1, automatic=(automatic,)),
            2.0,
            "a" * 64,
        ),
        case_run(
            cases[1],
            _observation(request_id=2, reviewable=(reviewable,)),
            2.0,
            "b" * 64,
        ),
    )

    summary = summarize_split(runs, _performance())

    assert summary["automatic"] == {
        "proposed_edits": 1,
        "true_positive_edits": 1,
        "false_positive_edits": 0,
        "false_negative_edits": 1,
        "precision": 1.0,
        "recall": 0.5,
        "correction_accuracy": 1.0,
    }
    assert summary["reviewable"] == {
        "proposed_edits": 1,
        "true_positive_edits": 1,
        "false_positive_edits": 0,
        "false_negative_edits": 1,
        "precision": 1.0,
        "recall": 0.5,
        "correction_accuracy": 1.0,
    }
    assert summary["categories"] == {
        "spelling": {
            "gold_edits": 1,
            "automatic": {
                "proposed_edits": 1,
                "true_positive_edits": 1,
                "false_positive_edits": 0,
                "false_negative_edits": 0,
                "precision": 1.0,
                "recall": 1.0,
            },
            "reviewable": {
                "proposed_edits": 0,
                "true_positive_edits": 0,
                "false_positive_edits": 0,
                "false_negative_edits": 1,
                "precision": None,
                "recall": 0.0,
            },
        },
        "syntax": {
            "gold_edits": 1,
            "automatic": {
                "proposed_edits": 0,
                "true_positive_edits": 0,
                "false_positive_edits": 0,
                "false_negative_edits": 1,
                "precision": None,
                "recall": 0.0,
            },
            "reviewable": {
                "proposed_edits": 1,
                "true_positive_edits": 1,
                "false_positive_edits": 0,
                "false_negative_edits": 0,
                "precision": 1.0,
                "recall": 1.0,
            },
        },
    }
    assert summary["sources"] == {
        "rule:automatic": {
            "proposed_edits": 1,
            "true_positive_edits": 1,
            "false_positive_edits": 0,
            "false_negative_edits": 1,
            "precision": 1.0,
            "recall": 0.5,
            "recall_denominator": "all_gold_edits",
        },
        "rule:reviewable": {
            "proposed_edits": 1,
            "true_positive_edits": 1,
            "false_positive_edits": 0,
            "false_negative_edits": 1,
            "precision": 1.0,
            "recall": 0.5,
            "recall_denominator": "all_gold_edits",
        },
    }
    assert summary["stable_repetition_digest"] == (
        "f6b2de54a53d855af46d889698e58e0269afddd2ccfd8d3ae572ac92bfdd0c6d"
    )
    assert "case_evidence" not in summary


def _qualifying_split(*, total_cases: int = 80) -> dict[str, object]:
    channel = {
        "proposed_edits": 1,
        "true_positive_edits": 1,
        "false_positive_edits": 0,
        "false_negative_edits": 0,
        "precision": 1.0,
        "recall": 1.0,
        "correction_accuracy": 1.0,
    }
    return {
        "total_cases": total_cases,
        "automatic": dict(channel),
        "reviewable": dict(channel),
        "structured_outcome_validity": 1.0,
        "protected_automatic_changes": 0,
        "protected_reviewable_findings": 0,
        "categories": {},
        "sources": {},
        "performance": _performance().as_dict(),
        "stable_repetition_digest": "d" * 64,
        "decision": {"qualified": True},
    }


def _qualifying_synthetic_report(
    *,
    configuration_sha256: str = "a" * 64,
    wheel_sha256: str = "b" * 64,
    sdist_sha256: str = "c" * 64,
    include_holdout: bool = False,
) -> dict[str, object]:
    split = _qualifying_split()
    return {
        "schema_version": 2,
        "experiment_id": "polis_sentence_safety_gate_v2_2026_08_02",
        "configuration_sha256": configuration_sha256,
        "environment": {
            "python_version": "3.13.5",
            "implementation": "CPython",
            "machine": "arm64",
            "operating_system": "synthetic",
            "platform_profile": "macos-arm64-v1",
            "source_policy_version": "1.2",
            "language_tool_version": "6.8",
            "language_tool_upstream_commit": (
                "e807fcde6a6506191e1470744d2345da28c26be6"
            ),
            "language_tool_manifest_sha256": (
                "d5871e8173addb96cc93e2f8ce6833737f08a20c4fc47e99596b4d82b8f3f6e8"
            ),
            "language_tool_bridge_sha256": (
                "c946c3ddfab36e45dab1716ca66ccfd61d0a6bfaa14b2e69926cb1b3da964c3d"
            ),
            "language_tool_runner_sha256": (
                "32b2d9bccdfccd1efc94939530de70f05040295861509b72b8b91752435b2fca"
            ),
            "language_tool_artifact_sha256": (
                "6959bbebad93c028552c21bae4d2524a0c08d09c1753c9a3fdf646ec1d645421"
            ),
            "language_tool_dependencies_sha256": (
                "de97bed1193abbed914ef23dd99757204aa3bcef29d3cfa8f1ea485178566a99"
            ),
            "model_calls_per_sentence": 0.0,
        },
        "artifact_audit": {
            "wheel_sha256": wheel_sha256,
            "sdist_sha256": sdist_sha256,
            "wheel_members": 2,
            "sdist_members": 2,
            "qualified": True,
        },
        "fallback": {
            "qualified": True,
            "status": "complete",
            "automatic_sources": ["rule:spelling.zeby"],
            "reviewable_sources": [],
            "model_calls": 0,
            "output_hash": "e" * 64,
        },
        "development": split,
        "holdout": _qualifying_split(total_cases=160) if include_holdout else None,
        "decision": {
            "qualified": include_holdout,
            "scope": "sentence_only",
        },
    }


def test_v2_report_is_aggregate_only() -> None:
    report = _qualifying_synthetic_report()

    validated = validate_privacy_safe_report(report)
    encoded = json.dumps(validated, ensure_ascii=False, sort_keys=True)

    for forbidden in (
        "case_id",
        "stratum",
        "expected_output",
        "original",
        "suggestion",
        "corrected_text",
        "selected_text",
        "raw_response",
    ):
        assert forbidden not in encoded


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("case_id", "synthetic-case"),
        ("stratum", "hard_negative"),
        ("original", "sekret"),
        ("raw_response", {"status": "complete"}),
        ("metadata", "/Users/private/research.json"),
    ],
)
def test_v2_report_rejects_case_text_raw_and_private_evidence(
    forbidden_key: str,
    forbidden_value: object,
) -> None:
    report = _qualifying_synthetic_report()
    development = report["development"]
    assert isinstance(development, dict)
    development[forbidden_key] = forbidden_value

    with pytest.raises(ValueError, match="report"):
        validate_privacy_safe_report(report)


@pytest.mark.parametrize(
    "private_path",
    [
        "prefix=file:///Users/private/research.json",
        "diagnostic path=/home/private/research.json",
        r"uri=C:\Users\private\research.json",
    ],
)
def test_v2_report_rejects_private_paths_embedded_in_values(
    private_path: str,
) -> None:
    report = _qualifying_synthetic_report()
    environment = report["environment"]
    assert isinstance(environment, dict)
    environment["operating_system"] = private_path

    with pytest.raises(ValueError, match="private path"):
        validate_privacy_safe_report(report)


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "Zdanie prywatne użytkownika.",
        "case_id_001",
        "file:///Users/private/research.json",
        "path=/home/private/research.json",
    ],
)
def test_v2_report_rejects_unsafe_category_keys(unsafe_key: str) -> None:
    report = _qualifying_synthetic_report()
    development = report["development"]
    assert isinstance(development, dict)
    development["categories"] = {
        unsafe_key: {
            "gold_edits": 0,
            "automatic": {
                "proposed_edits": 0,
                "true_positive_edits": 0,
                "false_positive_edits": 0,
                "false_negative_edits": 0,
                "precision": None,
                "recall": None,
            },
            "reviewable": {
                "proposed_edits": 0,
                "true_positive_edits": 0,
                "false_positive_edits": 0,
                "false_negative_edits": 0,
                "precision": None,
                "recall": None,
            },
        }
    }

    with pytest.raises(ValueError, match="category|private path"):
        validate_privacy_safe_report(report)


def _zero_source_metrics() -> dict[str, object]:
    return {
        "proposed_edits": 0,
        "true_positive_edits": 0,
        "false_positive_edits": 0,
        "false_negative_edits": 0,
        "precision": None,
        "recall": None,
        "recall_denominator": "all_gold_edits",
    }


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "Zdanie prywatne użytkownika.",
        "case_id_001",
        "file:///Users/private/research.json",
        "rule:path=/home/private/research.json",
        "rule:" + "a" * 200,
    ],
)
def test_v2_report_rejects_unsafe_source_keys(unsafe_key: str) -> None:
    report = _qualifying_synthetic_report()
    development = report["development"]
    assert isinstance(development, dict)
    development["sources"] = {unsafe_key: _zero_source_metrics()}

    with pytest.raises(ValueError, match="source|private path"):
        validate_privacy_safe_report(report)


def test_v2_report_rejects_unconfigured_safe_source_identifier(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    config = load_gate_config(config_path)
    report = _qualifying_synthetic_report()
    development = report["development"]
    assert isinstance(development, dict)
    development["sources"] = {"rule:case_id_001": _zero_source_metrics()}

    with pytest.raises(ValueError, match="configured"):
        validate_privacy_safe_report(report, config=config)


def _synthetic_authorization_inputs(
    tmp_path: Path,
) -> tuple[gate.GateConfig, FreezeInputs, dict[str, object], Path]:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    wheel = tmp_path / "artifact.whl"
    sdist = tmp_path / "artifact.tar.gz"
    wheel.write_bytes(b"synthetic wheel")
    sdist.write_bytes(b"synthetic sdist")
    inputs = FreezeInputs(
        files={"configuration": config_path, "wheel": wheel, "sdist": sdist},
        directories={},
    )
    report = _qualifying_synthetic_report(
        configuration_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        sdist_sha256=hashlib.sha256(sdist.read_bytes()).hexdigest(),
    )
    frozen_path = tmp_path / "frozen.json"
    frozen = {
        "configuration_sha256": report["configuration_sha256"],
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "sdist_sha256": hashlib.sha256(sdist.read_bytes()).hexdigest(),
        "development_report_sha256": hashlib.sha256(
            json.dumps(
                report,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
    }
    frozen_path.write_text(json.dumps(frozen), encoding="utf-8")
    return load_gate_config(config_path), inputs, report, frozen_path


def test_v2_development_decision_is_recomputed_before_holdout_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, inputs, report, frozen_path = _synthetic_authorization_inputs(tmp_path)
    development = report["development"]
    assert isinstance(development, dict)
    automatic = development["automatic"]
    assert isinstance(automatic, dict)
    automatic["precision"] = 0.0
    reserved = False

    def forbidden_reservation(*args: object, **kwargs: object) -> object:
        nonlocal reserved
        reserved = True
        raise AssertionError("failed development reached reservation")

    monkeypatch.setattr(run_evaluation, "preflight_release_capabilities", lambda: None)
    monkeypatch.setattr(run_evaluation, "reserve_holdout_once", forbidden_reservation)

    with pytest.raises(ValueError, match="development sentence gate"):
        run_evaluation.authorize_and_load_holdout(
            prior_report=report,
            config=config,
            frozen_path=frozen_path,
            marker_path=tmp_path / "holdout.started",
            inputs=inputs,
            corpus_path=tmp_path / "corpus.json",
            approval_path=tmp_path / "approval.json",
        )

    assert reserved is False


def test_v2_development_case_count_is_checked_before_holdout_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, inputs, report, frozen_path = _synthetic_authorization_inputs(tmp_path)
    development = report["development"]
    assert isinstance(development, dict)
    development["total_cases"] = 79
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    frozen["development_report_sha256"] = hashlib.sha256(
        json.dumps(
            report,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    frozen_path.write_text(json.dumps(frozen), encoding="utf-8")
    reserved = False

    def forbidden_reservation(*args: object, **kwargs: object) -> object:
        nonlocal reserved
        reserved = True
        raise AssertionError("invalid development count reached reservation")

    monkeypatch.setattr(run_evaluation, "preflight_release_capabilities", lambda: None)
    monkeypatch.setattr(run_evaluation, "reserve_holdout_once", forbidden_reservation)

    with pytest.raises(ValueError, match="exactly 80"):
        run_evaluation.authorize_and_load_holdout(
            prior_report=report,
            config=config,
            frozen_path=frozen_path,
            marker_path=tmp_path / "holdout.started",
            inputs=inputs,
            corpus_path=tmp_path / "corpus.json",
            approval_path=tmp_path / "approval.json",
        )

    assert reserved is False


def test_v2_authorization_reserves_before_loading_approved_holdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, inputs, report, frozen_path = _synthetic_authorization_inputs(tmp_path)
    marker = tmp_path / "holdout.started"
    approval = tmp_path / "approval.json"
    corpus = tmp_path / "corpus.json"
    observed: list[tuple[Path, Path, bool]] = []

    def synthetic_loader(
        corpus_path: Path,
        approval_path: Path,
        marker_path: Path,
        received_frozen: Path,
        received_inputs: FreezeInputs,
        *,
        reservation: object,
    ) -> tuple[gate.SentenceCase, ...]:
        assert received_frozen == frozen_path
        assert received_inputs is inputs
        assert reservation is not None
        observed.append((corpus_path, approval_path, marker_path.is_file()))
        return ()

    monkeypatch.setattr(run_evaluation, "preflight_release_capabilities", lambda: None)
    monkeypatch.setattr(
        run_evaluation,
        "load_reserved_holdout_sentences",
        synthetic_loader,
    )

    selected = run_evaluation.authorize_and_load_holdout(
        prior_report=report,
        config=config,
        frozen_path=frozen_path,
        marker_path=marker,
        inputs=inputs,
        corpus_path=corpus,
        approval_path=approval,
    )

    assert selected == ()
    assert observed == [(corpus, approval, True)]


def test_v2_verify_result_is_metadata_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, inputs, development_report, frozen_path = _synthetic_authorization_inputs(
        tmp_path
    )
    audit = development_report["artifact_audit"]
    assert isinstance(audit, dict)
    final_report = _qualifying_synthetic_report(
        configuration_sha256=str(development_report["configuration_sha256"]),
        wheel_sha256=str(audit["wheel_sha256"]),
        sdist_sha256=str(audit["sdist_sha256"]),
        include_holdout=True,
    )
    final_report["artifact_audit"] = dict(audit)
    output = Path("/Users/private/final-report.json")
    marker = tmp_path / "holdout.started"
    marker.write_text(frozen_path.read_text(encoding="utf-8"), encoding="utf-8")
    unavailable_calls: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        unavailable_calls.append("called")
        raise AssertionError("metadata verification opened corpus evidence")

    monkeypatch.setattr(run_evaluation, "load_gate_config", lambda path: config)
    monkeypatch.setattr(
        run_evaluation,
        "_distribution_paths",
        lambda path: (Path("wheel"), Path("sdist")),
    )
    monkeypatch.setattr(
        run_evaluation,
        "audit_release_artifacts",
        lambda *args: run_evaluation.ArtifactAudit("b" * 64, "c" * 64, 2, 2, True),
    )
    monkeypatch.setattr(run_evaluation, "_freeze_inputs", lambda *args: inputs)
    monkeypatch.setattr(run_evaluation, "_read_report", lambda path: final_report)
    monkeypatch.setattr(run_evaluation, "load_development_sentences", forbidden)
    monkeypatch.setattr(run_evaluation, "load_reserved_holdout_sentences", forbidden)
    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", forbidden)

    result = run_evaluation.main(
        [
            "--verify-result",
            "--config",
            os.fspath(tmp_path / "config.json"),
            "--dist",
            os.fspath(tmp_path / "dist"),
            "--output",
            os.fspath(output),
            "--frozen",
            os.fspath(frozen_path),
            "--holdout-marker",
            os.fspath(marker),
        ]
    )

    assert result == 0
    assert unavailable_calls == []
    assert capsys.readouterr().out == "sentence safety v2 result metadata verified\n"


def test_v2_verify_development_stdout_never_echoes_private_output_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, inputs, report, frozen_path = _synthetic_authorization_inputs(tmp_path)
    output = Path("/Users/private/development-report.json")
    monkeypatch.setattr(run_evaluation, "load_gate_config", lambda path: config)
    monkeypatch.setattr(
        run_evaluation,
        "_distribution_paths",
        lambda path: (Path("wheel"), Path("sdist")),
    )
    monkeypatch.setattr(
        run_evaluation,
        "audit_release_artifacts",
        lambda *args: run_evaluation.ArtifactAudit(
            str(report["artifact_audit"]["wheel_sha256"]),  # type: ignore[index]
            str(report["artifact_audit"]["sdist_sha256"]),  # type: ignore[index]
            2,
            2,
            True,
        ),
    )
    monkeypatch.setattr(run_evaluation, "_freeze_inputs", lambda *args: inputs)
    monkeypatch.setattr(run_evaluation, "_read_report", lambda path: report)
    monkeypatch.setattr(
        run_evaluation,
        "release_platform_profile",
        lambda: "macos-arm64-v1",
    )
    monkeypatch.setattr(run_evaluation, "_validate_frozen_runtime", lambda config: None)
    monkeypatch.setattr(
        run_evaluation,
        "_validate_vendored_stdio",
        lambda path, config: path,
    )

    result = run_evaluation.main(
        [
            "--verify-development",
            "--config",
            os.fspath(tmp_path / "config.json"),
            "--dist",
            os.fspath(tmp_path / "dist"),
            "--vendored-stdio",
            os.fspath(tmp_path / "run_stdio.sh"),
            "--output",
            os.fspath(output),
            "--freeze",
            os.fspath(frozen_path),
        ]
    )

    assert result == 0
    stdout = capsys.readouterr().out
    assert stdout == "sentence safety v2 development metadata verified\n"
    assert "/Users/" not in stdout


def test_v2_final_report_requires_exact_aggregate_holdout_count(
    tmp_path: Path,
) -> None:
    config, inputs, development_report, _ = _synthetic_authorization_inputs(tmp_path)
    final_report = dict(development_report)
    holdout = _qualifying_split(total_cases=159)
    final_report["holdout"] = holdout
    final_report["decision"] = {"qualified": True, "scope": "sentence_only"}

    with pytest.raises(ValueError, match="exactly 160"):
        run_evaluation._validate_final_report(final_report, config, inputs)


def test_v2_freeze_inputs_include_approval_and_evaluated_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    config = load_gate_config(config_path)
    wheel = tmp_path / "synthetic.whl"
    sdist = tmp_path / "synthetic.tar.gz"
    evaluated_source = tmp_path / "evaluated_source.json"
    for path in (wheel, sdist, evaluated_source):
        path.write_text("synthetic", encoding="utf-8")
    monkeypatch.setattr(run_evaluation, "_ROOT", tmp_path)
    monkeypatch.setattr(run_evaluation, "_EVALUATED_SOURCE", evaluated_source)

    inputs = run_evaluation._freeze_inputs(config_path, wheel, sdist, config)

    assert inputs.files["corpus_json"] == tmp_path / config.corpus_json_path
    assert inputs.files["corpus_xml"] == tmp_path / config.corpus_xml_path
    assert inputs.files["corpus_approval"] == (tmp_path / config.corpus_approval_path)
    assert inputs.files["evaluated_source"] == evaluated_source


def test_v2_fallback_evidence_persists_closed_failed_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()), encoding="utf-8")
    config = load_gate_config(config_path)

    class FailedSession:
        def __enter__(self) -> FailedSession:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def exchange(
            self, request_id: int, text: str
        ) -> tuple[dict[str, object], float]:
            del request_id, text
            return (
                {
                    "schema_version": 2,
                    "request_id": 1,
                    "status": "invalid_output",
                    "error_code": "runner.analysis_failed",
                },
                1.0,
            )

    monkeypatch.setattr(
        run_evaluation,
        "InstalledRunnerSession",
        lambda **kwargs: FailedSession(),
    )

    evidence = run_evaluation._fallback_evidence(
        tmp_path / "python",
        tmp_path,
        config,
        timeout_seconds=1.0,
    )

    assert evidence["qualified"] is False
    assert evidence["status"] == "failed"
    assert evidence["automatic_sources"] == []
    assert evidence["reviewable_sources"] == []
    assert evidence["model_calls"] == 0
    report = _qualifying_synthetic_report()
    report["fallback"] = evidence
    assert validate_privacy_safe_report(report) is report


_RETAINED_HISTORY_SHA256 = {
    "tests/fixtures/evaluation/polish_correction_corpus_v3.json": (
        "bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2"
    ),
    "tests/fixtures/evaluation/polish_correction_corpus_v3.xml": (
        "32d99cf82609ff43c034f008c64dbb1b3c19f04fb77ef89c834ff433ccf59e3c"
    ),
    "tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json": (
        "921ce0accd120e443a9131f192b8669484d4dd24bf18898fbd2ebcafbe1a87d9"
    ),
    "tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml": (
        "f2fcefef2172efcf3e27338bacc106230cde48b37c3c6989a4803bddc8dcc908"
    ),
    "tests/fixtures/evaluation/polish_correction_safety_corpus_v1.approval.json": (
        "8f0bb298c32f3b1c58dcfe008ad5e21da6eed851237839cde14c433cfa2c8559"
    ),
    "experiments/sentence_safety_gate/config.json": (
        "6c637167d7cb77003db28e6072009a2606a45597dfee1ec3173f31c2dea87fc6"
    ),
    "experiments/sentence_safety_gate/evaluated_source.json": (
        "b1bd4fda10301c06dbe5fd6c0397f88c1acf44016652299de854a4001acd5ab9"
    ),
    "experiments/sentence_safety_gate/frozen_gate.json": (
        "9fe74303924707df59d44a654877cec074219ea6f3314d2a60c993052d8ab736"
    ),
    "experiments/sentence_safety_gate/holdout.started": (
        "198371e64acb4fe04c8b2ae962e172b37e61ef3149b2d832c97175bde10f4d82"
    ),
    "experiments/sentence_safety_gate/report.json": (
        "69c88ac8370ff9d604a4669b674dc242954c6b28cc7c6e7d60ade6764f8a1c99"
    ),
    "experiments/sentence_safety_gate/README.md": (
        "e32140dd11b9324e043da4b8bddc6fbe2222ef35327f6c6d37246d52c6afa3ee"
    ),
    "docs/performance-baseline.md": (
        "cebb7ce95cecbb57d5383b1dbae220f10358c69ed7f09196292a8f9187dd09f7"
    ),
    "docs/quality-baseline.md": (
        "6723ca24b6ba18eb1ebbf0aee1ead603207008e7f84439866e69b7835a2aaf97"
    ),
}


def _byte_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_PRE_EVALUATION_BASE = "3035eb201f48bd84a5ada364ae41a96293259e50"
_PRE_EVALUATION_TREE = "5162007cfc9eac13aed415256ee698e5d0c5de4b"
_PRE_EVALUATION_PATCH = Path(
    "experiments/sentence_safety_gate_v2/pre_evaluation_inputs.patch"
)
_PRE_EVALUATION_PATCH_SHA256 = (
    "32a5419baf4bf673bcfb181b19e5533886e57ee71acc0089770db06969144aa2"
)
_PRE_EVALUATION_CHANGES = {
    "docs/evaluation-dataset.md": {
        "status": "M",
        "mode": "100644",
        "blob": "7898fba03e2b93a2a955c3724b0779a9b6d5adaa",
    },
    "docs/limitations.md": {
        "status": "M",
        "mode": "100644",
        "blob": "ae2688870467cb5d3439d386334ffca31f1d5081",
    },
    "docs/llm-quality-gates.md": {
        "status": "M",
        "mode": "100644",
        "blob": "a5a685f11ec364dc28676b3c98e141c0e5406afd",
    },
    "docs/project/ROADMAP.md": {
        "status": "M",
        "mode": "100644",
        "blob": "00443efae0cb403d400ee0efc8ad760a6bd0b73b",
    },
    "docs/superpowers/plans/2026-08-02-issue-146-sentence-safety-gate-v2.md": {
        "status": "A",
        "mode": "100644",
        "blob": "dcf09ad56393223b1b4835dc7c292845405210eb",
    },
    "docs/superpowers/specs/2026-08-02-issue-146-sentence-safety-gate-v2-design.md": {
        "status": "A",
        "mode": "100644",
        "blob": "dd6b2febbd990bad39eaf4435333bbf2f146e091",
    },
    "experiments/sentence_safety_gate_v2/README.md": {
        "status": "A",
        "mode": "100644",
        "blob": "6597d060fe14330ccb896d26c40325b3113d5071",
    },
    "experiments/sentence_safety_gate_v2/__init__.py": {
        "status": "A",
        "mode": "100644",
        "blob": "84fba0d67f022b1e9db5491ad58c1d5cf11951c2",
    },
    "experiments/sentence_safety_gate_v2/config.json": {
        "status": "A",
        "mode": "100644",
        "blob": "51d67c2988c9b6156e29ca0858fb2ffcc9ad47cb",
    },
    "experiments/sentence_safety_gate_v2/gate.py": {
        "status": "A",
        "mode": "100644",
        "blob": "be2fc4bf16721454b1947d90057120dc24570428",
    },
    "experiments/sentence_safety_gate_v2/run_evaluation.py": {
        "status": "A",
        "mode": "100644",
        "blob": "f54e0c848c570b2dab7bce76928b67b17478c601",
    },
    "tests/test_sentence_safety_gate_v2.py": {
        "status": "A",
        "mode": "100644",
        "blob": "b149a2c702311f9a5cc5da6926c2d8f1c5bdbfb1",
    },
}


def _reconstructed_pre_evaluation_tree(
    tmp_path: Path,
    *,
    repository: Path | None = None,
    patch_path: Path | None = None,
) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    index_path = tmp_path / "isolated-git-index"
    repository = Path.cwd() if repository is None else repository
    patch_path = (
        Path.cwd() / _PRE_EVALUATION_PATCH if patch_path is None else patch_path
    )
    assert _byte_sha256(patch_path) == _PRE_EVALUATION_PATCH_SHA256
    environment = os.environ.copy()
    environment["GIT_INDEX_FILE"] = os.fspath(index_path)

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"isolated git {' '.join(arguments)} failed: {completed.stderr.strip()}"
            )
        return completed.stdout.strip()

    git("read-tree", _PRE_EVALUATION_BASE)
    git("apply", "--cached", "--unidiff-zero", os.fspath(patch_path.resolve()))

    status_lines = git(
        "diff", "--cached", "--name-status", "--no-renames", _PRE_EVALUATION_BASE
    ).splitlines()
    statuses = {
        path: status for status, path in (line.split("\t", 1) for line in status_lines)
    }
    assert statuses == {
        path: str(expected["status"])
        for path, expected in _PRE_EVALUATION_CHANGES.items()
    }

    for path, expected in _PRE_EVALUATION_CHANGES.items():
        metadata, actual_path = git("ls-files", "--stage", "--", path).split("\t", 1)
        mode, blob, stage = metadata.split()
        assert actual_path == path
        assert stage == "0"
        assert mode == expected["mode"]
        assert blob == expected["blob"]

    return git("write-tree")


def test_v2_retained_historical_artifacts_preserve_exact_bytes() -> None:
    assert {
        path: _byte_sha256(Path(path)) for path in _RETAINED_HISTORY_SHA256
    } == _RETAINED_HISTORY_SHA256


def test_v2_real_config_freezes_every_runtime_and_source_identity(
    tmp_path: Path,
) -> None:
    config_path = Path("experiments/sentence_safety_gate_v2/config.json")
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    config = load_gate_config(config_path)

    assert set(raw) == {
        "schema_version",
        "experiment_id",
        "sentence_only",
        "platform_profile",
        "source_policy_version",
        "corpus",
        "sources",
        "language_tool",
        "gates",
    }
    assert config.experiment_id == "polis_sentence_safety_gate_v2_2026_08_02"
    assert config.platform_profile == "macos-arm64-v1"
    assert config.source_policy_version == "1.2"
    assert raw["corpus"] == {
        "id": "polis_polish_correction_safety_corpus_v2",
        "candidate_digest": (
            "c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53"
        ),
        "frozen_digest": (
            "53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29"
        ),
        "json_path": (
            "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.json"
        ),
        "json_sha256": (
            "9c9b1cf1103dfaa096dd113948e0b47bfb26d5722ebe5edce1250e9889a59f69"
        ),
        "xml_path": (
            "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.xml"
        ),
        "xml_sha256": (
            "676bc630e6644aecd30daf166c50ebe9c8558fd5714e74081722b0c4123ecb3a"
        ),
        "approval_path": (
            "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.approval.json"
        ),
        "approval_sha256": (
            "8a21b3d291eb0542b484db318350678bde39cbf549451eb6f35cfd995ba39d77"
        ),
    }
    assert raw["sources"] == {
        "automatic": [
            "rule:agreement.copula",
            "rule:languagetool.pl",
            "rule:spelling.jestes",
            "rule:spelling.wlasnie",
            "rule:spelling.zeby",
            "rule:syntax.comma_space",
            "rule:syntax.list_space",
            "rule:syntax.quote_space",
            "rule:syntax.sentence_space",
        ],
        "reviewable": [
            "rule:languagetool.contextual_inflection",
            "rule:syntax.missing_correlative",
            "rule:syntax.missing_reflexive",
        ],
    }
    assert raw["language_tool"] == {
        "version": "6.8",
        "upstream_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
        "manifest_sha256": (
            "d5871e8173addb96cc93e2f8ce6833737f08a20c4fc47e99596b4d82b8f3f6e8"
        ),
        "bridge_sha256": (
            "c946c3ddfab36e45dab1716ca66ccfd61d0a6bfaa14b2e69926cb1b3da964c3d"
        ),
        "runner_sha256": (
            "32b2d9bccdfccd1efc94939530de70f05040295861509b72b8b91752435b2fca"
        ),
        "artifact_sha256": (
            "6959bbebad93c028552c21bae4d2524a0c08d09c1753c9a3fdf646ec1d645421"
        ),
        "dependencies_sha256": (
            "de97bed1193abbed914ef23dd99757204aa3bcef29d3cfa8f1ea485178566a99"
        ),
    }
    assert raw["gates"] == _valid_config()["gates"]

    identity_mutations = (
        ("experiment_id", "changed"),
        ("platform_profile", "changed"),
        ("source_policy_version", "1.1"),
        ("corpus.id", "changed"),
        ("corpus.candidate_digest", "0" * 64),
        ("corpus.frozen_digest", "0" * 64),
        ("corpus.json_path", "changed.json"),
        ("corpus.json_sha256", "0" * 64),
        ("corpus.xml_path", "changed.xml"),
        ("corpus.xml_sha256", "0" * 64),
        ("corpus.approval_path", "changed.approval.json"),
        ("corpus.approval_sha256", "0" * 64),
        ("sources.automatic", ["rule:changed"]),
        ("sources.reviewable", ["rule:changed"]),
        ("language_tool.version", "changed"),
        ("language_tool.upstream_commit", "changed"),
        ("language_tool.manifest_sha256", "0" * 64),
        ("language_tool.bridge_sha256", "0" * 64),
        ("language_tool.runner_sha256", "0" * 64),
        ("language_tool.artifact_sha256", "0" * 64),
        ("language_tool.dependencies_sha256", "0" * 64),
        ("gates.automatic_minimum_precision", 0.99),
        ("gates.automatic_minimum_correction_accuracy", 0.99),
        ("gates.reviewable_minimum_precision", 0.89),
        ("gates.minimum_structured_outcome_validity", 0.99),
        ("gates.maximum_protected_automatic_changes", 1),
        ("gates.maximum_protected_reviewable_findings", 1),
        ("gates.maximum_warm_in_process_p95_ms", 101),
        ("gates.maximum_warm_e2e_p95_ms", 501),
        ("gates.maximum_combined_peak_rss_bytes", 1_073_741_825),
        ("gates.maximum_swap_delta_bytes", 1),
        ("gates.maximum_socket_count", 1),
        ("gates.required_model_calls", 1),
        ("gates.required_process_start_count", 2),
        ("gates.required_stable_repetitions", 3),
    )
    for dotted_name, changed in identity_mutations:
        mutated = json.loads(json.dumps(raw))
        target = mutated
        names = dotted_name.split(".")
        for name in names[:-1]:
            target = target[name]
        target[names[-1]] = changed
        mutated_path = tmp_path / f"{dotted_name.replace('.', '-')}.json"
        mutated_path.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="configuration|identity|source|policy"):
            load_gate_config(mutated_path)

    for section in ("corpus", "sources", "language_tool", "gates"):
        missing = json.loads(json.dumps(raw))
        missing[section].pop(next(iter(missing[section])))
        missing_path = tmp_path / f"missing-{section}.json"
        missing_path.write_text(json.dumps(missing), encoding="utf-8")
        with pytest.raises(ValueError, match="exactly the frozen keys"):
            load_gate_config(missing_path)

        extra = json.loads(json.dumps(raw))
        extra[section]["unexpected"] = True
        extra_path = tmp_path / f"extra-{section}.json"
        extra_path.write_text(json.dumps(extra), encoding="utf-8")
        with pytest.raises(ValueError, match="exactly the frozen keys"):
            load_gate_config(extra_path)


def test_v2_real_config_evaluated_source_binds_protected_history(
    tmp_path: Path,
) -> None:
    manifest_path = Path("experiments/sentence_safety_gate_v2/evaluated_source.json")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert raw["schema_version"] == 4
    assert raw["issue"] == 146
    assert raw["base_commit"] == _PRE_EVALUATION_BASE
    assert raw["staged_tree"] == _PRE_EVALUATION_TREE
    assert raw["staged_tree"] == _reconstructed_pre_evaluation_tree(tmp_path)
    assert raw["pre_evaluation_patch"] == {
        "path": os.fspath(_PRE_EVALUATION_PATCH),
        "sha256": _PRE_EVALUATION_PATCH_SHA256,
        "direction": "forward",
        "unidiff_zero": True,
    }
    assert raw["pre_evaluation_changes"] == _PRE_EVALUATION_CHANGES
    assert list(raw["pre_evaluation_changes"]) == sorted(_PRE_EVALUATION_CHANGES)
    assert set(raw) == {
        "schema_version",
        "issue",
        "base_commit",
        "staged_tree",
        "pre_evaluation_patch",
        "pre_evaluation_changes",
        "files",
        "protected_history",
        "protected_history_manifest_sha256",
    }
    assert set(raw["pre_evaluation_patch"]) == {
        "path",
        "sha256",
        "direction",
        "unidiff_zero",
    }
    assert raw["files"] == {
        "evaluator": {
            "path": "experiments/sentence_safety_gate_v2/run_evaluation.py",
            "sha256": (
                "bf2806e84f6e732df569173fa62f271a760bc40c057e8707f4bc9ce6bf1351cf"
            ),
        },
        "gate": {
            "path": "experiments/sentence_safety_gate_v2/gate.py",
            "sha256": _byte_sha256(Path("experiments/sentence_safety_gate_v2/gate.py")),
        },
        "installed_runner": {
            "path": "scripts/run_sentence_safety_case.py",
            "sha256": _byte_sha256(Path("scripts/run_sentence_safety_case.py")),
        },
        "analyzer_source_policy": {
            "path": "src/polis/analyzer.py",
            "sha256": _byte_sha256(Path("src/polis/analyzer.py")),
        },
        "corpus_json": {
            "path": (
                "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.json"
            ),
            "sha256": (
                "9c9b1cf1103dfaa096dd113948e0b47bfb26d5722ebe5edce1250e9889a59f69"
            ),
        },
        "corpus_xml": {
            "path": (
                "tests/fixtures/evaluation/polish_correction_safety_corpus_v2.xml"
            ),
            "sha256": (
                "676bc630e6644aecd30daf166c50ebe9c8558fd5714e74081722b0c4123ecb3a"
            ),
        },
        "corpus_approval": {
            "path": (
                "tests/fixtures/evaluation/"
                "polish_correction_safety_corpus_v2.approval.json"
            ),
            "sha256": (
                "8a21b3d291eb0542b484db318350678bde39cbf549451eb6f35cfd995ba39d77"
            ),
        },
        "configuration": {
            "path": "experiments/sentence_safety_gate_v2/config.json",
            "sha256": _byte_sha256(
                Path("experiments/sentence_safety_gate_v2/config.json")
            ),
        },
    }
    assert raw["protected_history"] == _RETAINED_HISTORY_SHA256
    protected_payload = json.dumps(
        _RETAINED_HISTORY_SHA256,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert (
        raw["protected_history_manifest_sha256"]
        == hashlib.sha256(protected_payload).hexdigest()
    )


def test_v2_pre_evaluation_reconstruction_ignores_alternate_head(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "alternate-repository"
    cloned = subprocess.run(
        (
            "git",
            "clone",
            "--shared",
            "--quiet",
            os.fspath(Path.cwd()),
            os.fspath(repository),
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert cloned.returncode == 0, cloned.stderr

    (repository / "upstream-added-after-evaluation.txt").write_text(
        "synthetic upstream path\n", encoding="utf-8"
    )
    for arguments in (
        ("add", "upstream-added-after-evaluation.txt"),
        (
            "-c",
            "user.name=Polis test",
            "-c",
            "user.email=polis-test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "synthetic alternate head",
        ),
    ):
        completed = subprocess.run(
            ("git", *arguments),
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    assert (
        _reconstructed_pre_evaluation_tree(
            tmp_path / "alternate-index",
            repository=repository,
            patch_path=repository / _PRE_EVALUATION_PATCH,
        )
        == _PRE_EVALUATION_TREE
    )


def test_v2_documentation_freezes_the_irreversible_sentence_only_boundary() -> None:
    readme = Path("experiments/sentence_safety_gate_v2/README.md").read_text(
        encoding="utf-8"
    )
    documentation = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path("docs/evaluation-dataset.md"),
            Path("docs/llm-quality-gates.md"),
            Path("docs/limitations.md"),
            Path("docs/project/ROADMAP.md"),
        )
    )
    combined = readme + documentation

    for command in ("--preflight", "--development", "--verify-development"):
        assert command in readme
    assert readme.count("--holdout") >= 1
    for required in (
        "#146",
        "sentence-only",
        "unchanged gates",
        "optional research",
        "autonomous authorization",
        "independent review",
        "without prompting",
        "permanently",
        "no recovery command",
    ):
        assert required in combined
    assert "does not qualify a production model" in combined
    assert "does not qualify paragraph behavior" in combined

    for required in (
        "80 development cases",
        "two stable repetitions",
        "not qualified",
        "7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141",
        "no frozen gate",
        "holdout was not reserved, materialized, or run",
        "#76 remains open",
        "Task 6 is forbidden",
        "post-evaluation audit tests",
        "pre-evaluation test blob",
    ):
        assert required in combined


def test_v2_negative_development_report_is_aggregate_and_immutable() -> None:
    report_path = Path("experiments/sentence_safety_gate_v2/report.json")
    assert _byte_sha256(report_path) == (
        "7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    config = load_gate_config(Path("experiments/sentence_safety_gate_v2/config.json"))

    validate_privacy_safe_report(report, config=config)
    assert report["decision"] == {"qualified": False, "scope": "sentence_only"}
    assert report["holdout"] is None
    assert report["development"]["total_cases"] == 80
    assert report["development"]["performance"]["stable_repetitions"] == 2
    assert report["development"]["decision"] == {"qualified": False}
    assert not Path("experiments/sentence_safety_gate_v2/frozen_gate.json").exists()
    assert not Path("experiments/sentence_safety_gate_v2/holdout.started").exists()


def test_v2_repository_quality_tools_include_the_experiment_package() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert (
        "experiments/sentence_safety_gate_v2/**/*.py"
        in project["tool"]["ruff"]["include"]
    )
    assert "experiments/sentence_safety_gate_v2" in project["tool"]["mypy"]["files"]


def test_v2_real_marker_is_absent_before_development() -> None:
    assert not Path("experiments/sentence_safety_gate_v2/holdout.started").exists()
