from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Protocol, runtime_checkable

import pytest
from tests.holdout_config_fixture import changed_config, synthetic_config
from tests.holdout_test_helpers import (
    SOURCE_IDENTITIES,
    JsonObject,
    JsonValue,
)

from polis import Analyzer, AnalyzerConfig
from polis.evaluation.holdout_models import SourceIdentity


class _DatasetView(Protocol):
    case_count: int
    reviewed_case_count: int


def test_analyzer_exposes_immutable_public_source_identity_snapshot() -> None:
    snapshot = Analyzer(AnalyzerConfig()).source_identity_snapshot

    assert isinstance(snapshot, tuple)
    assert len(snapshot) == 27
    assert snapshot[0].source == "rule:agreement.copula"
    assert snapshot[0].operation == "replace.copula_form"
    assert snapshot[0].behavior_version == "agreement-copula/1.0"
    assert any(
        item.source == "rule:agreement.nominal_group_ta_nowy_ksiazka"
        for item in snapshot
    )
    assert any(
        item.source == "rule:agreement.subject_verb_my_czyta" for item in snapshot
    )
    assert any(
        item.source == "rule:inflection.przygladac_sie_nowy_budynek"
        for item in snapshot
    )
    assert any(
        item.source == "rule:inflection.government_szukac_klucz" for item in snapshot
    )
    assert any(item.source == "rule:spelling.wogole" for item in snapshot)
    assert any(item.source == "rule:spelling.narazie" for item in snapshot)
    assert any(item.source == "rule:spelling.wziasc" for item in snapshot)


class _SourceIdentityView(Protocol):
    source: str
    category: str
    operation: str
    behavior_version: str
    source_policy_version: str


class _ParsedConfigView(Protocol):
    experiment_id: str
    dataset: _DatasetView
    warmup_repetitions: int
    measured_repetitions: int
    source_identities: tuple[_SourceIdentityView, ...]


@runtime_checkable
class _ContractApi(Protocol):
    HoldoutContractError: type[Exception]

    def parse_holdout_config(
        self,
        raw: JsonObject,
        *,
        source_snapshot: Callable[[], tuple[SourceIdentity, ...]] | None = None,
    ) -> _ParsedConfigView: ...

    def canonical_sha256(self, raw: JsonObject) -> str: ...


def _contract() -> _ContractApi:
    try:
        module = importlib.import_module("polis.evaluation.holdout_contract")
    except ModuleNotFoundError as error:
        raise AssertionError(
            "planned holdout contract implementation is absent"
        ) from error
    if not isinstance(module, _ContractApi):
        raise AssertionError("planned holdout contract API is incomplete")
    return module


def test_strict_contract_accepts_complete_synthetic_preregistration() -> None:
    parsed = _contract().parse_holdout_config(
        synthetic_config(), source_snapshot=_source_snapshot
    )

    assert parsed.experiment_id == "polis-a-b-one-shot-v1"
    assert parsed.dataset.case_count == 52
    assert parsed.dataset.reviewed_case_count == 52
    assert parsed.warmup_repetitions == 1
    assert parsed.measured_repetitions == 5


@pytest.mark.parametrize("field", ["schema_id", "taxonomy", "thresholds", "signature"])
def test_strict_contract_rejects_missing_required_field(field: str) -> None:
    raw = changed_config()
    del raw[field]

    with pytest.raises(
        _contract().HoldoutContractError, match="exactly the required fields"
    ):
        _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)


def test_strict_contract_rejects_unknown_field() -> None:
    raw = changed_config()
    raw["override"] = "forbidden"

    with pytest.raises(
        _contract().HoldoutContractError, match="exactly the required fields"
    ):
        _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate", "source identities must be unique"),
        ("missing", "source identities differ from the runtime composition root"),
    ],
)
def test_exact_twenty_source_tuple_binding_rejects_drift(
    mutation: str, message: str
) -> None:
    raw = changed_config()
    identities = raw["source_identities"]
    assert isinstance(identities, list)
    if mutation == "duplicate":
        identities[1] = identities[0]
    else:
        identities.pop()

    with pytest.raises(_contract().HoldoutContractError, match=message):
        _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)


def test_source_identity_reordering_is_allowed() -> None:
    raw = changed_config()
    identities = raw["source_identities"]
    assert isinstance(identities, list)

    identities.reverse()

    _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)


def test_source_snapshot_missing_identity_is_reported() -> None:
    source_snapshot = _source_snapshot()
    missing_source = source_snapshot[-1].source

    with pytest.raises(
        _contract().HoldoutContractError,
        match=f"missing: {missing_source}",
    ):
        _contract().parse_holdout_config(
            synthetic_config(), source_snapshot=lambda: source_snapshot[:-1]
        )


def _source_snapshot() -> tuple[SourceIdentity, ...]:
    return tuple(SourceIdentity(*identity) for identity in SOURCE_IDENTITIES)


def test_source_snapshot_drift_is_a_typed_contract_error() -> None:
    with pytest.raises(
        _contract().HoldoutContractError,
        match="source identities differ from the runtime composition root.*missing",
    ):
        _contract().parse_holdout_config(
            synthetic_config(), source_snapshot=lambda: _source_snapshot()[:-1]
        )


def test_source_snapshot_drift_reports_extra_identity() -> None:
    with pytest.raises(
        _contract().HoldoutContractError,
        match="extra: rule:synthetic.extra_rule_identity",
    ):
        _contract().parse_holdout_config(
            synthetic_config(),
            source_snapshot=lambda: (
                *_source_snapshot(),
                SourceIdentity(
                    "rule:synthetic.extra_rule_identity",
                    "syntax",
                    "noop",
                    "synthetic/1.0",
                    "1.2",
                ),
            ),
        )


def test_source_snapshot_provider_failure_is_a_typed_contract_error() -> None:
    def broken_snapshot() -> tuple[SourceIdentity, ...]:
        raise KeyError

    with pytest.raises(
        _contract().HoldoutContractError,
        match="current source identity snapshot is unavailable",
    ):
        _contract().parse_holdout_config(
            synthetic_config(), source_snapshot=broken_snapshot
        )


@pytest.mark.parametrize(
    ("container", "field", "value", "message"),
    [
        ("dataset", "license", "proprietary", "dataset license"),
        ("dataset", "review_status", "PENDING", "independent review"),
        ("dataset", "reviewed_case_count", 51, "review coverage"),
        ("signature", "method", "unsigned", "signature method"),
        ("thresholds", "precision", 0.99, "approved thresholds"),
    ],
)
def test_strict_contract_rejects_unapproved_identity_or_threshold(
    container: str, field: str, value: JsonValue, message: str
) -> None:
    raw = changed_config()
    nested = raw[container]
    assert isinstance(nested, dict)
    nested[field] = value

    with pytest.raises(_contract().HoldoutContractError, match=message):
        _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)


def test_canonical_config_digest_changes_for_one_byte_of_metadata() -> None:
    original = synthetic_config()
    changed = changed_config()
    changed["experiment_id"] = "polis-a-b-one-shot-v2"

    assert _contract().canonical_sha256(original) != _contract().canonical_sha256(
        changed
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "optional"),
        ("required_verified", False),
        ("required_reason", "unknown"),
        ("required_bindings", ["evaluated_merge_commit"]),
    ],
)
def test_signature_requirements_are_fail_closed(field: str, value: JsonValue) -> None:
    raw = changed_config()
    signature = raw["signature"]
    assert isinstance(signature, dict)
    signature[field] = value

    with pytest.raises(_contract().HoldoutContractError, match="signature"):
        _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("method", "self-hash"),
        ("signer_identity", "attacker"),
        ("namespace", "other-project"),
        ("trusted_public_key", "ssh-ed25519 attacker"),
        ("trusted_key_fingerprint", "SHA256:" + "A" * 43),
        ("signed_payload", "noncanonical-json"),
        ("host_system", "Linux"),
        ("host_machine", "x86_64"),
        ("ssh_keygen_path", "/tmp/ssh-keygen"),
    ],
)
def test_authorization_signature_requirements_are_exact(
    field: str, value: JsonValue
) -> None:
    raw = changed_config()
    signature = raw["authorization_signature"]
    assert isinstance(signature, dict)
    signature[field] = value

    with pytest.raises(_contract().HoldoutContractError, match="authorization"):
        _contract().parse_holdout_config(raw, source_snapshot=_source_snapshot)
