from __future__ import annotations

from dataclasses import dataclass

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
