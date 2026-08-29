from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from polis.evaluation._synthetic_corpus_validation import validate_single_edit

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

_CORPUS_KEYS: Final = frozenset(
    {
        "id",
        "error_class",
        "incorrect_text",
        "correct_text",
        "start",
        "end",
        "original",
        "suggestion",
        "source_dataset",
        "source_case_id",
        "lemma",
        "generated_tag",
    }
)
_CORPUS_REQUIRED_KEYS: Final = _CORPUS_KEYS - {"lemma", "generated_tag"}
_ERROR_CLASSES: Final = frozenset({"case", "agreement", "punctuation", "diacritics"})
_PREDICTION_KEYS: Final = frozenset({"pair_id", "edits"})
_EDIT_KEYS: Final = frozenset({"start", "end", "replacement"})
_COVERAGE_KEYS: Final = frozenset(
    {
        "phenomenon_counts",
        "shape_strata_counts",
        "hard_negative_count",
        "rejected_counts",
    }
)
_IDENTITY_KEYS: Final = frozenset(
    {"pair_ids", "source_case_ids", "correct_text_sha256"}
)


class BenchmarkInputError(ValueError):
    pass


class Score(TypedDict):
    total: int
    accepted: int
    abstained: int


class Coverage(TypedDict):
    phenomenon_counts: dict[str, int]
    shape_strata_counts: dict[str, int]
    hard_negative_count: int
    rejected_counts: NotRequired[dict[str, int]]


class SplitIdentity(TypedDict):
    source_case_ids: list[str]
    correct_text_sha256: list[str]
    pair_ids: NotRequired[list[str]]


class Split(TypedDict):
    development: SplitIdentity
    test: SplitIdentity


class BenchmarkReport(TypedDict):
    profile: str
    generator_version: str
    score: Score
    by_error_class: dict[str, Score]
    coverage: Coverage
    split: Split


@dataclass(frozen=True, slots=True)
class _CorpusPair:
    pair_id: str
    error_class: str
    incorrect_text: str
    correct_text: str
    source_case_id: str


@dataclass(frozen=True, slots=True)
class _Edit:
    start: int
    end: int
    replacement: str


@dataclass(frozen=True, slots=True)
class _Prediction:
    pair_id: str
    edit: _Edit | None


@dataclass(frozen=True, slots=True)
class _Manifest:
    profile: str
    generator_version: str
    coverage: Coverage
    split: Split


def evaluate_benchmark(
    corpus_path: Path, predictions_path: Path, manifest_path: Path
) -> BenchmarkReport:
    corpus_bytes = corpus_path.read_bytes()
    pairs = _parse_corpus(_decode(corpus_bytes, "corpus"))
    manifest = _parse_manifest(
        _read_json(manifest_path, "manifest"), corpus_bytes, pairs
    )
    predictions = _parse_predictions(predictions_path, pairs)
    return BenchmarkReport(
        profile=manifest.profile,
        generator_version=manifest.generator_version,
        score=_score(pairs, predictions),
        by_error_class={
            error_class: _score(
                tuple(pair for pair in pairs if pair.error_class == error_class),
                predictions,
            )
            for error_class in sorted({pair.error_class for pair in pairs})
        },
        coverage=manifest.coverage,
        split=manifest.split,
    )


def _parse_corpus(text: str) -> tuple[_CorpusPair, ...]:
    records = _parse_jsonl(text, "corpus")
    pairs = tuple(_parse_pair(record) for record in records)
    pair_ids = [pair.pair_id for pair in pairs]
    if not pairs or len(pair_ids) != len(set(pair_ids)):
        raise BenchmarkInputError("corpus IDs must be unique")
    return pairs


def _parse_pair(value: JsonValue) -> _CorpusPair:
    record = _mapping(value, "corpus record")
    if not _CORPUS_REQUIRED_KEYS <= record.keys() or not record.keys() <= _CORPUS_KEYS:
        raise BenchmarkInputError("corpus record has invalid fields")
    pair_id = _string(record, "id", nonempty=True)
    error_class = _string(record, "error_class", nonempty=True)
    incorrect = _string(record, "incorrect_text")
    correct = _string(record, "correct_text")
    start = _integer(record, "start")
    end = _integer(record, "end")
    original = _string(record, "original")
    suggestion = _string(record, "suggestion")
    source_case_id = _string(record, "source_case_id", nonempty=True)
    _string(record, "source_dataset", nonempty=True)
    _optional_string(record, "lemma")
    _optional_string(record, "generated_tag")
    if error_class not in _ERROR_CLASSES or not validate_single_edit(
        incorrect,
        correct,
        start=start,
        end=end,
        original=original,
        suggestion=suggestion,
    ):
        raise BenchmarkInputError("corpus record violates the validated profile")
    return _CorpusPair(pair_id, error_class, incorrect, correct, source_case_id)


def _parse_manifest(
    value: JsonValue, corpus_bytes: bytes, pairs: tuple[_CorpusPair, ...]
) -> _Manifest:
    record = _mapping(value, "manifest")
    expected_strings = {
        "schema_id": "polis.synthetic-corpus-manifest",
        "profile": "validated",
        "generator_version": "polis-synthetic-corpus-v2-validated",
        "purpose": "repeatable-development-only",
    }
    if any(
        _string(record, key, nonempty=True) != expected
        for key, expected in expected_strings.items()
    ):
        raise BenchmarkInputError("manifest is outside the validated profile boundary")
    if _integer(record, "schema_version") != 1 or record.get("holdout") is not False:
        raise BenchmarkInputError("manifest is outside the validated holdout boundary")
    seed = _integer(record, "seed")
    requested_count = _integer(record, "requested_count")
    pair_count = _integer(record, "pair_count")
    if seed < 0 or requested_count < pair_count or pair_count != len(pairs):
        raise BenchmarkInputError("manifest counts are inconsistent")
    for key in ("artifact_sha256", "license", "source"):
        _string(record, key, nonempty=True)
    if record.get("artifact_sha256") != sha256(corpus_bytes).hexdigest():
        raise BenchmarkInputError("manifest corpus identity is inconsistent")
    if _counts(record.get("class_counts"), "manifest class counts") != {
        error_class: sum(pair.error_class == error_class for pair in pairs)
        for error_class in sorted({pair.error_class for pair in pairs})
    }:
        raise BenchmarkInputError("manifest class counts are inconsistent")
    coverage = _coverage(record.get("coverage"))
    split = _split(record.get("split"), pairs)
    return _Manifest(
        "validated", expected_strings["generator_version"], coverage, split
    )


def _coverage(value: JsonValue) -> Coverage:
    record = _mapping(value, "manifest coverage")
    if (
        not {"phenomenon_counts", "shape_strata_counts", "hard_negative_count"}
        <= record.keys()
        or not record.keys() <= _COVERAGE_KEYS
    ):
        raise BenchmarkInputError("manifest coverage has invalid fields")
    hard_negative_count = _integer(record, "hard_negative_count")
    if hard_negative_count < 0:
        raise BenchmarkInputError("manifest coverage counts must be non-negative")
    result = Coverage(
        phenomenon_counts=_counts(record.get("phenomenon_counts"), "phenomenon counts"),
        shape_strata_counts=_counts(
            record.get("shape_strata_counts"), "shape strata counts"
        ),
        hard_negative_count=hard_negative_count,
    )
    if "rejected_counts" in record:
        result["rejected_counts"] = _counts(
            record["rejected_counts"], "rejected counts"
        )
    return result


def _split(value: JsonValue, pairs: tuple[_CorpusPair, ...]) -> Split:
    record = _mapping(value, "source-disjoint split")
    if set(record) != {"development", "test"}:
        raise _split_error()
    development = _identity(record["development"])
    test = _identity(record["test"])
    identities = (development, test)
    for key in ("source_case_ids", "correct_text_sha256"):
        if set(identities[0][key]) & set(identities[1][key]):
            raise _split_error()
    pair_id_presence = tuple("pair_ids" in identity for identity in identities)
    if pair_id_presence not in {(False, False), (True, True)}:
        raise _split_error()
    corpus_ids = {pair.pair_id for pair in pairs}
    corpus_sources = {pair.source_case_id for pair in pairs}
    corpus_hashes = {_digest(pair.correct_text) for pair in pairs}
    if (
        set(development["source_case_ids"]) | set(test["source_case_ids"])
        != corpus_sources
        or set(development["correct_text_sha256"]) | set(test["correct_text_sha256"])
        != corpus_hashes
    ):
        raise _split_error()
    if pair_id_presence == (True, True):
        development_ids = set(development["pair_ids"])
        test_ids = set(test["pair_ids"])
        if development_ids & test_ids or development_ids | test_ids != corpus_ids:
            raise _split_error()
        by_id = {pair.pair_id: pair for pair in pairs}
        for identity, pair_ids in ((development, development_ids), (test, test_ids)):
            selected = tuple(by_id[pair_id] for pair_id in pair_ids)
            if set(identity["source_case_ids"]) != {
                pair.source_case_id for pair in selected
            } or set(identity["correct_text_sha256"]) != {
                _digest(pair.correct_text) for pair in selected
            }:
                raise _split_error()
    return Split(development=development, test=test)


def _identity(value: JsonValue) -> SplitIdentity:
    record = _mapping(value, "source-disjoint split identity")
    if (
        not {"source_case_ids", "correct_text_sha256"} <= record.keys()
        or not record.keys() <= _IDENTITY_KEYS
    ):
        raise _split_error()
    source_case_ids = _strings(record["source_case_ids"])
    correct_text_sha256 = _strings(record["correct_text_sha256"])
    pair_ids = _strings(record["pair_ids"]) if "pair_ids" in record else None
    identity_values = (source_case_ids, correct_text_sha256)
    if any(not values or len(values) != len(set(values)) for values in identity_values):
        raise _split_error()
    if any(
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in correct_text_sha256
    ):
        raise _split_error()
    result = SplitIdentity(
        source_case_ids=source_case_ids,
        correct_text_sha256=correct_text_sha256,
    )
    if pair_ids is not None:
        if not pair_ids or len(pair_ids) != len(set(pair_ids)):
            raise _split_error()
        result["pair_ids"] = pair_ids
    return result


def _parse_predictions(
    path: Path, pairs: tuple[_CorpusPair, ...]
) -> dict[str, _Prediction]:
    records = _parse_jsonl(_decode(path.read_bytes(), "predictions"), "predictions")
    pair_by_id = {pair.pair_id: pair for pair in pairs}
    predictions = tuple(_parse_prediction(record, pair_by_id) for record in records)
    ids = [prediction.pair_id for prediction in predictions]
    if len(ids) != len(set(ids)):
        raise BenchmarkInputError("prediction IDs must be unique")
    if set(ids) != set(pair_by_id):
        raise BenchmarkInputError("predictions must cover every corpus ID exactly once")
    return {prediction.pair_id: prediction for prediction in predictions}


def _parse_prediction(
    value: JsonValue, pair_by_id: dict[str, _CorpusPair]
) -> _Prediction:
    record = _mapping(value, "prediction record")
    if set(record) != _PREDICTION_KEYS:
        raise BenchmarkInputError("prediction record has invalid fields")
    pair_id = _string(record, "pair_id", nonempty=True)
    if pair_id not in pair_by_id:
        raise BenchmarkInputError("prediction references an unknown corpus ID")
    edits = record["edits"]
    if not isinstance(edits, list) or len(edits) > 1:
        raise BenchmarkInputError("prediction edits must contain zero or one edit")
    if not edits:
        return _Prediction(pair_id, None)
    edit_record = _mapping(edits[0], "prediction edit")
    if set(edit_record) != _EDIT_KEYS:
        raise BenchmarkInputError("prediction edit has invalid fields")
    start = _integer(edit_record, "start")
    end = _integer(edit_record, "end")
    replacement = _string(edit_record, "replacement")
    if start < 0 or end < start or end > len(pair_by_id[pair_id].incorrect_text):
        raise BenchmarkInputError("prediction edit span is outside the corpus text")
    return _Prediction(pair_id, _Edit(start, end, replacement))


def _score(
    pairs: tuple[_CorpusPair, ...], predictions: dict[str, _Prediction]
) -> Score:
    abstained = sum(predictions[pair.pair_id].edit is None for pair in pairs)
    accepted = sum(_accepted(pair, predictions[pair.pair_id]) for pair in pairs)
    return Score(total=len(pairs), accepted=accepted, abstained=abstained)


def _accepted(pair: _CorpusPair, prediction: _Prediction) -> bool:
    edit = prediction.edit
    if edit is None:
        return False
    return bool(
        validate_single_edit(
            pair.incorrect_text,
            pair.correct_text,
            start=edit.start,
            end=edit.end,
            original=pair.incorrect_text[edit.start : edit.end],
            suggestion=edit.replacement,
        )
    )


def _parse_jsonl(text: str, label: str) -> tuple[JsonValue, ...]:
    records: list[JsonValue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise BenchmarkInputError(f"{label} JSONL contains a blank line")
        try:
            value: JsonValue = json.loads(line)
        except json.JSONDecodeError as error:
            raise BenchmarkInputError(
                f"{label} JSON is invalid on line {line_number}"
            ) from error
        records.append(value)
    return tuple(records)


def _read_json(path: Path, label: str) -> JsonValue:
    text = _decode(path.read_bytes(), label)
    try:
        value: JsonValue = json.loads(text)
    except json.JSONDecodeError as error:
        raise BenchmarkInputError(f"{label} JSON is invalid") from error
    return value


def _decode(value: bytes, label: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BenchmarkInputError(f"{label} is not valid UTF-8") from error


def _mapping(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise BenchmarkInputError(f"{label} must be a JSON object")
    return value


def _string(record: dict[str, JsonValue], key: str, *, nonempty: bool = False) -> str:
    value = record.get(key)
    if not isinstance(value, str) or (nonempty and not value):
        raise BenchmarkInputError("required string field is invalid")
    return value


def _optional_string(record: dict[str, JsonValue], key: str) -> None:
    value = record.get(key)
    if value is not None and not isinstance(value, str):
        raise BenchmarkInputError("optional string field is invalid")


def _integer(record: dict[str, JsonValue], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise BenchmarkInputError("required integer field is invalid")
    return value


def _counts(value: JsonValue, label: str) -> dict[str, int]:
    record = _mapping(value, label)
    if any(
        not key or type(count) is not int or count < 0 for key, count in record.items()
    ):
        raise BenchmarkInputError(f"{label} must contain non-negative integer counts")
    return {key: count for key, count in record.items() if type(count) is int}


def _strings(value: JsonValue) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise _split_error()
    return [item for item in value if isinstance(item, str)]


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _split_error() -> BenchmarkInputError:
    return BenchmarkInputError("source-disjoint split metadata is inconsistent")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = evaluate_benchmark(
            arguments.corpus, arguments.predictions, arguments.manifest
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(
                report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n",
            encoding="utf-8",
        )
    except BenchmarkInputError as error:
        print(f"synthetic benchmark input error: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("synthetic benchmark I/O error", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
