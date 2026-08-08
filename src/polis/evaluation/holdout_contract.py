from __future__ import annotations

from collections.abc import Callable

from polis.evaluation.holdout_config_authorization import parse_authorization_signature
from polis.evaluation.holdout_config_dataset import parse_dataset_identity
from polis.evaluation.holdout_json import (
    canonical_sha256 as _canonical_sha256,
)
from polis.evaluation.holdout_json import (
    fail as _fail,
)
from polis.evaluation.holdout_json import (
    integer_value as _integer,
)
from polis.evaluation.holdout_json import (
    number_value as _number,
)
from polis.evaluation.holdout_json import (
    object_value as _object,
)
from polis.evaluation.holdout_json import (
    string_value as _string,
)
from polis.evaluation.holdout_json import (
    strings_value as _strings,
)
from polis.evaluation.holdout_models import (
    FailurePolicy,
    HoldoutConfig,
    HoldoutSchemas,
    JsonObject,
    SignatureRequirements,
    SourceIdentity,
    Taxonomy,
    Thresholds,
)
from polis.evaluation.holdout_models import (
    HoldoutContractError as _HoldoutContractError,
)
from polis.evaluation.holdout_paths import parse_holdout_paths
from polis.evaluation.holdout_preregistration import (
    EXACT_COMMAND,
    METRICS,
    TAXONOMY,
    THRESHOLDS,
)
from polis.evaluation.holdout_sources import current_sources, parse_sources

canonical_sha256 = _canonical_sha256
HoldoutContractError = _HoldoutContractError

_TOP_FIELDS = {
    "schema_id",
    "schema_version",
    "experiment_id",
    "exact_command",
    "warmup_repetitions",
    "measured_repetitions",
    "dataset",
    "taxonomy",
    "metrics",
    "thresholds",
    "source_identities",
    "exclusions",
    "failure_policy",
    "signature",
    "authorization_signature",
    "external_schemas",
    "paths",
}


def parse_holdout_config(
    raw: JsonObject,
    *,
    source_snapshot: Callable[[], tuple[SourceIdentity, ...]] | None = None,
) -> HoldoutConfig:
    if set(raw) != _TOP_FIELDS:
        _fail("config must contain exactly the required fields")
    if raw["schema_id"] != "polis.a-b-one-shot.config" or raw["schema_version"] != 1:
        _fail("unsupported holdout config schema")
    dataset = parse_dataset_identity(raw["dataset"])
    taxonomy_raw = _object(
        raw["taxonomy"], {"categories", "roles", "features"}, "taxonomy"
    )
    taxonomy = Taxonomy(
        _strings(taxonomy_raw["categories"], "taxonomy categories"),
        _strings(taxonomy_raw["roles"], "taxonomy roles"),
        _strings(taxonomy_raw["features"], "taxonomy features"),
    )
    if taxonomy != TAXONOMY:
        _fail("taxonomy must match the preregistration")
    metrics = _strings(raw["metrics"], "metrics")
    if metrics != METRICS:
        _fail("metrics must match the preregistered set")
    thresholds_raw = _object(raw["thresholds"], set(METRICS[:6]), "thresholds")
    thresholds = Thresholds(
        *(_number(thresholds_raw[name], name) for name in METRICS[:6])
    )
    if (
        thresholds.precision,
        thresholds.recall,
        thresholds.f1,
        thresholds.exact_span_accuracy,
        thresholds.exact_correction_accuracy,
        thresholds.correct_sentence_false_alarm_rate,
    ) != THRESHOLDS:
        _fail("thresholds must match the approved thresholds")
    sources = parse_sources(
        raw["source_identities"], source_snapshot or current_sources
    )
    exclusions = _strings(raw["exclusions"], "exclusions")
    if exclusions != ("style", "tone", "meaning", "model", "network"):
        _fail("exclusions must match the preregistration")
    failure_raw = _object(
        raw["failure_policy"], {"retry", "tuning", "non_pass_source"}, "failure policy"
    )
    failure = FailurePolicy(
        *(
            _string(failure_raw[name], name)
            for name in ("retry", "tuning", "non_pass_source")
        )
    )
    if failure != FailurePolicy(
        "never", "new-development-dataset-and-experiment-only", "review-only"
    ):
        _fail("failure policy must prohibit retries and holdout tuning")
    signature_raw = _object(
        raw["signature"],
        {
            "method",
            "status",
            "required_verified",
            "required_reason",
            "required_bindings",
        },
        "signature",
    )
    required_verified = signature_raw["required_verified"]
    if type(required_verified) is not bool:
        _fail("signature required_verified must be boolean")
    signature = SignatureRequirements(
        _string(signature_raw["method"], "signature method"),
        _string(signature_raw["status"], "signature status"),
        required_verified,
        _string(signature_raw["required_reason"], "signature reason"),
        _strings(signature_raw["required_bindings"], "signature bindings"),
    )
    expected_signature = SignatureRequirements(
        "github-verified-merge-commit",
        "required-before-run",
        True,
        "valid",
        (
            "evaluated_merge_commit",
            "evaluated_source_tree_sha256",
            "verification_payload_sha256",
        ),
    )
    if signature.method != expected_signature.method:
        _fail("signature method does not match the approved signature contract")
    if signature != expected_signature:
        _fail("signature requirements do not match the approved signature contract")
    authorization_signature = parse_authorization_signature(
        raw["authorization_signature"]
    )
    schemas_raw = _object(
        raw["external_schemas"],
        {"dataset", "merge_verification", "run_authorization"},
        "external schemas",
    )
    schemas = HoldoutSchemas(
        _string(schemas_raw["dataset"], "dataset schema"),
        _string(schemas_raw["merge_verification"], "merge verification schema"),
        _string(schemas_raw["run_authorization"], "run authorization schema"),
    )
    if schemas != HoldoutSchemas(
        "polis.a-b-one-shot.dataset/1",
        "polis.a-b-one-shot.merge-verification/1",
        "polis.a-b-one-shot.run-authorization/1",
    ):
        _fail("external schemas must match the preregistration")
    paths = parse_holdout_paths(raw["paths"])
    if (
        _integer(raw["warmup_repetitions"], "warmup repetitions") != 1
        or _integer(raw["measured_repetitions"], "measured repetitions") != 5
    ):
        _fail("repetition counts must match the preregistration")
    experiment_id = _string(raw["experiment_id"], "experiment id")
    exact_command = _string(raw["exact_command"], "exact command")
    if experiment_id != "polis-a-b-one-shot-v1":
        _fail("experiment identity must match the preregistration")
    if exact_command != EXACT_COMMAND:
        _fail("exact command must match the preregistration")
    return HoldoutConfig(
        experiment_id,
        exact_command,
        1,
        5,
        dataset,
        taxonomy,
        metrics,
        thresholds,
        sources,
        exclusions,
        failure,
        signature,
        authorization_signature,
        schemas,
        paths,
    )
