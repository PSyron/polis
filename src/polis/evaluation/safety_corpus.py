"""Validate the independent sentence safety qualification corpus.

The safety corpus re-qualifies the installed-package sentence safety claim
after the corpus-v3 frozen holdout was consumed by a failed one-shot gate.
It reuses the schema-v3 invariants from
:mod:`polis.evaluation.correction_corpus` without changing that module, and
adds a dedicated controlled entity-surface catalog that shares no canonical
entity identifier with the corpus-v3 catalog.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
from typing import Literal, cast

from polis.evaluation.correction_corpus import (
    _CASE_ID,
    _ENTITY_SPAN_FIELDS,
    _REVIEW_POLICY_FIELDS,
    _SPLITS,
    _STRATA,
    _TOP_LEVEL_FIELDS,
    CorpusUsageError,
    CorrectionCorpus,
    CorrectionCorpusCase,
    EntitySpan,
    IsolationRecord,
    _apply_edits,
    _corpus_entity_alias_evidence,
    _detect_training_entity_spans,
    _normalized_text,
    _require_exact_fields,
    _require_id,
    _require_member,
    _require_object,
    _require_offset,
    _require_string_tuple,
    _require_text,
    _templates_are_near,
    _training_entity_signature,
    _valid_training_spans,
    _validate_balance,
    _validate_edit,
    _validate_non_overlapping,
    _validate_provenance,
    _validate_review,
    _xml_as_raw,
    derive_normalized_template,
    select_cases_for_purpose,
)

CORPUS_ID = "polis_polish_correction_safety_corpus_v1"
REVIEW_CHECKLIST_VERSION = "safety-corpus-review-v1"

_CASE_FIELDS = frozenset(
    {
        "id",
        "stratum",
        "split",
        "unit",
        "input",
        "expected_output",
        "description",
        "tags",
        "normalized_template",
        "entity_ids",
        "entity_spans",
        "protected_phenomenon",
        "provenance",
        "review",
        "edits",
    }
)
_UNITS = frozenset({"sentence"})

SAFETY_CONTROLLED_ENTITY_SURFACES = frozenset(
    {
        "Artur Pietrzak",
        "Arturem Pietrzakiem",
        "Bydgoszcz",
        "Bydgoszczy",
        "Emil Wasilewski",
        "Emila Wasilewskiego",
        "Emilu",
        "Emmę Brown",
        "Hubert Malinowski",
        "Huberta Malinowskiego",
        "Katarzyna Malicka",
        "Katarzynie Malicka",
        "Katarzynę Malicką",
        "Katowice",
        "Katowicach",
        "Kielc",
        "Kielcach",
        "Kielce",
        "Kindze Wrońskiej",
        "Kinga Wrońska",
        "Krystian Sobieraj",
        "Krystianowi Sobierajowi",
        "Lublin",
        "Lublina",
        "Lublinie",
        "Lucas Meyer",
        "Magdalena Cieślak",
        "Magdaleny Cieślak",
        "Mikołajem Brzezicki",
        "Mikołajem Brzezickim",
        "Mikołaju",
        "Natalia Głowacka",
        "Natalię Głowacką",
        "Oliwia Stępień",
        "Oliwii Stępień",
        "Olsztyn",
        "Olsztynem",
        "Olsztyna",
        "Olsztynie",
        "Opole",
        "Opolu",
        "Patrycja Żuk",
        "Patrycją Żuk",
        "Patrycjo",
        "Sebastian Chmura",
        "Sebastianowi Chmurze",
        "Stanisław Gajda",
        "Stanisławem Gajda",
        "Stanisławowi Gajdzie",
        "Szczecin",
        "Szczecina",
        "Szczecinie",
        "Tymon Bednarek",
        "Tymona Bednarka",
        "Weronika Stachura",
        "Weroniką Stachura",
        "Weroniką Stachurą",
        "Weroniko",
        "Wiktoria Sowa",
        "Wiktorią Sową",
        "Wiktorię Sowę",
        "Zakopane",
        "Zakopanego",
        "Łódź",
        "Łodzi",
    }
)

SAFETY_ENTITY_ID_OVERRIDES = {
    "arturem pietrzakiem": "artur_pietrzak",
    "bydgoszczy": "bydgoszcz",
    "emila wasilewskiego": "emil_wasilewski",
    "emilu": "emil",
    "emmę brown": "emma_brown",
    "huberta malinowskiego": "hubert_malinowski",
    "katarzynie malicka": "katarzyna_malicka",
    "katarzynę malicką": "katarzyna_malicka",
    "katowicach": "katowice",
    "kielc": "kielce",
    "kielcach": "kielce",
    "kindze wrońskiej": "kinga_wronska",
    "krystianowi sobierajowi": "krystian_sobieraj",
    "lublina": "lublin",
    "lublinie": "lublin",
    "magdaleny cieślak": "magdalena_cieslak",
    "mikołajem brzezicki": "mikolaj_brzezicki",
    "mikołajem brzezickim": "mikolaj_brzezicki",
    "mikołaju": "mikolaj",
    "natalię głowacką": "natalia_glowacka",
    "oliwii stępień": "oliwia_stepien",
    "olsztyna": "olsztyn",
    "olsztynie": "olsztyn",
    "olsztynem": "olsztyn",
    "opolu": "opole",
    "patrycją żuk": "patrycja_zuk",
    "patrycjo": "patrycja",
    "sebastianowi chmurze": "sebastian_chmura",
    "stanisławem gajda": "stanislaw_gajda",
    "stanisławowi gajdzie": "stanislaw_gajda",
    "szczecina": "szczecin",
    "szczecinie": "szczecin",
    "tymona bednarka": "tymon_bednarek",
    "weroniką stachura": "weronika_stachura",
    "weroniką stachurą": "weronika_stachura",
    "weroniko": "weronika",
    "łodzi": "lodz",
    "wiktorią sową": "wiktoria_sowa",
    "wiktorię sowę": "wiktoria_sowa",
    "zakopanego": "zakopane",
}


def load_safety_corpus_json(path: Path) -> CorrectionCorpus:
    """Load and validate the UTF-8 JSON safety corpus."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid safety corpus JSON: {path}") from error
    return validate_safety_corpus(raw)


def load_safety_corpus_xml(path: Path) -> CorrectionCorpus:
    """Load and validate the equivalent XML safety corpus."""

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"invalid safety corpus XML: {path}") from error
    return validate_safety_corpus(_xml_as_raw(root))


def validate_safety_corpus(raw: object) -> CorrectionCorpus:
    """Validate an exact schema-v3 safety corpus object and its invariants."""

    dataset = _require_object(raw, "corpus")
    _require_exact_fields(dataset, _TOP_LEVEL_FIELDS, "corpus")
    if dataset["schema_version"] != 3:
        raise ValueError("corpus schema_version must be 3")
    corpus_id = _require_id(dataset["id"], "corpus id")
    if corpus_id != CORPUS_ID:
        raise ValueError(f"corpus id must be {CORPUS_ID}")
    if dataset["language"] != "pl-PL":
        raise ValueError("corpus language must be pl-PL")
    holdout_state = dataset["holdout_state"]
    if holdout_state not in {"unfrozen-candidates", "frozen"}:
        raise ValueError("corpus holdout_state is invalid")
    provenance = _validate_provenance(dataset["provenance"], "corpus provenance")
    policy = _validate_review_policy(dataset["review_policy"])
    raw_cases = dataset["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("corpus cases must be a non-empty list")
    seen_ids: set[str] = set()
    cases = tuple(
        _validate_case(item, seen_ids, policy["checklist_version"])
        for item in raw_cases
    )
    _validate_balance(cases)
    _validate_isolation(cases)
    if holdout_state == "frozen" and any(
        case.review.status != policy["approval_status"] for case in cases
    ):
        raise ValueError("a frozen holdout cannot contain unapproved candidates")
    return CorrectionCorpus(
        schema_version=3,
        id=corpus_id,
        language="pl-PL",
        holdout_state=cast(str, holdout_state),
        provenance=provenance,
        required_reviewer=policy["required_reviewer"],
        checklist_version=policy["checklist_version"],
        cases=cases,
    )


def select_safety_cases_for_purpose(
    corpus: CorrectionCorpus,
    *,
    purpose: Literal["benchmark", "quality_gate", "training"],
) -> tuple[CorrectionCorpusCase, ...]:
    """Return approved cases when the safety corpus policy permits the purpose.

    Benchmark selection exposes approved development cases only. A quality
    gate requires the frozen state and all 160 approved holdout cases.
    Training use is always prohibited.
    """

    if corpus.id != CORPUS_ID:
        raise CorpusUsageError(
            "select_safety_cases_for_purpose requires the safety corpus"
        )
    return cast(
        tuple[CorrectionCorpusCase, ...],
        select_cases_for_purpose(corpus, purpose=purpose),
    )


def assert_no_cross_corpus_leakage(
    corpus: CorrectionCorpus,
    records: Iterable[IsolationRecord],
    *,
    source: str,
) -> None:
    """Reject records that leak into the safety corpus from another asset.

    Each record is compared against the safety corpus by normalized input,
    normalized template, canonical entity combination, and near-identical
    template family. Records without declared entity spans are spanned with
    the deterministic name-shape detector enriched with the safety corpus
    alias surfaces.
    """

    corpus_inputs = {_normalized_text(case.input) for case in corpus.cases}
    corpus_templates = {case.normalized_template for case in corpus.cases}
    corpus_signatures, alias_surfaces = _corpus_entity_alias_evidence(corpus)
    for record in records:
        label = f"{source}:{record.id}"
        if _normalized_text(record.input) in corpus_inputs:
            raise CorpusUsageError(f"cross-corpus leakage by input in {label}")
        if record.entity_spans and not _valid_training_spans(
            record.input, record.entity_spans
        ):
            raise CorpusUsageError(f"{label} has invalid entity span evidence")
        spans = record.entity_spans or _detect_training_entity_spans(
            record.input, alias_surfaces
        )
        template = derive_normalized_template(record.input, spans)
        if template in corpus_templates:
            raise CorpusUsageError(f"cross-corpus leakage by template in {label}")
        signature = _training_entity_signature(spans)
        if signature and signature in corpus_signatures:
            raise CorpusUsageError(
                f"cross-corpus leakage by entity combination in {label}"
            )
        for case in corpus.cases:
            if _templates_are_near(template, case.normalized_template):
                raise CorpusUsageError(
                    "near-identical cross-corpus template family: "
                    f"{label} and {case.id}"
                )


def canonical_corpus_json(raw: object) -> str:
    """Serialize canonical JSON with sorted keys and no extra whitespace."""

    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safety_corpus_digest(raw: object) -> str:
    """Hash the canonical UTF-8 JSON representation of the corpus."""

    return hashlib.sha256(canonical_corpus_json(raw).encode("utf-8")).hexdigest()


def safety_entity_catalog_ids() -> frozenset[str]:
    """Return every canonical entity identifier in the safety catalog."""

    return frozenset(
        _entity_id(surface) for surface in SAFETY_CONTROLLED_ENTITY_SURFACES
    )


def _validate_review_policy(raw: object) -> dict[str, str]:
    policy = _require_object(raw, "review policy")
    _require_exact_fields(policy, _REVIEW_POLICY_FIELDS, "review policy")
    expected = {
        "candidate_status": "pending-human-review",
        "approval_status": "human-reviewed",
        "required_reviewer": "Paweł Cyroń",
        "checklist_version": REVIEW_CHECKLIST_VERSION,
        "training_use": "prohibited",
    }
    if policy != expected:
        raise ValueError("corpus review policy must match the safety corpus policy")
    return cast(dict[str, str], policy)


def _validate_case(
    raw: object, seen_ids: set[str], checklist_version: str
) -> CorrectionCorpusCase:
    case = _require_object(raw, "case")
    _require_exact_fields(case, _CASE_FIELDS, "case")
    case_id = _require_id(case["id"], "case id")
    if case_id in seen_ids:
        raise ValueError(f"duplicate case id: {case_id}")
    seen_ids.add(case_id)
    stratum = _require_member(case["stratum"], _STRATA, "case stratum")
    split = _require_member(case["split"], _SPLITS, "case split")
    unit = _require_member(case["unit"], _UNITS, "case unit")
    input_text = _require_text(case["input"], "case input")
    expected_output = _require_text(case["expected_output"], "case expected_output")
    description = _require_text(case["description"], "case description")
    entity_spans = _validate_entity_spans(case["entity_spans"], input_text, case_id)
    normalized_template = _require_text(
        case["normalized_template"], "case normalized_template"
    )
    if normalized_template != derive_normalized_template(input_text, entity_spans):
        raise ValueError(
            "case normalized_template must equal derived normalized_template"
        )
    tags = _require_string_tuple(case["tags"], "case tags")
    if not tags or len(tags) != len(set(tags)):
        raise ValueError("case tags must be a non-empty unique string list")
    entity_ids = _require_string_tuple(case["entity_ids"], "case entity_ids")
    derived_entity_ids = tuple(_entity_id(span.surface) for span in entity_spans)
    if entity_ids != derived_entity_ids:
        raise ValueError("case entity_ids must equal derived entity_ids")
    if len(entity_ids) != len(set(entity_ids)):
        raise ValueError("case entity_ids must be unique")
    protected = case["protected_phenomenon"]
    if protected is not None and (
        not isinstance(protected, str) or _CASE_ID.fullmatch(protected) is None
    ):
        raise ValueError(
            "case protected_phenomenon must be null or lowercase snake_case"
        )
    provenance = _validate_provenance(case["provenance"], f"case {case_id} provenance")
    review = _validate_review(case["review"], case_id, checklist_version)
    raw_edits = case["edits"]
    if not isinstance(raw_edits, list):
        raise ValueError("case edits must be a list")
    edits = tuple(_validate_edit(item, input_text, case_id) for item in raw_edits)
    _validate_non_overlapping(edits, case_id)
    if stratum == "hard_negative":
        if edits or input_text != expected_output:
            raise ValueError("hard negative must have zero edits and unchanged output")
        if protected is None:
            raise ValueError("hard negative must name a protected phenomenon")
    else:
        if not edits or input_text == expected_output:
            raise ValueError("positive case must contain a correction")
        if protected is not None:
            raise ValueError("positive case cannot name a protected phenomenon")
        reconstructed = _apply_edits(input_text, edits)
        if reconstructed != expected_output:
            raise ValueError(f"case {case_id} edits do not reconstruct expected output")
    return CorrectionCorpusCase(
        id=case_id,
        stratum=stratum,
        split=split,
        unit=unit,
        input=input_text,
        expected_output=expected_output,
        description=description,
        tags=tags,
        normalized_template=normalized_template,
        entity_ids=entity_ids,
        entity_spans=entity_spans,
        protected_phenomenon=cast(str | None, protected),
        provenance=provenance,
        review=review,
        edits=edits,
    )


def _validate_entity_spans(
    raw: object, input_text: str, case_id: str
) -> tuple[EntitySpan, ...]:
    if not isinstance(raw, list):
        raise ValueError("case entity_spans must be a list")
    spans: list[EntitySpan] = []
    for item in raw:
        entity = _require_object(item, f"case {case_id} entity span")
        _require_exact_fields(entity, _ENTITY_SPAN_FIELDS, "entity span")
        start = _require_offset(entity["start"], "entity start")
        end = _require_offset(entity["end"], "entity end")
        surface = entity["surface"]
        if not isinstance(surface, str) or not surface:
            raise ValueError("entity surface must be a non-empty string")
        if end <= start or end > len(input_text) or input_text[start:end] != surface:
            raise ValueError("entity surface does not match input range")
        if surface not in SAFETY_CONTROLLED_ENTITY_SURFACES:
            raise ValueError("entity surface violates the controlled entity policy")
        spans.append(EntitySpan(start=start, end=end, surface=surface))
    ordered = tuple(sorted(spans, key=lambda item: item.start))
    for left, right in zip(ordered, ordered[1:], strict=False):
        if right.start < left.end:
            raise ValueError("entity spans must not overlap")
    if ordered != _detect_controlled_entity_spans(input_text):
        raise ValueError("case must include every controlled entity span")
    return ordered


def _detect_controlled_entity_spans(input_text: str) -> tuple[EntitySpan, ...]:
    candidates: list[EntitySpan] = []
    occupied: list[tuple[int, int]] = []
    for surface in sorted(SAFETY_CONTROLLED_ENTITY_SURFACES, key=len, reverse=True):
        cursor = 0
        while True:
            start = input_text.find(surface, cursor)
            if start < 0:
                break
            end = start + len(surface)
            cursor = end
            left_boundary = start == 0 or not input_text[start - 1].isalpha()
            right_boundary = end == len(input_text) or not input_text[end].isalpha()
            overlaps = any(
                start < other_end and other_start < end
                for other_start, other_end in occupied
            )
            if left_boundary and right_boundary and not overlaps:
                candidates.append(EntitySpan(start=start, end=end, surface=surface))
                occupied.append((start, end))
    return tuple(sorted(candidates, key=lambda item: item.start))


def _entity_id(surface: str) -> str:
    override = SAFETY_ENTITY_ID_OVERRIDES.get(surface.casefold())
    if override is not None:
        return override
    value = unicodedata.normalize("NFKD", surface.casefold()).replace("ł", "l")
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _entity_signature(spans: tuple[EntitySpan, ...]) -> tuple[str, ...]:
    return tuple(sorted(_entity_id(span.surface) for span in spans))


def _validate_isolation(cases: tuple[CorrectionCorpusCase, ...]) -> None:
    inputs: dict[str, str] = {}
    templates: dict[str, str] = {}
    entities_by_split: dict[str, dict[tuple[str, ...], str]] = {
        "development": {},
        "holdout": {},
    }
    for case in cases:
        normalized_input = _normalized_text(case.input)
        if normalized_input in inputs:
            raise ValueError(
                f"duplicate input in cases {inputs[normalized_input]} and {case.id}"
            )
        inputs[normalized_input] = case.id
        existing_template = templates.get(case.normalized_template)
        if existing_template is not None:
            raise ValueError(
                "duplicate normalized template in cases "
                f"{existing_template} and {case.id}"
            )
        templates[case.normalized_template] = case.id
        signature = _entity_signature(case.entity_spans)
        if signature:
            entities_by_split[case.split][signature] = case.id

    shared_entities = set(entities_by_split["development"]) & set(
        entities_by_split["holdout"]
    )
    if shared_entities:
        raise ValueError("entity combination leakage across splits")

    for (left_template, left_id), (right_template, right_id) in combinations(
        templates.items(), 2
    ):
        if _templates_are_near(left_template, right_template):
            raise ValueError(
                f"near-identical template family: {left_id} and {right_id}"
            )


__all__ = [
    "CORPUS_ID",
    "REVIEW_CHECKLIST_VERSION",
    "SAFETY_CONTROLLED_ENTITY_SURFACES",
    "SAFETY_ENTITY_ID_OVERRIDES",
    "assert_no_cross_corpus_leakage",
    "canonical_corpus_json",
    "load_safety_corpus_json",
    "load_safety_corpus_xml",
    "safety_corpus_digest",
    "safety_entity_catalog_ids",
    "select_safety_cases_for_purpose",
    "validate_safety_corpus",
]
