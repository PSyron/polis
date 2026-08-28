from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, cast

_SOURCE_PATHS: Final = (
    "quality/v1/cases.json",
    "quality/v2/cases.json",
    "quality/v3/cases.json",
    "quality/v4/cases.json",
)

type CaseKind = Literal["error", "correct", "conflict", "abstain"]
type ProtectedSpanKind = Literal["quote", "code"]


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    dataset_id: str
    dataset_version: int
    path: str
    sha256: str
    license: str
    source: str
    clean_case_count: int


@dataclass(frozen=True, slots=True)
class SourceFinding:
    category: str
    start: int
    end: int
    original: str
    suggestion: str
    rule_family: str | None = None


@dataclass(frozen=True, slots=True)
class SourceError:
    case_id: str
    kind: CaseKind
    phenomenon: str | None
    category: str | None
    features: frozenset[str]
    shape_strata: frozenset[str]
    pair_id: str | None
    text: str
    findings: tuple[SourceFinding, ...]


@dataclass(frozen=True, slots=True)
class SourceText:
    metadata: SourceMetadata
    case_id: str
    text: str
    kind: CaseKind = "correct"
    phenomenon: str | None = None
    category: str | None = None
    features: frozenset[str] = frozenset()
    shape_strata: frozenset[str] = frozenset()
    pair_id: str | None = None
    paired_error: SourceError | None = None
    controlled_error: SourceError | None = None
    expected_findings: tuple[SourceFinding, ...] = ()
    protected_spans: tuple[ProtectedSpan, ...] = ()


@dataclass(frozen=True, slots=True)
class ProtectedSpan:
    start: int
    end: int
    kind: ProtectedSpanKind


def source_texts(root: Path) -> tuple[SourceText, ...]:
    texts: list[SourceText] = []
    for relative_path in _SOURCE_PATHS:
        path = root / "src" / "polis" / "evaluation" / "datasets" / relative_path
        raw_bytes = path.read_bytes()
        raw = _json_object(json.loads(raw_bytes.decode("utf-8")), "dataset")
        if raw.get("license") != "CC0-1.0" or raw.get("source") != "project-authored":
            raise ValueError(f"synthetic source is not an approved CC0 dataset: {path}")
        dataset_id = _string(raw.get("id"), "dataset id")
        version = _integer(raw.get("dataset_version"), "dataset version")
        raw_cases = raw.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError(f"synthetic source has no cases: {path}")
        parsed_cases = tuple(_parse_case(item) for item in raw_cases)
        errors_by_pair: dict[str, list[SourceError]] = {}
        for case in parsed_cases:
            if case.kind == "error" and case.pair_id is not None:
                errors_by_pair.setdefault(case.pair_id, []).append(_source_error(case))
        metadata = SourceMetadata(
            dataset_id=dataset_id,
            dataset_version=version,
            path=relative_path,
            sha256=sha256(raw_bytes).hexdigest(),
            license="CC0-1.0",
            source="project-authored",
            clean_case_count=sum(case.kind == "correct" for case in parsed_cases),
        )
        for case in parsed_cases:
            if case.kind != "correct":
                continue
            paired_errors = tuple(errors_by_pair.get(case.pair_id or "", ()))
            texts.append(
                SourceText(
                    metadata=metadata,
                    case_id=case.case_id,
                    text=case.text,
                    kind=case.kind,
                    phenomenon=case.phenomenon,
                    category=case.category,
                    features=case.features,
                    shape_strata=case.shape_strata,
                    pair_id=case.pair_id,
                    paired_error=(
                        paired_errors[0] if len(paired_errors) == 1 else None
                    ),
                    controlled_error=_controlled_error(case, paired_errors),
                    expected_findings=case.findings,
                    protected_spans=protected_spans(case.text),
                )
            )
    unique: dict[tuple[str, str], SourceText] = {}
    for source in texts:
        unique.setdefault((source.metadata.dataset_id, source.case_id), source)
    return tuple(
        sorted(unique.values(), key=lambda item: (item.metadata.path, item.case_id))
    )


def provided_source_texts(
    clean_texts: str | Sequence[str],
    *,
    license_name: str,
    source_name: str,
) -> tuple[SourceText, ...]:
    texts = (clean_texts,) if isinstance(clean_texts, str) else tuple(clean_texts)
    if not texts or any(not isinstance(text, str) or not text for text in texts):
        raise ValueError("clean_texts must contain at least one non-empty string")
    if (
        not isinstance(license_name, str)
        or not license_name
        or not isinstance(source_name, str)
        or not source_name
    ):
        raise ValueError("source license and source origin are required")
    payload = json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    metadata = SourceMetadata(
        dataset_id="caller-provided",
        dataset_version=1,
        path="<caller-provided>",
        sha256=sha256(payload).hexdigest(),
        license=license_name,
        source=source_name,
        clean_case_count=len(texts),
    )
    return tuple(
        SourceText(
            metadata=metadata,
            case_id=f"provided_{index:05d}",
            text=text,
            protected_spans=protected_spans(text),
        )
        for index, text in enumerate(texts, start=1)
    )


def protected_spans(text: str) -> tuple[ProtectedSpan, ...]:
    spans: set[tuple[int, int, ProtectedSpanKind]] = set()
    delimiters: tuple[tuple[str, str, ProtectedSpanKind], ...] = (
        ("„", "”", "quote"),
        ("“", "”", "quote"),
        ("«", "»", "quote"),
        ('"', '"', "quote"),
        ("'", "'", "quote"),
        ("`", "`", "code"),
    )
    for opener, closer, kind in delimiters:
        start = text.find(opener)
        while start >= 0:
            end = text.find(closer, start + len(opener))
            if end < 0:
                spans.add((start, len(text), kind))
                break
            spans.add((start, end + len(closer), kind))
            start = text.find(opener, end + len(closer))
    return tuple(
        ProtectedSpan(start=start, end=end, kind=kind)
        for start, end, kind in sorted(spans)
    )


@dataclass(frozen=True, slots=True)
class _ParsedCase:
    case_id: str
    kind: CaseKind
    phenomenon: str | None
    category: str | None
    features: frozenset[str]
    shape_strata: frozenset[str]
    pair_id: str | None
    text: str
    findings: tuple[SourceFinding, ...]


def _parse_case(raw: object) -> _ParsedCase:
    case = _json_object(raw, "dataset case")
    kind = _case_kind(case.get("kind"))
    findings = _findings(case.get("expected_findings"))
    return _ParsedCase(
        case_id=_string(case.get("id"), "case id"),
        kind=kind,
        phenomenon=_optional_string(case.get("phenomenon"), "case phenomenon"),
        category=_optional_string(case.get("category"), "case category"),
        features=_string_set(case.get("features"), "case features"),
        shape_strata=_string_set(case.get("shape_strata"), "case shape strata"),
        pair_id=_optional_string(case.get("pair_id"), "case pair id"),
        text=_string(case.get("text"), "case text"),
        findings=findings,
    )


def _case_kind(value: object) -> CaseKind:
    if not isinstance(value, str) or value not in {
        "error",
        "correct",
        "conflict",
        "abstain",
    }:
        raise ValueError("case kind must be error, correct, conflict, or abstain")
    return cast(CaseKind, value)


def _findings(value: object) -> tuple[SourceFinding, ...]:
    if not isinstance(value, list):
        raise ValueError("case expected_findings must be a list")
    return tuple(_finding(item) for item in value)


def _finding(value: object) -> SourceFinding:
    finding = _json_object(value, "expected finding")
    start = _offset(finding.get("start"), "finding start")
    end = _offset(finding.get("end"), "finding end")
    if end < start:
        raise ValueError("finding end must not precede start")
    return SourceFinding(
        category=_string(finding.get("category"), "finding category"),
        start=start,
        end=end,
        original=_text(finding.get("original"), "finding original"),
        suggestion=_text(finding.get("suggestion"), "finding suggestion"),
        rule_family=_optional_string(finding.get("rule_family"), "finding rule family"),
    )


def _controlled_error(
    case: _ParsedCase, errors: tuple[SourceError, ...]
) -> SourceError | None:
    if case.pair_id is None or len(errors) != 1:
        return None
    error = errors[0]
    if len(error.findings) != 1:
        return None
    finding = error.findings[0]
    if (
        finding.start > len(error.text)
        or finding.end > len(error.text)
        or error.text[finding.start : finding.end] != finding.original
    ):
        return None
    reconstructed = (
        error.text[: finding.start] + finding.suggestion + error.text[finding.end :]
    )
    return error if reconstructed == case.text else None


def _source_error(case: _ParsedCase) -> SourceError:
    return SourceError(
        case_id=case.case_id,
        kind=case.kind,
        phenomenon=case.phenomenon,
        category=case.category,
        features=case.features,
        shape_strata=case.shape_strata,
        pair_id=case.pair_id,
        text=case.text,
        findings=case.findings,
    )


def _string_set(value: object, label: str) -> frozenset[str]:
    if value is None:
        return frozenset()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    return frozenset(value)


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _offset(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _json_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value
