from __future__ import annotations

import json
from pathlib import Path

from polis.evaluation.quality_report import load_quality_report

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "docs/quality-baseline-v3-default.json"
MORPHOLOGY = ROOT / "docs/quality-baseline-v3-morphology.json"
V3_DATASET_SHA = "8f6dec8379af6330f2fb8330421f6a6581f6c9e39ad98fe304322b4a9abb6276"


def test_v3_baselines_exist_for_both_profiles_with_shared_provenance() -> None:
    default = json.loads(DEFAULT.read_text(encoding="utf-8"))
    morph = json.loads(MORPHOLOGY.read_text(encoding="utf-8"))

    assert default["schema_version"] == 3
    assert morph["schema_version"] == 3
    assert default["dataset"]["schema_version"] == 3
    assert morph["dataset"]["schema_version"] == 3
    assert default["dataset"]["id"] == "polis_v3_quality_development"
    assert morph["dataset"]["id"] == "polis_v3_quality_development"
    assert default["dataset"]["cases"] == 340
    assert morph["dataset"]["cases"] == 340
    assert default["dataset"]["sha256"] == V3_DATASET_SHA
    assert morph["dataset"]["sha256"] == V3_DATASET_SHA
    assert default["source"]["git_sha"] == morph["source"]["git_sha"]
    assert default["artifact"]["sha256"] == morph["artifact"]["sha256"]
    assert default["profile"]["id"] == "default"
    assert morph["profile"]["id"] == "morphology"
    assert default["profile"]["morphology_provider"] is None
    assert morph["profile"]["morphology_provider"]["provider"] == "morfeusz2"
    assert default["quality"]["false_alarm_rate"] == 0.0
    assert morph["quality"]["false_alarm_rate"] == 0.0
    assert default["quality"]["precision"] == 1.0
    assert morph["quality"]["precision"] == 1.0


def test_v3_baselines_parse_as_quality_reports() -> None:
    default = load_quality_report(DEFAULT)
    morph = load_quality_report(MORPHOLOGY)
    assert default.run_identity.dataset_schema_version == 3
    assert morph.run_identity.dataset_schema_version == 3
    assert default.run_identity.source_sha == morph.run_identity.source_sha
    assert default.run_identity.artifact_sha256 == morph.run_identity.artifact_sha256
