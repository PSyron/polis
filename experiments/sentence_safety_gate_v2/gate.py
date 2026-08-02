"""V2 configuration and split-safe loading for the sentence safety gate."""

from __future__ import annotations

import json
import math
import os
import xml.sax
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Any, Literal, cast
from xml.sax.handler import ContentHandler
from xml.sax.xmlreader import AttributesImpl

from experiments.sentence_safety_gate.gate import (
    FreezeInputs,
    GoldEdit,
    QualityGates,
    verify_frozen_gate,
)

from polis.evaluation.correction_corpus import CorrectionCorpusCase
from polis.evaluation.safety_corpus import (
    CORPUS_V2_ID,
    REVIEW_CHECKLIST_V2_VERSION,
    V2_APPROVED_CANDIDATE_DIGEST,
    V2_APPROVED_FROZEN_DIGEST,
    V2_APPROVED_REVIEW_DATE,
    V2_REQUIRED_REVIEWER,
    select_safety_cases_for_purpose,
    validate_safety_corpus,
)

Split = Literal["development", "holdout"]

_TOP_LEVEL_KEYS = frozenset(
    {
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
)
_CORPUS_KEYS = frozenset(
    {
        "id",
        "candidate_digest",
        "frozen_digest",
        "json_path",
        "json_sha256",
        "xml_path",
        "xml_sha256",
        "approval_path",
        "approval_sha256",
    }
)
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
_EXPERIMENT_ID = "polis_sentence_safety_gate_v2_2026_08_02"
_PLATFORM_PROFILE = "macos-arm64-v1"
_SOURCE_POLICY_VERSION = "1.2"
_CORPUS_IDENTITY: Mapping[str, object] = MappingProxyType(
    {
        "id": CORPUS_V2_ID,
        "candidate_digest": V2_APPROVED_CANDIDATE_DIGEST,
        "frozen_digest": V2_APPROVED_FROZEN_DIGEST,
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
)
_AUTOMATIC_SOURCES = frozenset(
    {
        "rule:agreement.copula",
        "rule:languagetool.pl",
        "rule:spelling.jestes",
        "rule:spelling.wlasnie",
        "rule:spelling.zeby",
        "rule:syntax.comma_space",
        "rule:syntax.list_space",
        "rule:syntax.quote_space",
        "rule:syntax.sentence_space",
    }
)
_REVIEWABLE_SOURCES = frozenset(
    {
        "rule:languagetool.contextual_inflection",
        "rule:syntax.missing_correlative",
        "rule:syntax.missing_reflexive",
    }
)
_LANGUAGE_TOOL_IDENTITY: Mapping[str, str] = MappingProxyType(
    {
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
_REQUIRED_GATES = QualityGates(
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


@dataclass(frozen=True, slots=True)
class GateConfig:
    """Closed v2 identity and quality-gate configuration."""

    schema_version: int
    experiment_id: str
    sentence_only: bool
    platform_profile: str
    source_policy_version: str
    corpus_id: str
    candidate_corpus_digest: str
    frozen_corpus_digest: str
    corpus_json_path: str
    corpus_sha256: str
    corpus_xml_path: str
    corpus_xml_sha256: str
    corpus_approval_path: str
    corpus_approval_sha256: str
    automatic_sources: frozenset[str]
    reviewable_sources: frozenset[str]
    language_tool: Mapping[str, str]
    gates: QualityGates


@dataclass(frozen=True, slots=True)
class SentenceCase:
    """One development sentence retained by the repository-side scorer."""

    case_id: str
    stratum: str
    split: Split
    source: str
    expected_output: str
    gold_edits: tuple[GoldEdit, ...]
    tags: tuple[str, ...]

    @property
    def protected_negative(self) -> bool:
        """Whether the case is a protected hard negative."""

        return self.stratum == "hard_negative"


@dataclass(frozen=True, slots=True, eq=False)
class HoldoutReservation:
    """Process-local single-use authority for one durable holdout marker."""

    _marker: Path
    _frozen_records: tuple[tuple[str, str], ...]
    _issuer_pid: int


_RESERVATION_LOCK = Lock()
_ACTIVE_RESERVATIONS: dict[int, HoldoutReservation] = {}


class _DevelopmentSentenceHandler(ContentHandler):
    """Materialize reviewed development cases and ignore holdout events."""

    def __init__(self, on_materialized: Callable[[str], None] | None) -> None:
        super().__init__()
        self.cases: list[SentenceCase] = []
        self.holdout_sentence_count = 0
        self._on_materialized = on_materialized
        self._selected = False
        self._case: dict[str, object] | None = None
        self._field: str | None = None
        self._characters: list[str] = []

    def startElement(self, name: str, attrs: AttributesImpl) -> None:  # noqa: N802
        if name == "case":
            if attrs.get("split") == "holdout" and attrs.get("unit") == "sentence":
                self.holdout_sentence_count += 1
            self._selected = (
                attrs.get("split") == "development" and attrs.get("unit") == "sentence"
            )
            if self._selected:
                self._case = {
                    "id": attrs.get("id"),
                    "stratum": attrs.get("stratum"),
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
                and attrs.get("reviewer") == V2_REQUIRED_REVIEWER
                and attrs.get("reviewed_at") == V2_APPROVED_REVIEW_DATE
                and attrs.get("checklist_version") == REVIEW_CHECKLIST_V2_VERSION
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
        case = _selected_case(self._case)
        self.cases.append(case)
        if self._on_materialized is not None:
            self._on_materialized(case.case_id)
        self._case = None
        self._selected = False


def load_development_sentences(
    path: Path,
    *,
    on_materialized: Callable[[str], None] | None = None,
) -> tuple[SentenceCase, ...]:
    """Stream only 80 reviewed development sentences from a v2 XML corpus."""

    handler = _DevelopmentSentenceHandler(on_materialized)
    xml.sax.parse(path, handler)
    if len(handler.cases) != 80:
        raise ValueError("development split must contain exactly 80 sentences")
    if handler.holdout_sentence_count != 160:
        raise ValueError("holdout split must contain exactly 160 sentences")
    identifiers = [case.case_id for case in handler.cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("development sentence identifiers must be unique")
    return tuple(handler.cases)


def reserve_holdout_once(
    frozen_path: Path,
    marker: Path,
    inputs: FreezeInputs,
) -> HoldoutReservation:
    """Durably reserve the only holdout run after verifying frozen inputs."""

    frozen = verify_frozen_gate(frozen_path, inputs)
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        with marker.open("x", encoding="utf-8") as destination:
            json.dump(
                frozen.as_dict(),
                destination,
                sort_keys=True,
                separators=(",", ":"),
            )
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error
    if os.name == "posix":
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory = os.open(marker.parent, flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    reservation = HoldoutReservation(
        _marker=marker.resolve(),
        _frozen_records=tuple(sorted(frozen.as_dict().items())),
        _issuer_pid=os.getpid(),
    )
    with _RESERVATION_LOCK:
        _ACTIVE_RESERVATIONS[id(reservation)] = reservation
    return reservation


def load_reserved_holdout_sentences(
    corpus_path: Path,
    approval_path: Path,
    marker: Path,
    frozen_path: Path,
    inputs: FreezeInputs,
    *,
    reservation: HoldoutReservation,
) -> tuple[SentenceCase, ...]:
    """Load the approved v2 holdout only after matching durable reservation."""

    _consume_reservation(reservation)
    if reservation._marker != marker.resolve():
        raise ValueError("holdout reservation capability does not match marker")
    if not marker.is_file():
        raise ValueError("holdout must be reserved before loading")
    raw_marker = _mapping(
        json.loads(marker.read_text(encoding="utf-8")),
        "holdout reservation",
    )
    frozen = verify_frozen_gate(frozen_path, inputs)
    frozen_records = tuple(sorted(frozen.as_dict().items()))
    if raw_marker != frozen.as_dict() or frozen_records != reservation._frozen_records:
        raise ValueError("holdout reservation does not match frozen inputs")

    raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    corpus = validate_safety_corpus(raw)
    selected = select_safety_cases_for_purpose(
        corpus,
        purpose="quality_gate",
        raw=raw,
        approval_manifest=approval,
    )
    if len(selected) != 160 or any(
        case.split != "holdout" or case.review.status != "human-reviewed"
        for case in selected
    ):
        raise ValueError("quality gate requires exactly 160 reviewed holdout cases")
    return tuple(_from_corpus_case(case) for case in selected)


def _consume_reservation(reservation: HoldoutReservation) -> None:
    if not isinstance(reservation, HoldoutReservation):
        raise ValueError("a valid holdout reservation capability is required")
    if reservation._issuer_pid != os.getpid():
        raise ValueError("holdout reservation capability belongs to issuing process")
    with _RESERVATION_LOCK:
        registered = _ACTIVE_RESERVATIONS.pop(id(reservation), None)
    if registered is not reservation:
        raise ValueError(
            "holdout reservation capability is invalid or already consumed"
        )


def load_gate_config(path: Path) -> GateConfig:
    """Load the exact closed v2 sentence-safety-gate configuration."""

    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "configuration")
    _exact_keys(raw, _TOP_LEVEL_KEYS, "configuration")
    if raw["schema_version"] != 1:
        raise ValueError("configuration schema_version must be 1")
    if raw["sentence_only"] is not True:
        raise ValueError("configuration must be sentence-only")
    if raw["experiment_id"] != _EXPERIMENT_ID:
        raise ValueError("configuration experiment identity mismatch")
    if raw["platform_profile"] != _PLATFORM_PROFILE:
        raise ValueError("configuration platform identity mismatch")
    if raw["source_policy_version"] != _SOURCE_POLICY_VERSION:
        raise ValueError("configuration source policy version must be 1.2")

    corpus = _mapping(raw["corpus"], "corpus configuration")
    sources = _mapping(raw["sources"], "source configuration")
    language_tool = _mapping(raw["language_tool"], "LanguageTool configuration")
    gates = _mapping(raw["gates"], "quality gates")
    _exact_keys(corpus, _CORPUS_KEYS, "corpus configuration")
    _exact_keys(sources, _SOURCE_KEYS, "source configuration")
    _exact_keys(language_tool, _LANGUAGE_TOOL_KEYS, "LanguageTool configuration")
    _exact_keys(gates, _GATE_KEYS, "quality gates")

    if corpus != _CORPUS_IDENTITY:
        raise ValueError("configuration corpus identity mismatch")
    if corpus["id"] != CORPUS_V2_ID:
        raise ValueError("configuration must use the v2 safety corpus")
    candidate_digest = _digest(corpus["candidate_digest"], "candidate corpus digest")
    if candidate_digest != V2_APPROVED_CANDIDATE_DIGEST:
        raise ValueError("configuration candidate safety corpus digest is invalid")
    frozen_digest = _digest(corpus["frozen_digest"], "frozen corpus digest")
    if frozen_digest != V2_APPROVED_FROZEN_DIGEST:
        raise ValueError("configuration frozen safety corpus digest is invalid")
    automatic = _string_set(sources["automatic"], "automatic sources")
    reviewable = _string_set(sources["reviewable"], "reviewable sources")
    if automatic & reviewable:
        raise ValueError("source channels must be disjoint")
    if automatic != _AUTOMATIC_SOURCES or reviewable != _REVIEWABLE_SOURCES:
        raise ValueError("configuration source identity mismatch")
    language_tool_strings = _language_tool_strings(language_tool)
    if language_tool_strings != _LANGUAGE_TOOL_IDENTITY:
        raise ValueError("configuration LanguageTool identity mismatch")
    quality_gates = _quality_gates(gates)
    if quality_gates != _REQUIRED_GATES:
        raise ValueError("configuration quality gates must remain unchanged")

    return GateConfig(
        schema_version=1,
        experiment_id=_EXPERIMENT_ID,
        sentence_only=True,
        platform_profile=_PLATFORM_PROFILE,
        source_policy_version=_SOURCE_POLICY_VERSION,
        corpus_id=CORPUS_V2_ID,
        candidate_corpus_digest=candidate_digest,
        frozen_corpus_digest=frozen_digest,
        corpus_json_path=_required_text(corpus["json_path"], "corpus JSON path"),
        corpus_sha256=_digest(corpus["json_sha256"], "corpus JSON hash"),
        corpus_xml_path=_required_text(corpus["xml_path"], "corpus XML path"),
        corpus_xml_sha256=_digest(corpus["xml_sha256"], "corpus XML hash"),
        corpus_approval_path=_required_text(
            corpus["approval_path"], "corpus approval path"
        ),
        corpus_approval_sha256=_digest(
            corpus["approval_sha256"], "corpus approval hash"
        ),
        automatic_sources=automatic,
        reviewable_sources=reviewable,
        language_tool=language_tool_strings,
        gates=quality_gates,
    )


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _exact_keys(
    value: Mapping[str, object],
    expected: frozenset[str],
    label: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} must contain exactly the frozen keys")


def _string_set(value: object, label: str) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    strings = tuple(_required_text(item, label) for item in value)
    if tuple(sorted(strings)) != strings or len(strings) != len(set(strings)):
        raise ValueError(f"{label} must be sorted and unique")
    return frozenset(strings)


def _language_tool_strings(raw: Mapping[str, object]) -> Mapping[str, str]:
    values: dict[str, str] = {}
    for name, value in raw.items():
        text = _required_text(value, f"LanguageTool {name}")
        if name.endswith("_sha256"):
            _digest(text, f"LanguageTool {name}")
        values[name] = text
    return MappingProxyType(values)


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


def _number(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise ValueError("quality threshold must be finite and numeric")
    return float(value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("quality count must be a non-negative integer")
    return value


def _digest(value: object, label: str) -> str:
    if not (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be SHA-256")
    return value


def _selected_case(raw: dict[str, object]) -> SentenceCase:
    if raw.get("reviewed") is not True:
        raise ValueError("development sentence must be owner-reviewed")
    source = _required_text(raw.get("input"), "case input")
    edits = tuple(cast(list[GoldEdit], raw["edits"]))
    for edit in edits:
        if (
            edit.end < edit.start
            or edit.end > len(source)
            or source[edit.start : edit.end] != edit.original
        ):
            raise ValueError("development edit does not match original input")
    return SentenceCase(
        case_id=_required_text(raw.get("id"), "case id"),
        stratum=_required_text(raw.get("stratum"), "case stratum"),
        split="development",
        source=source,
        expected_output=_required_text(raw.get("expected_output"), "case output"),
        gold_edits=edits,
        tags=tuple(cast(list[str], raw["tags"])),
    )


def _from_corpus_case(case: CorrectionCorpusCase) -> SentenceCase:
    return SentenceCase(
        case_id=case.id,
        stratum=case.stratum,
        split="holdout",
        source=case.input,
        expected_output=case.expected_output,
        gold_edits=tuple(
            GoldEdit(
                category=edit.category,
                start=edit.start,
                end=edit.end,
                original=edit.original,
                suggestion=edit.suggestion,
            )
            for edit in case.edits
        ),
        tags=case.tags,
    )


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _non_negative_int(value: object, name: str) -> int:
    try:
        parsed = int(cast(str, value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


__all__ = [
    "GateConfig",
    "QualityGates",
    "SentenceCase",
    "load_development_sentences",
    "load_gate_config",
    "load_reserved_holdout_sentences",
    "reserve_holdout_once",
]
