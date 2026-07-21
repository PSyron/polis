from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from polis.evaluation.finetuning_dataset import (
    BIELIK_BOS_TOKEN,
    DATASET_CATEGORIES,
    FinetuningDataset,
    FinetuningRecord,
    load_finetuning_bundle,
    render_bielik_chatml,
    validate_finetuning_records,
)

ROOT = Path(__file__).parents[1]
BUNDLE = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
CORPUS_V3 = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)


@pytest.fixture(scope="module")
def dataset() -> FinetuningDataset:
    return load_finetuning_bundle(BUNDLE, evaluation_corpus_path=CORPUS_V3)


def test_bundle_has_exact_split_counts_and_category_balance(
    dataset: FinetuningDataset,
) -> None:
    assert len(dataset.train) == 1_200
    assert len(dataset.validation) == 240
    assert Counter(record.category for record in dataset.train) == {
        category: 300 for category in DATASET_CATEGORIES
    }
    assert Counter(record.category for record in dataset.validation) == {
        category: 60 for category in DATASET_CATEGORIES
    }


def test_records_are_cc0_non_model_gold_with_reviewed_transformations(
    dataset: FinetuningDataset,
) -> None:
    for record in (*dataset.train, *dataset.validation):
        assert record.provenance.license == "CC0-1.0"
        assert record.provenance.model_generated is False
        assert record.provenance.gold_source in {
            "reviewed-linguistic-transformation",
            "project-authored-correction",
        }
        assert record.review.state in {
            "transformation-reviewed",
            "authored-correction-reviewed",
        }


def test_messages_and_stored_chatml_follow_selected_contracts(
    dataset: FinetuningDataset,
) -> None:
    for record in (*dataset.train[:8], *dataset.validation[:8]):
        assert tuple(message.role for message in record.messages) == (
            "system",
            "user",
            "assistant",
        )
        assert record.chatml == render_bielik_chatml(record.messages)
        assert record.chatml.startswith(f"{BIELIK_BOS_TOKEN}<|im_start|>system\n")
        assert record.chatml.endswith("<|im_end|>\n")
        assert "<INPUT_JSON_START>" in record.messages[1].content
        assert record.protocol_id in {
            "specialist-candidate-selection",
            "specialist-corrected-text",
        }


def test_positive_targets_change_text_and_no_change_targets_preserve_it(
    dataset: FinetuningDataset,
) -> None:
    for record in (*dataset.train, *dataset.validation):
        if record.category == "inflection":
            assert record.target.candidate_id is not None
            selected = next(
                candidate
                for candidate in record.candidates
                if candidate.candidate_id == record.target.candidate_id
            )
            assert selected.form != record.source_text[selected.start : selected.end]
        elif record.category == "no_change":
            assert record.target.corrected_text == record.source_text
        else:
            assert record.target.corrected_text != record.source_text


def test_no_change_records_cover_protected_negative_families(
    dataset: FinetuningDataset,
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
    for split in (dataset.train, dataset.validation):
        covered = {
            tag
            for record in split
            if record.category == "no_change"
            for tag in record.tags
        }
        assert required <= covered


def test_train_and_validation_are_template_and_entity_disjoint(
    dataset: FinetuningDataset,
) -> None:
    train_templates = {record.template_id for record in dataset.train}
    validation_templates = {record.template_id for record in dataset.validation}
    assert train_templates.isdisjoint(validation_templates)
    train_entities = {
        span.identity for record in dataset.train for span in record.entity_spans
    }
    validation_entities = {
        span.identity for record in dataset.validation for span in record.entity_spans
    }
    assert train_entities.isdisjoint(validation_entities)


def test_manifest_matches_deterministic_statistics(dataset: FinetuningDataset) -> None:
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == dataset.manifest
    assert manifest["record_counts"] == {"train": 1_200, "validation": 240}
    assert manifest["category_counts"]["train"] == {
        category: 300 for category in DATASET_CATEGORIES
    }
    assert manifest["category_counts"]["validation"] == {
        category: 60 for category in DATASET_CATEGORIES
    }
    assert manifest["corpus_v3_isolation"] == "passed"
    assert manifest["license"] == "CC0-1.0"


def test_generator_reproduces_committed_bundle(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_finetuning_dataset.py"),
            "--output",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
    )
    for filename in ("train.jsonl", "validation.jsonl", "manifest.json"):
        assert (tmp_path / filename).read_bytes() == (BUNDLE / filename).read_bytes()


def test_validator_rejects_duplicate_malformed_and_unsupported_records(
    dataset: FinetuningDataset,
) -> None:
    raw = _raw(dataset.train[0])
    with pytest.raises(ValueError, match="duplicate record id|duplicate source"):
        validate_finetuning_records([raw, deepcopy(raw)], expected_split="train")

    malformed = deepcopy(raw)
    malformed["messages"] = malformed["messages"][:2]
    with pytest.raises(ValueError, match="messages"):
        validate_finetuning_records([malformed], expected_split="train")

    unsupported = deepcopy(raw)
    unsupported["category"] = "style"
    with pytest.raises(ValueError, match="category"):
        validate_finetuning_records([unsupported], expected_split="train")


def test_validator_rejects_noop_positive_unsafe_rewrite_and_split_leakage(
    dataset: FinetuningDataset,
) -> None:
    syntax = next(record for record in dataset.train if record.category == "syntax")
    no_op = _raw(syntax)
    no_op["target"]["corrected_text"] = no_op["source_text"]
    no_op["messages"][2]["content"] = json.dumps(
        no_op["target"], ensure_ascii=False, separators=(",", ":")
    )
    no_op["chatml"] = render_bielik_chatml(no_op["messages"])
    with pytest.raises(ValueError, match="positive record must change"):
        validate_finetuning_records([no_op], expected_split="train")

    punctuation = next(
        record for record in dataset.train if record.category == "punctuation"
    )
    unsafe = _raw(punctuation)
    unsafe["target"]["corrected_text"] = "Całkowicie inne zdanie."
    unsafe["messages"][2]["content"] = json.dumps(
        unsafe["target"], ensure_ascii=False, separators=(",", ":")
    )
    unsafe["chatml"] = render_bielik_chatml(unsafe["messages"])
    with pytest.raises(ValueError, match="unsafe rewrite"):
        validate_finetuning_records([unsafe], expected_split="train")

    leaked = _raw(dataset.train[0])
    leaked["split"] = "validation"
    with pytest.raises(ValueError, match="split"):
        validate_finetuning_records([leaked], expected_split="train")


def _raw(record: FinetuningRecord) -> dict[str, Any]:
    raw = cast(
        dict[str, Any], json.loads(json.dumps(asdict(record), ensure_ascii=False))
    )
    raw["target"] = {
        key: value for key, value in raw["target"].items() if value is not None
    }
    return raw
