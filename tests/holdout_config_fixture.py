from __future__ import annotations

from copy import deepcopy

from tests.holdout_test_helpers import DATASET_SHA256, SOURCE_IDENTITIES

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


def synthetic_config() -> JsonObject:
    return {
        "schema_id": "polis.a-b-one-shot.config",
        "schema_version": 1,
        "experiment_id": "polis-a-b-one-shot-v1",
        "exact_command": (
            "uv run --locked --extra dev python -m polis.evaluation run-holdout "
            "--config experiments/a-b-one-shot/config.json"
        ),
        "warmup_repetitions": 1,
        "measured_repetitions": 5,
        "dataset": {
            "sha256": DATASET_SHA256,
            "size_bytes": 17370,
            "case_count": 52,
            "source_count": 20,
            "license": "CC0-1.0",
            "provenance": "project-authored-independent-review",
            "review_status": "APPROVE",
            "reviewed_case_count": 52,
            "mode": "0600",
        },
        "taxonomy": {
            "categories": [
                "inflection/rection",
                "agreement",
                "spelling",
                "syntax",
                "punctuation",
            ],
            "roles": ["error", "correct", "abstain", "conflict"],
            "features": [
                "paired_close_negative",
                "unicode",
                "multi_sentence",
                "morphology_unknown",
                "morphology_ambiguous",
                "overlap_conflict",
            ],
        },
        "metrics": [
            "precision",
            "recall",
            "f1",
            "exact_span_accuracy",
            "exact_correction_accuracy",
            "correct_sentence_false_alarm_rate",
            "latency",
            "throughput",
            "peak_rss",
        ],
        "thresholds": {
            "precision": 1.0,
            "recall": 0.7142857142857143,
            "f1": 0.8333333333333334,
            "exact_span_accuracy": 0.7142857142857143,
            "exact_correction_accuracy": 1.0,
            "correct_sentence_false_alarm_rate": 0.0,
        },
        "source_identities": [list(identity) for identity in SOURCE_IDENTITIES],
        "exclusions": ["style", "tone", "meaning", "model", "network"],
        "failure_policy": {
            "retry": "never",
            "tuning": "new-development-dataset-and-experiment-only",
            "non_pass_source": "review-only",
        },
        "signature": {
            "method": "github-verified-merge-commit",
            "status": "required-before-run",
            "required_verified": True,
            "required_reason": "valid",
            "required_bindings": [
                "evaluated_merge_commit",
                "evaluated_source_tree_sha256",
                "verification_payload_sha256",
            ],
        },
        "authorization_signature": {
            "method": "ssh-ed25519-detached",
            "signer_identity": "PSyron",
            "namespace": "polis-holdout-authorization-v1",
            "trusted_public_key": (
                "ssh-ed25519 "
                "AAAAC3NzaC1lZDI1NTE5AAAAIPSl0nj4FZIeprDr+GYHNCVbMJfIy5nmpyBvHi2u31Ey "
                "pawel.cyron@tv2.no"
            ),
            "trusted_key_fingerprint": (
                "SHA256:JvdjEgHYEQPsrsthSO5GnrM7saNvsanY5uJl89B0lQk"
            ),
            "signed_payload": "canonical-json-sort-keys-compact-utf8-final-lf",
            "host_system": "Darwin",
            "host_machine": "arm64",
            "ssh_keygen_path": "/usr/bin/ssh-keygen",
        },
        "external_schemas": {
            "dataset": "polis.a-b-one-shot.dataset/1",
            "merge_verification": "polis.a-b-one-shot.merge-verification/1",
            "run_authorization": "polis.a-b-one-shot.run-authorization/1",
        },
        "paths": {
            "dataset": ".omo/sealed/a-b-one-shot-v1/cases.json",
            "merge_verification": ".omo/sealed/a-b-one-shot-v1/merge-verification.json",
            "run_authorization": ".omo/sealed/a-b-one-shot-v1/run-authorization.json",
            "run_authorization_signature": (
                ".omo/sealed/a-b-one-shot-v1/run-authorization.sig"
            ),
            "marker": "holdout.started",
            "raw_report": "report.json",
            "normalized_report": "normalized-report.json",
            "result_manifest": "result.manifest.json",
        },
    }


def changed_config() -> JsonObject:
    return deepcopy(synthetic_config())
