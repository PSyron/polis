"""Strict schema and isolation gates for the licensed fine-tuning dataset."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final, Literal, cast

from polis.evaluation.correction_corpus import (
    EntitySpan as CorpusEntitySpan,
)
from polis.evaluation.correction_corpus import (
    IsolationRecord,
    assert_no_training_leakage,
    load_correction_corpus_json,
)
from polis.llm import (
    FiniteCandidate,
    build_inflection_candidate_prompt_request,
    build_specialist_corrected_text_prompt_request,
)
from polis.llm.corrected_text import SpecialistFocus

DatasetCategory = Literal["inflection", "syntax", "punctuation", "no_change"]
DatasetSplit = Literal["train", "validation"]

DATASET_CATEGORIES: Final[tuple[DatasetCategory, ...]] = (
    "inflection",
    "syntax",
    "punctuation",
    "no_change",
)
BIELIK_BOS_TOKEN: Final[str] = "<s>"
_SCHEMA_VERSION: Final[int] = 1
_LICENSE: Final[str] = "CC0-1.0"
_EXPECTED_COUNTS: Final[dict[DatasetSplit, int]] = {
    "train": 1_200,
    "validation": 240,
}
_EXPECTED_PER_CATEGORY: Final[dict[DatasetSplit, int]] = {
    "train": 300,
    "validation": 60,
}
_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "id",
        "split",
        "category",
        "protocol_id",
        "focus",
        "source_text",
        "target",
        "candidates",
        "messages",
        "chatml",
        "transformation_id",
        "template_id",
        "entity_spans",
        "tags",
        "provenance",
        "review",
    }
)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class FinetuningTarget:
    candidate_id: str | None = None
    corrected_text: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetEntitySpan:
    start: int
    end: int
    surface: str
    identity: str


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    source: str
    license: str
    gold_source: str
    model_generated: bool


@dataclass(frozen=True, slots=True)
class DatasetReview:
    state: str
    method: str
    checklist_version: str


@dataclass(frozen=True, slots=True)
class FinetuningRecord:
    schema_version: int
    id: str
    split: DatasetSplit
    category: DatasetCategory
    protocol_id: str
    focus: str
    source_text: str
    target: FinetuningTarget
    candidates: tuple[FiniteCandidate, ...]
    messages: tuple[ChatMessage, ...]
    chatml: str
    transformation_id: str
    template_id: str
    entity_spans: tuple[DatasetEntitySpan, ...]
    tags: tuple[str, ...]
    provenance: DatasetProvenance
    review: DatasetReview


@dataclass(frozen=True, slots=True)
class FinetuningDataset:
    train: tuple[FinetuningRecord, ...]
    validation: tuple[FinetuningRecord, ...]
    manifest: dict[str, object]


def render_bielik_chatml(
    messages: Sequence[ChatMessage] | Sequence[Mapping[str, object]],
) -> str:
    """Render messages with the official Bielik 1.5B v3 ChatML template."""

    rendered = [BIELIK_BOS_TOKEN]
    for raw_message in messages:
        if isinstance(raw_message, ChatMessage):
            role = raw_message.role
            content = raw_message.content
        else:
            role = _require_string(raw_message.get("role"), "message role")
            content = _require_string(raw_message.get("content"), "message content")
        if role not in {"system", "user", "assistant"}:
            raise ValueError("message role is unsupported")
        if "<|im_start|>" in content or "<|im_end|>" in content:
            raise ValueError("message content contains reserved ChatML token")
        rendered.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    return "".join(rendered)


def load_finetuning_bundle(
    directory: Path,
    *,
    evaluation_corpus_path: Path,
) -> FinetuningDataset:
    """Load, validate, and verify one committed fine-tuning bundle."""

    train_path = directory / "train.jsonl"
    validation_path = directory / "validation.jsonl"
    train = validate_finetuning_records(_load_jsonl(train_path), expected_split="train")
    validation = validate_finetuning_records(
        _load_jsonl(validation_path), expected_split="validation"
    )
    _validate_bundle_counts(train, validation)
    _validate_cross_split_isolation(train, validation)
    _validate_evaluation_isolation(
        (*train, *validation), evaluation_corpus_path=evaluation_corpus_path
    )
    _validate_negative_coverage(train, "train")
    _validate_negative_coverage(validation, "validation")

    manifest_path = directory / "manifest.json"
    manifest_raw = _load_json(manifest_path)
    manifest = _require_mapping(manifest_raw, "manifest")
    expected_manifest = build_finetuning_manifest(
        train,
        validation,
        train_sha256=_sha256(train_path),
        validation_sha256=_sha256(validation_path),
    )
    if manifest != expected_manifest:
        raise ValueError("fine-tuning manifest does not match dataset statistics")
    return FinetuningDataset(train, validation, dict(manifest))


def validate_finetuning_records(
    raw_records: Iterable[object],
    *,
    expected_split: DatasetSplit,
) -> tuple[FinetuningRecord, ...]:
    """Validate fine-tuning records with a closed, versioned schema."""

    records: list[FinetuningRecord] = []
    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    for raw in raw_records:
        record = _validate_record(raw, expected_split)
        if record.id in seen_ids:
            raise ValueError(f"duplicate record id: {record.id}")
        normalized_source = " ".join(record.source_text.casefold().split())
        if normalized_source in seen_sources:
            raise ValueError(f"duplicate source text: {record.id}")
        seen_ids.add(record.id)
        seen_sources.add(normalized_source)
        records.append(record)
    if not records:
        raise ValueError("fine-tuning split must not be empty")
    return tuple(records)


def build_finetuning_manifest(
    train: Sequence[FinetuningRecord],
    validation: Sequence[FinetuningRecord],
    *,
    train_sha256: str,
    validation_sha256: str,
) -> dict[str, object]:
    """Build deterministic statistics and audit state for a dataset bundle."""

    split_records = {"train": train, "validation": validation}
    return {
        "schema_version": _SCHEMA_VERSION,
        "dataset_id": "polis-bielik-1.5b-correction-v1",
        "license": _LICENSE,
        "record_counts": {
            split: len(records) for split, records in split_records.items()
        },
        "category_counts": {
            split: dict(sorted(Counter(r.category for r in records).items()))
            for split, records in split_records.items()
        },
        "protocol_counts": {
            split: dict(sorted(Counter(r.protocol_id for r in records).items()))
            for split, records in split_records.items()
        },
        "review_state_counts": {
            split: dict(sorted(Counter(r.review.state for r in records).items()))
            for split, records in split_records.items()
        },
        "negative_tag_counts": {
            split: dict(
                sorted(
                    Counter(
                        tag
                        for record in records
                        if record.category == "no_change"
                        for tag in record.tags
                    ).items()
                )
            )
            for split, records in split_records.items()
        },
        "corpus_v3_isolation": "passed",
        "files": {
            "train.jsonl": {"sha256": train_sha256},
            "validation.jsonl": {"sha256": validation_sha256},
        },
    }


def _validate_record(raw: object, expected_split: DatasetSplit) -> FinetuningRecord:
    item = _require_mapping(raw, "record")
    _require_exact_fields(item, _RECORD_FIELDS, "record")
    if item["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("record schema_version must be 1")
    record_id = _require_string(item["id"], "record id")
    split = item["split"]
    if split != expected_split:
        raise ValueError(f"record {record_id} has unexpected split")
    category = item["category"]
    if category not in DATASET_CATEGORIES:
        raise ValueError(f"record {record_id} category is unsupported")
    typed_category = category
    source_text = _require_string(item["source_text"], "source_text")
    focus = _require_string(item["focus"], "focus")
    if focus not in {"inflection", "syntax", "punctuation"}:
        raise ValueError("record focus is unsupported")

    target = _validate_target(item["target"], typed_category)
    candidates = _validate_candidates(item["candidates"], source_text)
    protocol_id = _require_string(item["protocol_id"], "protocol_id")
    expected_protocol = (
        "specialist-candidate-selection"
        if typed_category == "inflection"
        else "specialist-corrected-text"
    )
    if protocol_id != expected_protocol:
        raise ValueError("record protocol_id does not match category")

    messages = _validate_messages(item["messages"])
    _validate_prompt_contract(
        messages,
        protocol_id=protocol_id,
        focus=focus,
        source_text=source_text,
        candidates=candidates,
    )
    expected_answer = json.dumps(
        _target_as_json(target), ensure_ascii=False, separators=(",", ":")
    )
    if messages[2].content != expected_answer:
        raise ValueError("assistant message does not match target")
    chatml = _require_string(item["chatml"], "chatml")
    if chatml != render_bielik_chatml(messages):
        raise ValueError("stored ChatML does not match messages")

    entity_spans = _validate_entity_spans(item["entity_spans"], source_text)
    tags = _validate_string_sequence(item["tags"], "tags")
    provenance = _validate_provenance(item["provenance"])
    review = _validate_review(item["review"])
    _validate_target_behavior(typed_category, source_text, target, candidates)

    return FinetuningRecord(
        schema_version=_SCHEMA_VERSION,
        id=record_id,
        split=split,
        category=typed_category,
        protocol_id=protocol_id,
        focus=focus,
        source_text=source_text,
        target=target,
        candidates=candidates,
        messages=messages,
        chatml=chatml,
        transformation_id=_require_string(
            item["transformation_id"], "transformation_id"
        ),
        template_id=_require_string(item["template_id"], "template_id"),
        entity_spans=entity_spans,
        tags=tags,
        provenance=provenance,
        review=review,
    )


def _validate_target(raw: object, category: DatasetCategory) -> FinetuningTarget:
    item = _require_mapping(raw, "target")
    if category == "inflection":
        _require_exact_fields(item, frozenset({"candidate_id"}), "target")
        return FinetuningTarget(
            candidate_id=_require_string(item["candidate_id"], "candidate_id")
        )
    _require_exact_fields(item, frozenset({"corrected_text"}), "target")
    return FinetuningTarget(
        corrected_text=_require_string(item["corrected_text"], "corrected_text")
    )


def _validate_candidates(raw: object, source_text: str) -> tuple[FiniteCandidate, ...]:
    if not isinstance(raw, list):
        raise ValueError("candidates must be a list")
    candidates: list[FiniteCandidate] = []
    for item_raw in raw:
        item = _require_mapping(item_raw, "candidate")
        _require_exact_fields(
            item,
            frozenset({"candidate_id", "start", "end", "form", "lemma", "features"}),
            "candidate",
        )
        features = _validate_string_sequence(item["features"], "candidate features")
        start = _require_int(item["start"], "candidate start")
        end = _require_int(item["end"], "candidate end")
        candidates.append(
            FiniteCandidate(
                _require_string(item["candidate_id"], "candidate_id"),
                start,
                end,
                _require_string(item["form"], "candidate form"),
                _require_optional_string(item["lemma"], "candidate lemma"),
                features,
            )
        )
    if candidates:
        build_inflection_candidate_prompt_request(source_text, tuple(candidates))
    return tuple(candidates)


def _validate_messages(raw: object) -> tuple[ChatMessage, ...]:
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError("messages must contain system, user, and assistant")
    messages: list[ChatMessage] = []
    for item_raw in raw:
        item = _require_mapping(item_raw, "message")
        _require_exact_fields(item, frozenset({"role", "content"}), "message")
        messages.append(
            ChatMessage(
                _require_string(item["role"], "message role"),
                _require_string(item["content"], "message content"),
            )
        )
    if tuple(message.role for message in messages) != (
        "system",
        "user",
        "assistant",
    ):
        raise ValueError("messages must be ordered system, user, assistant")
    return tuple(messages)


def _validate_prompt_contract(
    messages: tuple[ChatMessage, ...],
    *,
    protocol_id: str,
    focus: str,
    source_text: str,
    candidates: tuple[FiniteCandidate, ...],
) -> None:
    if protocol_id == "specialist-candidate-selection":
        if not candidates:
            raise ValueError("inflection record requires candidates")
        request = build_inflection_candidate_prompt_request(source_text, candidates)
    else:
        if candidates:
            raise ValueError("corrected-text record cannot contain candidates")
        request = build_specialist_corrected_text_prompt_request(
            source_text,
            focus=cast(SpecialistFocus, focus),
        )
    expected = tuple(ChatMessage(**message) for message in request.messages)
    if messages[:2] != expected:
        raise ValueError("messages do not match selected prompt contract")


def _validate_entity_spans(
    raw: object, source_text: str
) -> tuple[DatasetEntitySpan, ...]:
    if not isinstance(raw, list):
        raise ValueError("entity_spans must be a list")
    spans: list[DatasetEntitySpan] = []
    previous_end = -1
    for item_raw in raw:
        item = _require_mapping(item_raw, "entity span")
        _require_exact_fields(
            item, frozenset({"start", "end", "surface", "identity"}), "entity span"
        )
        start = _require_int(item["start"], "entity start")
        end = _require_int(item["end"], "entity end")
        surface = _require_string(item["surface"], "entity surface")
        identity = _require_string(item["identity"], "entity identity")
        if start < 0 or end <= start or end > len(source_text) or start < previous_end:
            raise ValueError("entity span offsets are invalid")
        if source_text[start:end] != surface:
            raise ValueError("entity span surface does not match source_text")
        spans.append(DatasetEntitySpan(start, end, surface, identity))
        previous_end = end
    return tuple(spans)


def _validate_provenance(raw: object) -> DatasetProvenance:
    item = _require_mapping(raw, "provenance")
    _require_exact_fields(
        item,
        frozenset({"source", "license", "gold_source", "model_generated"}),
        "provenance",
    )
    if item["license"] != _LICENSE:
        raise ValueError("dataset record license must be CC0-1.0")
    if item["model_generated"] is not False:
        raise ValueError("model-generated gold is prohibited")
    gold_source = _require_string(item["gold_source"], "gold_source")
    if gold_source not in {
        "reviewed-linguistic-transformation",
        "project-authored-correction",
    }:
        raise ValueError("gold_source is unsupported")
    return DatasetProvenance(
        _require_string(item["source"], "provenance source"),
        _LICENSE,
        gold_source,
        False,
    )


def _validate_review(raw: object) -> DatasetReview:
    item = _require_mapping(raw, "review")
    _require_exact_fields(
        item, frozenset({"state", "method", "checklist_version"}), "review"
    )
    state = _require_string(item["state"], "review state")
    if state not in {
        "transformation-reviewed",
        "authored-correction-reviewed",
    }:
        raise ValueError("review state is unsupported")
    return DatasetReview(
        state,
        _require_string(item["method"], "review method"),
        _require_string(item["checklist_version"], "review checklist_version"),
    )


def _validate_target_behavior(
    category: DatasetCategory,
    source_text: str,
    target: FinetuningTarget,
    candidates: tuple[FiniteCandidate, ...],
) -> None:
    if category == "inflection":
        selected = next(
            (
                candidate
                for candidate in candidates
                if candidate.candidate_id == target.candidate_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("target candidate_id is not in candidates")
        if selected.form == source_text[selected.start : selected.end]:
            raise ValueError("positive record must change source text")
        return
    corrected = cast(str, target.corrected_text)
    if category == "no_change":
        if corrected != source_text:
            raise ValueError("no_change target must preserve source text")
        return
    if corrected == source_text:
        raise ValueError("positive record must change source text")
    matcher = SequenceMatcher(a=source_text, b=corrected, autojunk=False)
    if matcher.ratio() < 0.72 or abs(len(source_text) - len(corrected)) > 24:
        raise ValueError("unsafe rewrite is not a minimal correction")
    changed = "".join(
        source_text[a:b] + corrected[c:d]
        for tag, a, b, c, d in matcher.get_opcodes()
        if tag != "equal"
    )
    if category == "punctuation" and any(char.isalnum() for char in changed):
        raise ValueError("unsafe rewrite changes words in punctuation record")


def _validate_bundle_counts(
    train: tuple[FinetuningRecord, ...], validation: tuple[FinetuningRecord, ...]
) -> None:
    split_records: tuple[tuple[DatasetSplit, tuple[FinetuningRecord, ...]], ...] = (
        ("train", train),
        ("validation", validation),
    )
    for split, records in split_records:
        if len(records) != _EXPECTED_COUNTS[split]:
            raise ValueError(f"{split} record count is invalid")
        counts = Counter(record.category for record in records)
        if counts != Counter(
            {category: _EXPECTED_PER_CATEGORY[split] for category in DATASET_CATEGORIES}
        ):
            raise ValueError(f"{split} category balance is invalid")


def _validate_cross_split_isolation(
    train: tuple[FinetuningRecord, ...], validation: tuple[FinetuningRecord, ...]
) -> None:
    train_sources = {
        " ".join(record.source_text.casefold().split()) for record in train
    }
    validation_sources = {
        " ".join(record.source_text.casefold().split()) for record in validation
    }
    if not train_sources.isdisjoint(validation_sources):
        raise ValueError("source leakage across fine-tuning splits")
    if not {r.template_id for r in train}.isdisjoint(
        {r.template_id for r in validation}
    ):
        raise ValueError("template leakage across fine-tuning splits")
    train_entities = {span.identity for record in train for span in record.entity_spans}
    validation_entities = {
        span.identity for record in validation for span in record.entity_spans
    }
    if not train_entities.isdisjoint(validation_entities):
        raise ValueError("entity leakage across fine-tuning splits")


def _validate_evaluation_isolation(
    records: Sequence[FinetuningRecord], *, evaluation_corpus_path: Path
) -> None:
    corpus = load_correction_corpus_json(evaluation_corpus_path)
    isolation_records = tuple(
        IsolationRecord(
            record.id,
            record.source_text,
            tuple(
                CorpusEntitySpan(span.start, span.end, span.surface)
                for span in record.entity_spans
            ),
        )
        for record in records
    )
    assert_no_training_leakage(corpus, isolation_records)
    expected_outputs = {
        " ".join(case.expected_output.casefold().split()) for case in corpus.cases
    }
    for record in records:
        output = _record_output(record)
        if " ".join(output.casefold().split()) in expected_outputs:
            raise ValueError(f"evaluation expected-output leakage in {record.id}")


def _validate_negative_coverage(
    records: tuple[FinetuningRecord, ...], split: DatasetSplit
) -> None:
    required = {
        "correct-inflection",
        "proper-name",
        "marked-word-order",
        "correct-punctuation",
        "number",
        "url",
        "quotation",
    }
    present = {
        tag
        for record in records
        if record.category == "no_change"
        for tag in record.tags
    }
    if not required <= present:
        raise ValueError(f"{split} no_change coverage is incomplete")


def _record_output(record: FinetuningRecord) -> str:
    if record.target.corrected_text is not None:
        return record.target.corrected_text
    selected = next(
        candidate
        for candidate in record.candidates
        if candidate.candidate_id == record.target.candidate_id
    )
    return cast(
        str,
        record.source_text[: selected.start]
        + selected.form
        + record.source_text[selected.end :],
    )


def _target_as_json(target: FinetuningTarget) -> dict[str, str]:
    if target.candidate_id is not None:
        return {"candidate_id": target.candidate_id}
    return {"corrected_text": cast(str, target.corrected_text)}


def _load_jsonl(path: Path) -> list[object]:
    records: list[object] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"cannot read fine-tuning data: {path}") from error
    for number, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at {path}:{number}") from error
    return records


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read valid JSON: {path}") from error


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _require_exact_fields(
    value: Mapping[str, object], expected: frozenset[str], label: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} fields are malformed")


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, label)


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _validate_string_sequence(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a sequence")
    items = tuple(_require_string(item, label) for item in value)
    if len(set(items)) != len(items):
        raise ValueError(f"{label} contains duplicates")
    return items


__all__ = [
    "BIELIK_BOS_TOKEN",
    "DATASET_CATEGORIES",
    "ChatMessage",
    "DatasetEntitySpan",
    "DatasetProvenance",
    "DatasetReview",
    "FinetuningDataset",
    "FinetuningRecord",
    "FinetuningTarget",
    "build_finetuning_manifest",
    "load_finetuning_bundle",
    "render_bielik_chatml",
    "validate_finetuning_records",
]
