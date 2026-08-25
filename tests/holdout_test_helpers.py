from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from polis.evaluation.holdout_admission import ExternalAdmission

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]

DATASET_SHA256 = "a1f9b87dbfc89dc9283f652b56058fee995dabbb71902d642fb8efd576ea7b32"
CONFIG_SHA256 = "a959638116058ab6646f929ce464d8bdc6ba3b36fb9a2b181411c0ec7b4cb6a2"
SOURCE_SHA256 = "8352a9d793fa047e0aa7e6a43be95ddda873cadeddedf1867cd762d317583063"
ARTIFACT_SHA256 = "d" * 64
VERIFICATION_PAYLOAD_SHA256 = "9" * 64
MERGE_COMMIT = "7" * 40
NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
MORPHOLOGY_SUFFIX = "+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-" + NOTICE_SHA256

SOURCE_IDENTITIES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "rule:agreement.copula",
        "agreement",
        "replace.copula_form",
        "agreement-copula/1.0",
        "1.2",
    ),
    (
        "rule:agreement.te_zdanie",
        "agreement",
        "replace.demonstrative_neuter_phrase",
        "agreement-te-zdanie/1.0",
        "1.2",
    ),
    (
        "rule:agreement.nominal_group_te_duze_okno",
        "agreement",
        "replace.demonstrative_neuter_form",
        "agreement-nominal-group-te-duze-okno/1.0" + MORPHOLOGY_SUFFIX,
        "1.2",
    ),
    (
        "rule:agreement.subject_verb_oni_czyta",
        "agreement",
        "replace.subject_verb_number",
        "agreement-subject-verb-oni-czyta/1.0" + MORPHOLOGY_SUFFIX,
        "1.2",
    ),
    (
        "rule:inflection.negated_widziec",
        "inflection",
        "replace.negated_government_form",
        "inflection-negated-widziec/1.0",
        "1.2",
    ),
    (
        "rule:inflection.negated_widziec_nominal_group",
        "inflection",
        "replace.negated_government_nominal_group",
        "inflection-negated-widziec-nominal-group/1.0" + MORPHOLOGY_SUFFIX,
        "1.2",
    ),
    (
        "rule:inflection.government_potrzebowac_pomoc",
        "inflection",
        "replace.governed_form",
        "inflection-government-potrzebowac-pomoc/1.0" + MORPHOLOGY_SUFFIX,
        "1.2",
    ),
    (
        "rule:spelling.jestes",
        "spelling",
        "replace.common_typo",
        "spelling-jestes/1.0",
        "1.2",
    ),
    (
        "rule:spelling.napewno",
        "spelling",
        "replace.common_typo",
        "spelling-napewno/1.0",
        "1.2",
    ),
    (
        "rule:spelling.wlasnie",
        "spelling",
        "replace.common_typo",
        "spelling-wlasnie/1.0",
        "1.2",
    ),
    (
        "rule:spelling.zeby",
        "spelling",
        "replace.common_typo",
        "spelling-zeby/1.0",
        "1.2",
    ),
    (
        "rule:syntax.comma_space",
        "punctuation",
        "normalize.comma_spacing",
        "syntax-comma-space/1.0",
        "1.2",
    ),
    (
        "rule:syntax.duplicate_comma",
        "punctuation",
        "remove.duplicate_comma",
        "syntax-duplicate-comma/1.0",
        "1.2",
    ),
    (
        "rule:syntax.initial_conditional_comma",
        "syntax",
        "insert.conditional_clause_comma",
        "syntax-initial-conditional-comma/1.0",
        "1.2",
    ),
    (
        "rule:syntax.list_space",
        "syntax",
        "normalize.list_marker_spacing",
        "syntax-list-space/1.0",
        "1.2",
    ),
    (
        "rule:syntax.missing_correlative",
        "syntax",
        "insert.correlative",
        "syntax-missing-correlative/1.0",
        "1.2",
    ),
    (
        "rule:syntax.missing_destination_preposition",
        "syntax",
        "insert.destination_preposition",
        "syntax-missing-destination-preposition/1.0",
        "1.2",
    ),
    (
        "rule:syntax.missing_reflexive",
        "syntax",
        "insert.reflexive_pronoun",
        "syntax-missing-reflexive/1.0",
        "1.2",
    ),
    (
        "rule:syntax.quote_space",
        "punctuation",
        "normalize.quote_spacing",
        "syntax-quote-space/1.0",
        "1.2",
    ),
    (
        "rule:syntax.sentence_space",
        "punctuation",
        "normalize.sentence_spacing",
        "syntax-sentence-space/1.0",
        "1.2",
    ),
)


@dataclass(frozen=True, slots=True)
class AdmissionEvidence:
    config_sha256: str
    source_sha256: str
    dataset_sha256: str
    merge_commit: str | None
    verification_verified: bool | None
    verification_reason: str | None
    verification_payload_sha256: str | None


def approved_admission() -> AdmissionEvidence:
    return AdmissionEvidence(
        config_sha256=CONFIG_SHA256,
        source_sha256=SOURCE_SHA256,
        dataset_sha256=DATASET_SHA256,
        merge_commit=MERGE_COMMIT,
        verification_verified=True,
        verification_reason="valid",
        verification_payload_sha256=VERIFICATION_PAYLOAD_SHA256,
    )


def load_synthetic_external_admission(
    root: Path,
    *,
    dataset_sha256: str,
    merge_commit: str,
    source_tree_sha256: str,
) -> ExternalAdmission:
    from polis.evaluation.holdout_admission import load_external_admission
    from polis.evaluation.holdout_contract import canonical_sha256, parse_holdout_config

    config_path = root / "experiments/a-b-one-shot/config.json"
    config_document = json.loads(config_path.read_bytes())
    assert isinstance(config_document, dict)
    dataset = config_document["dataset"]
    assert isinstance(dataset, dict)
    dataset["sha256"] = dataset_sha256
    dataset["size_bytes"] = 17370
    config = parse_holdout_config(config_document)
    merge_path = root / ".omo/sealed/a-b-one-shot-v1/merge-verification.json"
    merge = json.loads(merge_path.read_bytes())
    assert isinstance(merge, dict)
    merge["evaluated_source_sha"] = merge_commit
    merge["evaluated_source_tree_sha256"] = source_tree_sha256
    merge_path.write_text(json.dumps(merge), encoding="utf-8")

    authorization = {
        "schema_id": "polis.a-b-one-shot.run-authorization",
        "schema_version": 1,
        "run_authorization": "approved",
        "repository": "PSyron/polis",
        "issue_number": 243,
        "comment_id": 5228447542,
        "comment_url": "https://github.com/PSyron/polis/issues/243#issuecomment-5228447542",
        "author": "PSyron",
        "created_at": "2026-08-08T20:20:00Z",
        "body": "",
        "evaluated_source_sha": merge_commit,
        "config_sha256": canonical_sha256(config_document),
        "dataset_sha256": dataset_sha256,
        "preflight_completed_at": "2026-08-08T20:10:00Z",
        "wheel_sha256": "c" * 64,
        "sdist_sha256": "d" * 64,
        "lock_sha256": "e" * 64,
        "ssh_keygen_path": "/usr/bin/ssh-keygen",
        "ssh_keygen_sha256": "f" * 64,
    }
    authorization["body"] = "\n".join(
        (
            "run_authorization=approved",
            f"evaluated_source_sha={merge_commit}",
            f"config_sha256={authorization['config_sha256']}",
            f"dataset_sha256={dataset_sha256}",
            "ssh_keygen_path=/usr/bin/ssh-keygen",
            f"ssh_keygen_sha256={authorization['ssh_keygen_sha256']}",
        )
    )
    authorization["operator_attestation_sha256"] = canonical_sha256(authorization)
    authorization_path = root / ".omo/sealed/a-b-one-shot-v1/run-authorization.json"
    authorization_path.write_bytes(
        (
            json.dumps(authorization, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    )
    (authorization_path.with_suffix(".sig")).write_bytes(
        b"-----BEGIN SSH SIGNATURE-----\nc3ludGhldGlj\n-----END SSH SIGNATURE-----\n"
    )

    def load_metadata(path: Path) -> JsonObject:
        value = json.loads((root / path).read_bytes())
        assert isinstance(value, dict)
        return value

    return load_external_admission(
        config_document,
        config,
        checkout_identity=lambda kind: (
            merge_commit if kind == "commit" else source_tree_sha256
        ),
        verify_commit=lambda _source_sha: True,
        load_metadata=load_metadata,
        load_evidence=lambda path: (root / path).read_bytes(),
    )
