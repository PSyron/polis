from __future__ import annotations

from polis.evaluation.holdout_models import Taxonomy

DATASET_SHA256 = "a1f9b87dbfc89dc9283f652b56058fee995dabbb71902d642fb8efd576ea7b32"
AUTHORIZATION_COMMENT_ID_WATERMARK = 5228447541
AUTHORIZATION_METHOD = "ssh-ed25519-detached"
AUTHORIZATION_IDENTITY = "PSyron"
AUTHORIZATION_NAMESPACE = "polis-holdout-authorization-v1"
AUTHORIZATION_PUBLIC_KEY = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIPSl0nj4FZIeprDr+GYHNCVbMJfIy5nmpyBvHi2u31Ey "
    "pawel.cyron@tv2.no"
)
AUTHORIZATION_FINGERPRINT = "SHA256:JvdjEgHYEQPsrsthSO5GnrM7saNvsanY5uJl89B0lQk"
AUTHORIZATION_SIGNED_PAYLOAD = "canonical-json-sort-keys-compact-utf8-final-lf"
AUTHORIZATION_HOST_SYSTEM = "Darwin"
AUTHORIZATION_HOST_MACHINE = "arm64"
SSH_KEYGEN_PATH = "/usr/bin/ssh-keygen"
EXACT_COMMAND = (
    "uv run --locked --extra dev python -m polis.evaluation run-holdout "
    "--config experiments/a-b-one-shot/config.json"
)
METRICS = (
    "precision",
    "recall",
    "f1",
    "exact_span_accuracy",
    "exact_correction_accuracy",
    "correct_sentence_false_alarm_rate",
    "latency",
    "throughput",
    "peak_rss",
)
THRESHOLDS = (
    1.0,
    0.7142857142857143,
    0.8333333333333334,
    0.7142857142857143,
    1.0,
    0.0,
)
TAXONOMY = Taxonomy(
    ("inflection/rection", "agreement", "spelling", "syntax", "punctuation"),
    ("error", "correct", "abstain", "conflict"),
    (
        "paired_close_negative",
        "unicode",
        "multi_sentence",
        "morphology_unknown",
        "morphology_ambiguous",
        "overlap_conflict",
    ),
)
