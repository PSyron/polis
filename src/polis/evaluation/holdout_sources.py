from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from polis.analyzer import Analyzer, AnalyzerConfig
from polis.correction.policy import SOURCE_POLICY_VERSION
from polis.evaluation.calibration_source_rows import SOURCE_ROWS
from polis.evaluation.holdout_models import (
    HoldoutConfig,
    HoldoutContractError,
    JsonValue,
    SourceIdentity,
)

_CATEGORY_BY_SOURCE = {
    "rule:agreement.copula": "agreement",
    "rule:agreement.te_zdanie": "agreement",
    "rule:agreement.nominal_group_te_duze_okno": "agreement",
    "rule:agreement.nominal_group_ta_nowy_ksiazka": "agreement",
    "rule:agreement.subject_verb_oni_czyta": "agreement",
    "rule:agreement.subject_verb_my_czyta": "agreement",
    "rule:inflection.negated_widziec": "inflection",
    "rule:inflection.negated_widziec_nominal_group": "inflection",
    "rule:inflection.przygladac_sie_nowy_budynek": "inflection",
    "rule:inflection.government_potrzebowac_pomoc": "inflection",
    "rule:spelling.jestes": "spelling",
    "rule:spelling.napewno": "spelling",
    "rule:spelling.wlasnie": "spelling",
    "rule:spelling.zeby": "spelling",
    "rule:spelling.wogole": "spelling",
    "rule:spelling.narazie": "spelling",
    "rule:spelling.wziasc": "spelling",
    "rule:syntax.comma_space": "punctuation",
    "rule:syntax.duplicate_comma": "punctuation",
    "rule:syntax.initial_conditional_comma": "syntax",
    "rule:syntax.list_space": "syntax",
    "rule:syntax.missing_correlative": "syntax",
    "rule:syntax.missing_destination_preposition": "syntax",
    "rule:syntax.missing_reflexive": "syntax",
    "rule:syntax.quote_space": "punctuation",
    "rule:syntax.sentence_space": "punctuation",
}


def current_sources() -> tuple[SourceIdentity, ...]:
    """Return the expanding runtime composition-root snapshot."""

    try:
        registrations = Analyzer(AnalyzerConfig()).source_identity_snapshot
        return tuple(
            SourceIdentity(
                source=str(entry.source),
                category=_CATEGORY_BY_SOURCE[str(entry.source)],
                operation=entry.operation,
                behavior_version=entry.behavior_version,
                source_policy_version=SOURCE_POLICY_VERSION,
            )
            for entry in registrations
        )
    except (
        AttributeError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        raise HoldoutContractError(
            "current source identity snapshot is unavailable"
        ) from error


def qualification_sources() -> tuple[SourceIdentity, ...]:
    """Return the immutable 20-source qualification cohort (ADR-0025)."""

    return tuple(
        SourceIdentity(
            source=row.source,
            category=row.category,
            operation=row.operation,
            behavior_version=row.behavior_version,
            source_policy_version=row.source_policy_version,
        )
        for row in SOURCE_ROWS
    )


def parse_sources(
    value: JsonValue,
    source_snapshot: Callable[[], tuple[SourceIdentity, ...]],
) -> tuple[SourceIdentity, ...]:
    if not isinstance(value, list):
        raise HoldoutContractError("source identities must be a list")
    parsed: list[SourceIdentity] = []
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 5
            or any(not isinstance(part, str) for part in item)
        ):
            raise HoldoutContractError(
                "source identities must contain five-string tuples"
            )
        parsed.append(SourceIdentity(*item))
    identities = tuple(parsed)
    if len(set(identities)) != len(identities):
        raise HoldoutContractError("source identities must be unique")
    try:
        current = source_snapshot()
    except (
        AttributeError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        raise HoldoutContractError(
            "current source identity snapshot is unavailable"
        ) from error
    current_set = set(current)
    identities_set = set(identities)
    if len(current_set) != len(current) or len(identities_set) != len(identities):
        raise HoldoutContractError("source identities must be unique")

    missing = sorted(
        (item for item in identities if item not in current_set),
        key=lambda item: item.source,
    )
    extra = sorted(
        (item for item in current if item not in identities_set),
        key=lambda item: item.source,
    )
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(item.source for item in missing))
        if extra:
            details.append("extra: " + ", ".join(item.source for item in extra))
        raise HoldoutContractError(
            "source identities differ from the runtime composition root: "
            + "; ".join(details)
        )
    return identities


def source_sha256(config: HoldoutConfig) -> str:
    identities = [
        [
            item.source,
            item.category,
            item.operation,
            item.behavior_version,
            item.source_policy_version,
        ]
        for item in config.source_identities
    ]
    payload = json.dumps(
        identities,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
