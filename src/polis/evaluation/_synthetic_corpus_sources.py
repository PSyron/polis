from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, cast

_SOURCE_PATHS: Final = (
    "quality/v1/cases.json",
    "quality/v2/cases.json",
    "quality/v3/cases.json",
    "quality/v4/cases.json",
)


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
class SourceText:
    metadata: SourceMetadata
    case_id: str
    text: str


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
        metadata = SourceMetadata(
            dataset_id=dataset_id,
            dataset_version=version,
            path=relative_path,
            sha256=sha256(raw_bytes).hexdigest(),
            license="CC0-1.0",
            source="project-authored",
            clean_case_count=sum(
                1
                for item in raw_cases
                if isinstance(item, dict) and item.get("kind") == "correct"
            ),
        )
        for item in raw_cases:
            case = _json_object(item, "dataset case")
            if case.get("kind") != "correct":
                continue
            texts.append(
                SourceText(
                    metadata=metadata,
                    case_id=_string(case.get("id"), "case id"),
                    text=_string(case.get("text"), "case text"),
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
        SourceText(metadata=metadata, case_id=f"provided_{index:05d}", text=text)
        for index, text in enumerate(texts, start=1)
    )


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
