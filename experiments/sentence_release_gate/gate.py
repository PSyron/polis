"""Closed contracts and split-safe data loading for the sentence release gate."""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.sax
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from xml.sax.handler import ContentHandler
from xml.sax.xmlreader import AttributesImpl

from polis.evaluation.correction_corpus import (
    CorrectionCorpusCase,
    load_correction_corpus_json,
    select_cases_for_purpose,
)

Split = Literal["development", "holdout"]

_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "sentence_only",
        "source_policy_version",
        "corpus",
        "sources",
        "language_tool",
        "gates",
    }
)
_CORPUS_KEYS = frozenset({"json_path", "json_sha256", "xml_path", "xml_sha256"})
_SOURCE_KEYS = frozenset({"automatic", "reviewable"})
_LANGUAGE_TOOL_KEYS = frozenset(
    {
        "version",
        "upstream_commit",
        "manifest_sha256",
        "bridge_sha256",
        "runner_sha256",
        "artifact_sha256",
        "dependencies_sha256",
    }
)
_GATE_KEYS = frozenset(
    {
        "automatic_minimum_precision",
        "automatic_minimum_correction_accuracy",
        "reviewable_minimum_precision",
        "minimum_structured_outcome_validity",
        "maximum_protected_automatic_changes",
        "maximum_protected_reviewable_findings",
        "maximum_warm_in_process_p95_ms",
        "maximum_warm_e2e_p95_ms",
        "maximum_combined_peak_rss_bytes",
        "maximum_swap_delta_bytes",
        "maximum_socket_count",
        "required_model_calls",
        "required_process_start_count",
        "required_stable_repetitions",
    }
)


@dataclass(frozen=True, slots=True)
class GoldEdit:
    """One scorer-only exact edit against the source sentence."""

    category: str
    start: int
    end: int
    original: str
    suggestion: str

    @property
    def exact_key(self) -> tuple[int, int, str, str]:
        return (self.start, self.end, self.original, self.suggestion)


@dataclass(frozen=True, slots=True)
class ObservedEdit:
    """One public finding reduced to scorer-relevant edit evidence."""

    start: int
    end: int
    original: str
    suggestion: str
    category: str
    source: str
    finding_id: str

    @property
    def exact_key(self) -> tuple[int, int, str, str]:
        return (self.start, self.end, self.original, self.suggestion)


@dataclass(frozen=True, slots=True)
class EditCounts:
    """Exact edit contingency counts."""

    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def proposed(self) -> int:
        return self.true_positive + self.false_positive

    @property
    def precision(self) -> float:
        return self.true_positive / self.proposed if self.proposed else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0


@dataclass(frozen=True, slots=True)
class RunnerObservation:
    """One structurally validated installed-runner result."""

    request_id: int
    automatic_edits: tuple[ObservedEdit, ...]
    reviewable_edits: tuple[ObservedEdit, ...]
    analysis_finding_ids: tuple[str, ...]
    corrected_text: str
    selected_text: str
    suggestion_outcomes: tuple[Mapping[str, object], ...]
    elapsed_ms: float
    python_rss_bytes: int
    child_rss_bytes: int
    combined_rss_bytes: int
    python_peak_rss_bytes: int
    child_peak_rss_bytes: int
    combined_peak_rss_bytes: int
    model_calls: int
    process_start_count: int


@dataclass(frozen=True, slots=True)
class FreezeInputs:
    """Every file and directory whose bytes define one holdout run."""

    files: Mapping[str, Path]
    directories: Mapping[str, Path]

    def __post_init__(self) -> None:
        names = (*self.files, *self.directories)
        if not names or len(names) != len(set(names)):
            raise ValueError("freeze input names must be non-empty and unique")
        if any(re.fullmatch(r"[a-z][a-z0-9_]*", name) is None for name in names):
            raise ValueError("freeze input name is invalid")


@dataclass(frozen=True, slots=True)
class FrozenGate:
    """Canonical SHA-256 identities committed before holdout access."""

    hashes: Mapping[str, str]
    development_report_sha256: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = dict(self.hashes)
        if self.development_report_sha256 is not None:
            payload["development_report_sha256"] = self.development_report_sha256
        return payload


@dataclass(frozen=True, slots=True)
class SentenceCase:
    """One reviewed sentence retained by the repository-side scorer."""

    case_id: str
    stratum: str
    split: Split
    unit: Literal["sentence"]
    source: str
    expected_output: str
    gold_edits: tuple[GoldEdit, ...]
    tags: tuple[str, ...]

    @property
    def protected_negative(self) -> bool:
        return self.stratum == "hard_negative"


@dataclass(frozen=True, slots=True)
class QualityGates:
    automatic_minimum_precision: float
    automatic_minimum_correction_accuracy: float
    reviewable_minimum_precision: float
    minimum_structured_outcome_validity: float
    maximum_protected_automatic_changes: int
    maximum_protected_reviewable_findings: int
    maximum_warm_in_process_p95_ms: float
    maximum_warm_e2e_p95_ms: float
    maximum_combined_peak_rss_bytes: int
    maximum_swap_delta_bytes: int
    maximum_socket_count: int
    required_model_calls: int
    required_process_start_count: int
    required_stable_repetitions: int


@dataclass(frozen=True, slots=True)
class GateConfig:
    schema_version: int
    experiment_id: str
    sentence_only: bool
    source_policy_version: str
    corpus_json_path: str
    corpus_sha256: str
    corpus_xml_path: str
    corpus_xml_sha256: str
    automatic_sources: frozenset[str]
    reviewable_sources: frozenset[str]
    language_tool: Mapping[str, str]
    gates: QualityGates


def sha256_path(path: Path) -> str:
    """Return a lowercase SHA-256 digest for one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gate_config(path: Path) -> GateConfig:
    """Load the exact, closed release-gate configuration."""

    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "configuration")
    _exact_keys(raw, _TOP_LEVEL_KEYS, "configuration")
    if raw["schema_version"] != 1:
        raise ValueError("configuration schema_version must be 1")
    if raw["sentence_only"] is not True:
        raise ValueError("configuration must be sentence-only")
    if raw["source_policy_version"] != "1.1":
        raise ValueError("source policy version must be 1.1")

    corpus = _mapping(raw["corpus"], "corpus configuration")
    sources = _mapping(raw["sources"], "source configuration")
    language_tool = _mapping(raw["language_tool"], "LanguageTool configuration")
    gates = _mapping(raw["gates"], "quality gates")
    _exact_keys(corpus, _CORPUS_KEYS, "corpus configuration")
    _exact_keys(sources, _SOURCE_KEYS, "source configuration")
    _exact_keys(language_tool, _LANGUAGE_TOOL_KEYS, "LanguageTool configuration")
    _exact_keys(gates, _GATE_KEYS, "quality gates")

    automatic = _string_set(sources["automatic"], "automatic sources")
    reviewable = _string_set(sources["reviewable"], "reviewable sources")
    if not automatic or not reviewable or automatic & reviewable:
        raise ValueError("source channels must be non-empty and disjoint")
    for name, value in language_tool.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"LanguageTool {name} must be a non-empty string")
        if name.endswith("_sha256") and not _is_sha256(value):
            raise ValueError(f"LanguageTool {name} must be SHA-256")

    return GateConfig(
        schema_version=1,
        experiment_id=_string(raw["experiment_id"], "experiment id"),
        sentence_only=True,
        source_policy_version="1.1",
        corpus_json_path=_string(corpus["json_path"], "corpus JSON path"),
        corpus_sha256=_digest(corpus["json_sha256"], "corpus JSON hash"),
        corpus_xml_path=_string(corpus["xml_path"], "corpus XML path"),
        corpus_xml_sha256=_digest(corpus["xml_sha256"], "corpus XML hash"),
        automatic_sources=automatic,
        reviewable_sources=reviewable,
        language_tool={key: cast(str, value) for key, value in language_tool.items()},
        gates=_quality_gates(gates),
    )


class _DevelopmentSentenceHandler(ContentHandler):
    """Materialize reviewed development sentences while discarding other text."""

    def __init__(self, on_materialized: Callable[[str], None] | None) -> None:
        super().__init__()
        self.cases: list[SentenceCase] = []
        self._on_materialized = on_materialized
        self._selected = False
        self._case: dict[str, object] | None = None
        self._field: str | None = None
        self._characters: list[str] = []

    def startElement(self, name: str, attrs: AttributesImpl) -> None:  # noqa: N802
        if name == "case":
            self._selected = (
                attrs.get("split") == "development" and attrs.get("unit") == "sentence"
            )
            if self._selected:
                self._case = {
                    "id": attrs.get("id"),
                    "stratum": attrs.get("stratum"),
                    "split": "development",
                    "unit": "sentence",
                    "tags": [],
                    "edits": [],
                    "reviewed": False,
                }
            return
        if not self._selected or self._case is None:
            return
        if name in {"input", "expected_output", "tag"}:
            self._field = name
            self._characters = []
        elif name == "review":
            self._case["reviewed"] = (
                attrs.get("status") == "human-reviewed"
                and attrs.get("reviewer") == "Paweł Cyroń"
            )
        elif name == "edit":
            edits = cast(list[GoldEdit], self._case["edits"])
            edits.append(
                GoldEdit(
                    category=attrs.get("category", ""),
                    start=_non_negative_int(attrs.get("start"), "edit start"),
                    end=_non_negative_int(attrs.get("end"), "edit end"),
                    original=attrs.get("original", ""),
                    suggestion=attrs.get("suggestion", ""),
                )
            )

    def characters(self, content: str) -> None:
        if self._selected and self._field is not None:
            self._characters.append(content)

    def endElement(self, name: str) -> None:  # noqa: N802
        if not self._selected or self._case is None:
            return
        if name == self._field:
            value = "".join(self._characters)
            if name == "tag":
                cast(list[str], self._case["tags"]).append(value)
            else:
                self._case[name] = value
            self._field = None
            self._characters = []
        if name != "case":
            return
        materialized = _sentence_case_from_selected_xml(self._case)
        self.cases.append(materialized)
        if self._on_materialized is not None:
            self._on_materialized(materialized.case_id)
        self._case = None
        self._selected = False


def load_development_sentences(
    path: Path, *, on_materialized: Callable[[str], None] | None = None
) -> tuple[SentenceCase, ...]:
    """Load only development sentences without retaining holdout character data."""

    handler = _DevelopmentSentenceHandler(on_materialized)
    xml.sax.parse(path, handler)
    if not handler.cases:
        raise ValueError("development sentence split is empty")
    ids = [case.case_id for case in handler.cases]
    if len(ids) != len(set(ids)):
        raise ValueError("development sentence identifiers must be unique")
    return tuple(handler.cases)


def load_reserved_holdout_sentences(
    path: Path,
    marker: Path,
    frozen_path: Path,
    inputs: FreezeInputs,
) -> tuple[SentenceCase, ...]:
    """Load reviewed holdout sentences only after a valid reservation exists."""

    if not marker.is_file():
        raise ValueError("holdout must be reserved before loading")
    raw_marker = _mapping(
        json.loads(marker.read_text(encoding="utf-8")), "holdout reservation"
    )
    frozen = verify_frozen_gate(frozen_path, inputs)
    if raw_marker != frozen.as_dict():
        raise ValueError("holdout reservation does not match frozen inputs")
    corpus = load_correction_corpus_json(path)
    selected = select_cases_for_purpose(corpus, purpose="quality_gate")
    return tuple(
        _from_corpus_case(case)
        for case in selected
        if case.split == "holdout" and case.unit == "sentence"
    )


def score_exact_edits(
    gold: tuple[GoldEdit, ...], actual: tuple[ObservedEdit, ...]
) -> EditCounts:
    """Compare exact edits without trusting reported source or category."""

    gold_keys = {item.exact_key for item in gold}
    actual_keys = {item.exact_key for item in actual}
    if len(gold_keys) != len(gold) or len(actual_keys) != len(actual):
        raise ValueError("exact edit inputs must not contain duplicates")
    return EditCounts(
        true_positive=len(gold_keys & actual_keys),
        false_positive=len(actual_keys - gold_keys),
        false_negative=len(gold_keys - actual_keys),
    )


def validate_runner_response(
    source: str,
    raw: object,
    *,
    config: GateConfig | None = None,
) -> RunnerObservation:
    """Validate the complete installed-runner response against original text."""

    response = _mapping(raw, "runner response")
    expected_keys = {
        "schema_version",
        "request_id",
        "status",
        "analysis_findings",
        "automatic_findings",
        "reviewable_findings",
        "corrected_text",
        "selected_text",
        "selected_finding_ids",
        "suggestion_outcomes",
        "elapsed_ms",
        "python_rss_bytes",
        "child_rss_bytes",
        "combined_rss_bytes",
        "python_peak_rss_bytes",
        "child_peak_rss_bytes",
        "combined_peak_rss_bytes",
        "model_calls",
        "process_start_count",
    }
    if set(response) != expected_keys:
        raise ValueError("runner response must contain exactly the protocol fields")
    if response["schema_version"] != 1 or response["status"] != "complete":
        raise ValueError("runner response is not a complete schema-v1 outcome")
    request_id = _positive_integer(response["request_id"], "request id")
    analysis = _finding_sequence(response["analysis_findings"], source, "analysis")
    automatic = _finding_sequence(response["automatic_findings"], source, "automatic")
    reviewable = _finding_sequence(
        response["reviewable_findings"], source, "reviewable"
    )
    analysis_ids = tuple(item.finding_id for item in analysis)
    automatic_ids = {item.finding_id for item in automatic}
    reviewable_ids = {item.finding_id for item in reviewable}
    if automatic_ids & reviewable_ids:
        raise ValueError("automatic and reviewable channels must be disjoint")
    if not automatic_ids | reviewable_ids <= set(analysis_ids):
        raise ValueError("correction findings must originate from analyze")
    analysis_by_id = {item.finding_id: item for item in analysis}
    if len(analysis_by_id) != len(analysis):
        raise ValueError("analysis finding identifiers must be unique")
    if any(
        analysis_by_id[item.finding_id] != item for item in (*automatic, *reviewable)
    ):
        raise ValueError("correction findings must be identical to analyze findings")
    if config is not None:
        if any(item.source not in config.automatic_sources for item in automatic):
            raise ValueError("automatic finding source is not allowlisted")
        if any(item.source not in config.reviewable_sources for item in reviewable):
            raise ValueError("reviewable finding source is not allowlisted")
        if any(item.source.startswith("llm:") for item in automatic):
            raise ValueError("model finding cannot enter automatic channel")

    corrected_text = _string(response["corrected_text"], "corrected text")
    selected_text = _string(response["selected_text"], "selected text")
    if _apply_observed_edits(source, automatic) != corrected_text:
        raise ValueError("automatic findings do not reconstruct corrected text")
    selected_ids_raw = response["selected_finding_ids"]
    if not isinstance(selected_ids_raw, list) or not all(
        isinstance(item, str) for item in selected_ids_raw
    ):
        raise ValueError("selected finding identifiers must be a string list")
    selected_ids = tuple(cast(list[str], selected_ids_raw))
    if (
        len(selected_ids) != len(set(selected_ids))
        or set(selected_ids) != reviewable_ids
    ):
        raise ValueError("selected findings must equal reviewable findings")
    if _apply_observed_edits(source, (*automatic, *reviewable)) != selected_text:
        raise ValueError("selected findings do not reconstruct selected text")

    outcomes_raw = response["suggestion_outcomes"]
    if not isinstance(outcomes_raw, list):
        raise ValueError("suggestion outcomes must be a list")
    outcomes = tuple(_validate_suggestion_outcome(item) for item in outcomes_raw)
    model_calls = _non_negative_integer(response["model_calls"], "model calls")
    if model_calls != sum(cast(int, item["model_calls"]) for item in outcomes):
        raise ValueError("model call count does not match suggestion outcomes")
    python_rss = _non_negative_integer(response["python_rss_bytes"], "Python RSS")
    child_rss = _non_negative_integer(response["child_rss_bytes"], "child RSS")
    combined_rss = _non_negative_integer(response["combined_rss_bytes"], "combined RSS")
    if python_rss + child_rss != combined_rss:
        raise ValueError("combined RSS does not equal process RSS values")
    python_peak_rss = _non_negative_integer(
        response["python_peak_rss_bytes"], "Python peak RSS"
    )
    child_peak_rss = _non_negative_integer(
        response["child_peak_rss_bytes"], "child peak RSS"
    )
    combined_peak_rss = _non_negative_integer(
        response["combined_peak_rss_bytes"], "combined peak RSS"
    )
    if python_peak_rss + child_peak_rss != combined_peak_rss:
        raise ValueError("combined peak RSS does not equal process peak RSS values")
    if (
        python_peak_rss < python_rss
        or child_peak_rss < child_rss
        or combined_peak_rss < combined_rss
    ):
        raise ValueError("peak RSS cannot be below loaded RSS")
    return RunnerObservation(
        request_id=request_id,
        automatic_edits=automatic,
        reviewable_edits=reviewable,
        analysis_finding_ids=analysis_ids,
        corrected_text=corrected_text,
        selected_text=selected_text,
        suggestion_outcomes=outcomes,
        elapsed_ms=_non_negative_number(response["elapsed_ms"], "elapsed time"),
        python_rss_bytes=python_rss,
        child_rss_bytes=child_rss,
        combined_rss_bytes=combined_rss,
        python_peak_rss_bytes=python_peak_rss,
        child_peak_rss_bytes=child_peak_rss,
        combined_peak_rss_bytes=combined_peak_rss,
        model_calls=model_calls,
        process_start_count=_non_negative_integer(
            response["process_start_count"], "process start count"
        ),
    )


def gate_qualifies(report: Mapping[str, object], config: GateConfig) -> bool:
    """Return whether one split passes every frozen non-vacuous gate."""

    try:
        automatic = _mapping(report["automatic"], "automatic metrics")
        reviewable = _mapping(report["reviewable"], "reviewable metrics")
        performance = _mapping(report["performance"], "performance metrics")
        gates = config.gates
        return bool(
            _non_negative_integer(automatic["proposed_edits"], "automatic proposals")
            > 0
            and _non_negative_number(automatic["precision"], "automatic precision")
            >= gates.automatic_minimum_precision
            and _non_negative_number(
                automatic["correction_accuracy"], "automatic correction accuracy"
            )
            >= gates.automatic_minimum_correction_accuracy
            and _non_negative_integer(
                reviewable["proposed_edits"], "reviewable proposals"
            )
            > 0
            and _non_negative_number(reviewable["precision"], "reviewable precision")
            >= gates.reviewable_minimum_precision
            and _non_negative_number(
                report["structured_outcome_validity"], "outcome validity"
            )
            >= gates.minimum_structured_outcome_validity
            and _non_negative_integer(
                report["protected_automatic_changes"], "protected automatic changes"
            )
            <= gates.maximum_protected_automatic_changes
            and _non_negative_integer(
                report["protected_reviewable_findings"],
                "protected reviewable findings",
            )
            <= gates.maximum_protected_reviewable_findings
            and _non_negative_number(
                performance["warm_in_process_p95_ms"], "warm in-process p95"
            )
            <= gates.maximum_warm_in_process_p95_ms
            and _non_negative_number(
                performance["warm_e2e_p95_ms"], "warm end-to-end p95"
            )
            <= gates.maximum_warm_e2e_p95_ms
            and _non_negative_integer(
                performance["combined_peak_rss_bytes"], "combined peak RSS"
            )
            <= gates.maximum_combined_peak_rss_bytes
            and _non_negative_integer(performance["swap_delta_bytes"], "swap delta")
            <= gates.maximum_swap_delta_bytes
            and _non_negative_integer(performance["socket_count"], "socket count")
            <= gates.maximum_socket_count
            and _non_negative_integer(performance["model_calls"], "model calls")
            == gates.required_model_calls
            and _non_negative_integer(
                performance["process_start_count"], "process starts"
            )
            == gates.required_process_start_count
            and _non_negative_integer(
                performance["stable_repetitions"], "stable repetitions"
            )
            >= gates.required_stable_repetitions
        )
    except (KeyError, TypeError, ValueError):
        return False


def validate_privacy_safe_report(raw: object) -> Mapping[str, object]:
    """Reject analyzed text, edit material, raw responses, and private paths."""

    report = _mapping(raw, "release report")
    forbidden_keys = {
        "text",
        "source",
        "source_text",
        "input",
        "expected_output",
        "original",
        "suggestion",
        "corrected_text",
        "selected_text",
        "raw_response",
    }

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    raise ValueError("report cannot contain raw analyzed text")
                inspect(child)
        elif isinstance(value, list | tuple):
            for child in value:
                inspect(child)
        elif isinstance(value, str) and re.search(
            r"(?:^|\s)(?:/Users/|/home/|[A-Za-z]:\\Users\\)", value
        ):
            raise ValueError("report cannot contain a private path")

    inspect(report)
    return report


def canonical_json_sha256(value: object) -> str:
    """Hash one JSON-compatible value with a stable canonical encoding."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def frozen_input_hashes(inputs: FreezeInputs) -> dict[str, str]:
    """Return canonical identities for every frozen input."""

    return _freeze_hashes(inputs)


def freeze_gate(
    inputs: FreezeInputs,
    destination: Path,
    *,
    development_report: Mapping[str, object] | None = None,
) -> FrozenGate:
    """Hash every executable gate input and persist a canonical freeze."""

    frozen = FrozenGate(
        _freeze_hashes(inputs),
        (
            canonical_json_sha256(development_report)
            if development_report is not None
            else None
        ),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            frozen.as_dict(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return frozen


def verify_frozen_gate(
    path: Path,
    inputs: FreezeInputs,
    *,
    development_report: Mapping[str, object] | None = None,
) -> FrozenGate:
    """Verify that the current bytes exactly match a prior freeze."""

    if not path.is_file():
        raise ValueError("frozen gate is unavailable")
    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "frozen gate")
    if not raw or not all(
        isinstance(key, str) and key.endswith("_sha256") and _is_sha256(value)
        for key, value in raw.items()
    ):
        raise ValueError("frozen gate has invalid hash records")
    expected = _freeze_hashes(inputs)
    report_hash = raw.pop("development_report_sha256", None)
    if raw != expected:
        raise ValueError("frozen gate hash mismatch")
    if development_report is not None:
        if report_hash is None or report_hash != canonical_json_sha256(
            development_report
        ):
            raise ValueError("frozen development report hash mismatch")
    return FrozenGate(
        {key: cast(str, value) for key, value in raw.items()},
        cast(str | None, report_hash),
    )


def reserve_holdout_once(
    frozen_path: Path,
    marker_path: Path,
    inputs: FreezeInputs,
    *,
    development_report: Mapping[str, object] | None = None,
) -> None:
    """Atomically reserve one holdout run after validating every frozen byte."""

    frozen = verify_frozen_gate(
        frozen_path,
        inputs,
        development_report=development_report,
    )
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with marker_path.open("x", encoding="utf-8") as marker:
            json.dump(
                frozen.as_dict(),
                marker,
                sort_keys=True,
                separators=(",", ":"),
            )
            marker.write("\n")
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error


def _freeze_hashes(inputs: FreezeInputs) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in sorted(inputs.files.items()):
        if not path.is_file():
            raise ValueError(f"freeze file {name} is unavailable")
        hashes[f"{name}_sha256"] = sha256_path(path)
    for name, path in sorted(inputs.directories.items()):
        hashes[f"{name}_sha256"] = _directory_sha256(path)
    return hashes


def _directory_sha256(path: Path) -> str:
    if not path.is_dir():
        raise ValueError("freeze directory is unavailable")
    records = [
        (item.relative_to(path).as_posix(), sha256_path(item))
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    if not records:
        raise ValueError("freeze directory is empty")
    encoded = json.dumps(records, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finding_sequence(
    value: object, source_text: str, label: str
) -> tuple[ObservedEdit, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} findings must be a list")
    findings = tuple(_observed_edit(item, source_text, label) for item in value)
    ids = [item.finding_id for item in findings]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} findings contain duplicate identifiers")
    return findings


def _observed_edit(value: object, source_text: str, label: str) -> ObservedEdit:
    item = _mapping(value, f"{label} finding")
    if set(item) != {
        "id",
        "category",
        "severity",
        "original",
        "suggestion",
        "start",
        "end",
        "confidence",
        "source",
    }:
        raise ValueError(f"{label} finding has invalid fields")
    start = _non_negative_integer(item["start"], "finding start")
    end = _non_negative_integer(item["end"], "finding end")
    original = item["original"]
    suggestion = item["suggestion"]
    if not isinstance(original, str) or not isinstance(suggestion, str):
        raise ValueError("finding original and suggestion must be strings")
    if end < start or end > len(source_text):
        raise ValueError("finding range is outside original text")
    if source_text[start:end] != original:
        raise ValueError("finding original does not match original text")
    if original == suggestion:
        raise ValueError("finding suggestion must change original text")
    _non_negative_number(item["confidence"], "finding confidence")
    return ObservedEdit(
        start=start,
        end=end,
        original=original,
        suggestion=suggestion,
        category=_string(item["category"], "finding category"),
        source=_string(item["source"], "finding source"),
        finding_id=_string(item["id"], "finding id"),
    )


def _apply_observed_edits(source: str, edits: tuple[ObservedEdit, ...]) -> str:
    ordered = sorted(edits, key=lambda item: (item.start, item.end, item.finding_id))
    cursor = 0
    pieces: list[str] = []
    insertion_offsets: set[int] = set()
    for edit in ordered:
        if edit.start < cursor:
            raise ValueError("findings conflict or overlap")
        if edit.start == edit.end:
            if edit.start in insertion_offsets:
                raise ValueError("findings contain conflicting insertions")
            insertion_offsets.add(edit.start)
        pieces.extend((source[cursor : edit.start], edit.suggestion))
        cursor = edit.end
    pieces.append(source[cursor:])
    return "".join(pieces)


def _validate_suggestion_outcome(value: object) -> Mapping[str, object]:
    outcome = _mapping(value, "suggestion outcome")
    expected = {
        "status",
        "backend",
        "operation",
        "suggestions",
        "model_calls",
        "protocol_versions",
        "operation_version",
        "source_policy_version",
    }
    if set(outcome) != expected:
        raise ValueError("suggestion outcome has invalid fields")
    if outcome["status"] not in {
        "complete",
        "unavailable",
        "timed_out",
        "invalid_response",
    }:
        raise ValueError("suggestion outcome status is invalid")
    _non_negative_integer(outcome["suggestions"], "outcome suggestions")
    _non_negative_integer(outcome["model_calls"], "outcome model calls")
    for key in ("backend", "operation", "operation_version", "source_policy_version"):
        _string(outcome[key], f"outcome {key}")
    if not isinstance(outcome["protocol_versions"], list) or not all(
        isinstance(item, str) for item in outcome["protocol_versions"]
    ):
        raise ValueError("outcome protocol versions must be strings")
    return outcome


def _from_corpus_case(case: CorrectionCorpusCase) -> SentenceCase:
    return SentenceCase(
        case_id=case.id,
        stratum=case.stratum,
        split="holdout",
        unit="sentence",
        source=case.input,
        expected_output=case.expected_output,
        gold_edits=tuple(
            GoldEdit(
                edit.category,
                edit.start,
                edit.end,
                edit.original,
                edit.suggestion,
            )
            for edit in case.edits
        ),
        tags=case.tags,
    )


def _sentence_case_from_selected_xml(raw: Mapping[str, object]) -> SentenceCase:
    if raw.get("reviewed") is not True:
        raise ValueError("development sentence must be human-reviewed")
    case_id = _string(raw.get("id"), "case id")
    stratum = _string(raw.get("stratum"), "case stratum")
    if stratum not in {"inflection", "syntax", "punctuation", "hard_negative"}:
        raise ValueError(f"case {case_id} has invalid stratum")
    source = _string(raw.get("input"), f"case {case_id} input")
    expected = _string(raw.get("expected_output"), f"case {case_id} expected output")
    edits = tuple(cast(list[GoldEdit], raw["edits"]))
    cursor = 0
    output: list[str] = []
    for edit in sorted(edits, key=lambda item: (item.start, item.end)):
        if edit.end < edit.start or edit.start < cursor or edit.end > len(source):
            raise ValueError(f"case {case_id} has invalid or overlapping edits")
        if source[edit.start : edit.end] != edit.original:
            raise ValueError(f"case {case_id} edit original does not match")
        if edit.original == edit.suggestion:
            raise ValueError(f"case {case_id} edit does not change text")
        output.extend((source[cursor : edit.start], edit.suggestion))
        cursor = edit.end
    output.append(source[cursor:])
    if "".join(output) != expected:
        raise ValueError(f"case {case_id} edits do not reconstruct expected output")
    return SentenceCase(
        case_id=case_id,
        stratum=stratum,
        split="development",
        unit="sentence",
        source=source,
        expected_output=expected,
        gold_edits=edits,
        tags=tuple(cast(list[str], raw["tags"])),
    )


def _quality_gates(raw: Mapping[str, object]) -> QualityGates:
    return QualityGates(
        automatic_minimum_precision=_number(raw["automatic_minimum_precision"]),
        automatic_minimum_correction_accuracy=_number(
            raw["automatic_minimum_correction_accuracy"]
        ),
        reviewable_minimum_precision=_number(raw["reviewable_minimum_precision"]),
        minimum_structured_outcome_validity=_number(
            raw["minimum_structured_outcome_validity"]
        ),
        maximum_protected_automatic_changes=_integer(
            raw["maximum_protected_automatic_changes"]
        ),
        maximum_protected_reviewable_findings=_integer(
            raw["maximum_protected_reviewable_findings"]
        ),
        maximum_warm_in_process_p95_ms=_number(raw["maximum_warm_in_process_p95_ms"]),
        maximum_warm_e2e_p95_ms=_number(raw["maximum_warm_e2e_p95_ms"]),
        maximum_combined_peak_rss_bytes=_integer(
            raw["maximum_combined_peak_rss_bytes"]
        ),
        maximum_swap_delta_bytes=_integer(raw["maximum_swap_delta_bytes"]),
        maximum_socket_count=_integer(raw["maximum_socket_count"]),
        required_model_calls=_integer(raw["required_model_calls"]),
        required_process_start_count=_integer(raw["required_process_start_count"]),
        required_stable_repetitions=_integer(raw["required_stable_repetitions"]),
    )


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], label: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} must contain exactly the frozen keys")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _string_set(value: object, label: str) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    strings = tuple(_string(item, label) for item in value)
    if tuple(sorted(strings)) != strings or len(strings) != len(set(strings)):
        raise ValueError(f"{label} must be sorted and unique")
    return frozenset(strings)


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("quality threshold must be numeric")
    return float(value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("quality count must be a non-negative integer")
    return value


def _non_negative_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _positive_integer(value: object, label: str) -> int:
    parsed = _non_negative_integer(value, label)
    if parsed == 0:
        raise ValueError(f"{label} must be positive")
    return parsed


def _non_negative_number(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{label} must be non-negative and finite")
    return float(value)


def _non_negative_int(value: str | None, label: str) -> int:
    try:
        parsed = int(value or "")
    except ValueError as error:
        raise ValueError(f"{label} must be an integer") from error
    if parsed < 0:
        raise ValueError(f"{label} must be non-negative")
    return parsed


def _digest(value: object, label: str) -> str:
    if not _is_sha256(value):
        raise ValueError(f"{label} must be SHA-256")
    return cast(str, value)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = [
    "canonical_json_sha256",
    "EditCounts",
    "FreezeInputs",
    "FrozenGate",
    "GateConfig",
    "GoldEdit",
    "ObservedEdit",
    "QualityGates",
    "RunnerObservation",
    "SentenceCase",
    "gate_qualifies",
    "freeze_gate",
    "frozen_input_hashes",
    "load_development_sentences",
    "load_gate_config",
    "load_reserved_holdout_sentences",
    "score_exact_edits",
    "sha256_path",
    "reserve_holdout_once",
    "validate_privacy_safe_report",
    "validate_runner_response",
    "verify_frozen_gate",
]
