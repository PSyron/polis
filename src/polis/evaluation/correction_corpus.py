"""Validate the independently reviewed Polish correction corpus schema v3."""

from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any, Literal, cast

_CASE_ID = re.compile(r"[a-z][a-z0-9_]*\Z")
_STRATA = frozenset({"inflection", "syntax", "punctuation", "hard_negative"})
_SPLITS = frozenset({"development", "holdout"})
_UNITS = frozenset({"sentence", "short_paragraph"})
_CATEGORIES = frozenset({"inflection", "agreement", "syntax", "punctuation"})
_PROVENANCE_FIELDS = frozenset({"source", "license", "created", "method", "notes"})
_REVIEW_FIELDS = frozenset({"status", "reviewer", "reviewed_at", "checklist_version"})
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
_EDIT_FIELDS = frozenset(
    {"category", "start", "end", "original", "suggestion", "rationale"}
)
_ENTITY_SPAN_FIELDS = frozenset({"start", "end", "surface"})
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "id",
        "language",
        "holdout_state",
        "provenance",
        "review_policy",
        "cases",
    }
)
_REVIEW_POLICY_FIELDS = frozenset(
    {
        "candidate_status",
        "approval_status",
        "required_reviewer",
        "checklist_version",
        "training_use",
    }
)
_CONTROLLED_ENTITY_SURFACES = frozenset(
    {
        "Adamowi Lis",
        "Agnieszka",
        "Adam Lis",
        "Adamem Lis",
        "Aleksandrę Kamińska",
        "Alicji Dudkowej",
        "Andrzeja Grabowski",
        "Anna",
        "Anna Kowalska",
        "Annie Kowalska",
        "Annie Kowalskiej",
        "Anną Kowalską",
        "Annę Górska",
        "Annę Kowalską",
        "Anny Kowalskiej",
        "Barbary Piotrowska",
        "Bartosza Ostrowskiego",
        "Carmen Miller",
        "Damianie Walczak",
        "Dominique",
        "Elżbiety Rutkowska",
        "Ewie Szymańskiej",
        "Ewy Nowicka",
        "Gdańsk",
        "Grabowskiego",
        "Grzegorz Sobczakowi",
        "Górską",
        "Inez Nowak",
        "Iwoną Sikora",
        "Jabłońskiemu",
        "Jakuba Michalski",
        "Jan",
        "Janem Nowak",
        "Jankowskiego",
        "Joannie Dąbrowskiej",
        "Joannie Szymańska",
        "Kaczmarkiem",
        "Karolina",
        "Kasiu",
        "Klara",
        "Kozłowskiej",
        "Krakowa",
        "Krzysztof Woźniak",
        "Krzysztofa Dąbrowski",
        "Lee Chen",
        "Maria",
        "Marka Woźniak",
        "Martą Lewandowska",
        "Martą Zielińską",
        "Mateusza Nowak",
        "Michale Wójcik",
        "Michalskiemu",
        "Michała Wójcika",
        "Norbert",
        "Nicole Kidman",
        "Noemi",
        "Oldze Pawłowska",
        "Olę",
        "Paweł",
        "Pawła Wiśniewskiego",
        "Pawłowskiej",
        "Piotrowi Nowakowi",
        "Piotrowi Zieliński",
        "Piotrowskiej",
        "Poznań",
        "Przemysławie Zalewski",
        "Rafała Baran",
        "Robertem Król",
        "Roman",
        "Szymonem Jankowski",
        "Tomasz Kamiński",
        "Tomasza Wiśniewski",
        "Toruń",
        "Walczakowi",
        "Warszawę",
        "Wojciechem Jabłoński",
        "Wrocławia",
        "Zofii Kozłowska",
        "Zofii Lewandowskiej",
        "Zosia",
        "Filipie",
        "Helena",
        "Igor",
        "Leno",
        "Łukaszem Kaczmarek",
    }
)
_ENTITY_ID_OVERRIDES = {
    "adamowi lis": "adam_lis",
    "aleksandrę kamińska": "aleksandra_kaminska",
    "andrzeja grabowski": "andrzej_grabowski",
    "annę górska": "anna_gorska",
    "anna kowalska": "anna_kowalska",
    "annie kowalska": "anna_kowalska",
    "annie kowalskiej": "anna_kowalska",
    "anną kowalską": "anna_kowalska",
    "annę kowalską": "anna_kowalska",
    "anny kowalskiej": "anna_kowalska",
    "barbary piotrowska": "barbara_piotrowska",
    "bartosza ostrowskiego": "bartosz_ostrowski",
    "damianie walczak": "damian_walczak",
    "elżbiety rutkowska": "elzbieta_rutkowska",
    "ewie szymańskiej": "ewa_szymanska",
    "ewy nowicka": "ewa_nowicka",
    "filipie": "filip",
    "grabowskiego": "grabowski",
    "grzegorz sobczakowi": "grzegorz_sobczak",
    "jabłońskiemu": "jablonski",
    "jakuba michalski": "jakub_michalski",
    "janem nowak": "jan_nowak",
    "joannie dąbrowskiej": "joanna_dabrowska",
    "joannie szymańska": "joanna_szymanska",
    "kaczmarkiem": "kaczmarek",
    "kasiu": "kasia",
    "kozłowskiej": "kozlowska",
    "krzysztofa dąbrowski": "krzysztof_dabrowski",
    "leno": "lena",
    "łukaszem kaczmarek": "lukasz_kaczmarek",
    "marka woźniak": "marek_wozniak",
    "mateusza nowak": "mateusz_nowak",
    "michale wójcik": "michal_wojcik",
    "michalskiemu": "michalski",
    "michała wójcika": "michal_wojcik",
    "oldze pawłowska": "olga_pawlowska",
    "pawła wiśniewskiego": "pawel_wisniewski",
    "pawłowskiej": "pawlowska",
    "piotrowi nowakowi": "piotr_nowak",
    "piotrowi zieliński": "piotr_zielinski",
    "piotrowskiej": "piotrowska",
    "przemysławie zalewski": "przemyslaw_zalewski",
    "rafała baran": "rafal_baran",
    "robertem król": "robert_krol",
    "szymonem jankowski": "szymon_jankowski",
    "tomasza wiśniewski": "tomasz_wisniewski",
    "walczakowi": "walczak",
    "warszawę": "warszawa",
    "wojciechem jabłoński": "wojciech_jablonski",
    "wrocławia": "wroclaw",
    "zofii lewandowskiej": "zofia_lewandowska",
    "zofii kozłowska": "zofia_kozlowska",
    "jankowskiego": "jankowski",
}


class CorpusUsageError(ValueError):
    """Raised when corpus review or isolation rules forbid a requested use."""


@dataclass(frozen=True, slots=True)
class CorpusProvenance:
    """Auditable origin and licensing information."""

    source: str
    license: str
    created: str
    method: str
    notes: str


@dataclass(frozen=True, slots=True)
class CaseReview:
    """Human-review state for one candidate case."""

    status: str
    reviewer: str | None
    reviewed_at: str | None
    checklist_version: str


@dataclass(frozen=True, slots=True)
class CorpusEdit:
    """One exact minimal edit against the original input."""

    category: str
    start: int
    end: int
    original: str
    suggestion: str
    rationale: str


@dataclass(frozen=True, slots=True)
class EntitySpan:
    """One exact proper-name surface used for deterministic isolation."""

    start: int
    end: int
    surface: str


@dataclass(frozen=True, slots=True)
class CorrectionCorpusCase:
    """One candidate positive case or protected hard negative."""

    id: str
    stratum: str
    split: str
    unit: str
    input: str
    expected_output: str
    description: str
    tags: tuple[str, ...]
    normalized_template: str
    entity_ids: tuple[str, ...]
    entity_spans: tuple[EntitySpan, ...]
    protected_phenomenon: str | None
    provenance: CorpusProvenance
    review: CaseReview
    edits: tuple[CorpusEdit, ...]


@dataclass(frozen=True, slots=True)
class CorrectionCorpus:
    """Validated schema-v3 corpus with explicit review and split state."""

    schema_version: int
    id: str
    language: str
    holdout_state: str
    provenance: CorpusProvenance
    required_reviewer: str
    checklist_version: str
    cases: tuple[CorrectionCorpusCase, ...]


@dataclass(frozen=True, slots=True)
class IsolationRecord:
    """Minimal training-record metadata used only for leakage checks."""

    id: str
    input: str
    entity_spans: tuple[EntitySpan, ...] = ()


def load_correction_corpus_json(path: Path) -> CorrectionCorpus:
    """Load and validate one UTF-8 JSON representation of corpus v3."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid correction corpus JSON: {path}") from error
    return validate_correction_corpus(raw)


def load_correction_corpus_xml(path: Path) -> CorrectionCorpus:
    """Load and validate one XML representation of corpus v3."""

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"invalid correction corpus XML: {path}") from error
    return validate_correction_corpus(_xml_as_raw(root))


def validate_correction_corpus(raw: object) -> CorrectionCorpus:
    """Validate an exact schema-v3 object and all corpus invariants."""

    dataset = _require_object(raw, "corpus")
    _require_exact_fields(dataset, _TOP_LEVEL_FIELDS, "corpus")
    if dataset["schema_version"] != 3:
        raise ValueError("corpus schema_version must be 3")
    corpus_id = _require_id(dataset["id"], "corpus id")
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


def select_cases_for_purpose(
    corpus: CorrectionCorpus,
    *,
    purpose: Literal["benchmark", "quality_gate", "training"],
) -> tuple[CorrectionCorpusCase, ...]:
    """Return only approved cases when corpus policy permits the purpose."""

    if purpose == "training":
        raise CorpusUsageError("evaluation corpus use for training is prohibited")
    if purpose not in {"benchmark", "quality_gate"}:
        raise CorpusUsageError(f"unknown corpus purpose: {purpose!r}")
    approved = tuple(
        case for case in corpus.cases if case.review.status == "human-reviewed"
    )
    if not approved:
        raise CorpusUsageError(
            "all corpus candidates are pending-human-review and unavailable for "
            f"{purpose}"
        )
    if purpose == "quality_gate":
        if corpus.holdout_state != "frozen":
            raise CorpusUsageError("quality_gate requires a frozen holdout")
        holdout = tuple(case for case in approved if case.split == "holdout")
        if len(holdout) != 160:
            raise CorpusUsageError(
                "quality_gate requires all 160 approved holdout cases"
            )
        return holdout
    development = tuple(case for case in approved if case.split == "development")
    if not development:
        raise CorpusUsageError(
            "no approved development cases are available for benchmark"
        )
    return development


def assert_no_training_leakage(
    corpus: CorrectionCorpus, records: Iterable[IsolationRecord]
) -> None:
    """Reject closed-contract training metadata overlapping evaluation data."""

    corpus_inputs = {_normalized_text(case.input) for case in corpus.cases}
    corpus_templates = {case.normalized_template for case in corpus.cases}
    corpus_entities, corpus_alias_surfaces = _corpus_entity_alias_evidence(corpus)
    for record in records:
        if _normalized_text(record.input) in corpus_inputs:
            raise CorpusUsageError(f"training leakage by input in {record.id}")
        if not _valid_training_spans(record.input, record.entity_spans):
            raise CorpusUsageError(
                f"training record {record.id} has invalid entity span evidence"
            )
        template = derive_normalized_template(record.input, record.entity_spans)
        if template in corpus_templates:
            raise CorpusUsageError(f"training leakage by template in {record.id}")
        entity_signature = _training_entity_signature(record.entity_spans)
        if entity_signature and entity_signature in corpus_entities:
            raise CorpusUsageError(
                f"training leakage by entity combination in {record.id}"
            )
        detected_spans = _detect_training_entity_spans(
            record.input, corpus_alias_surfaces
        )
        if record.entity_spans != detected_spans:
            raise CorpusUsageError(
                f"training record {record.id} requires complete entity span evidence"
            )


def _validate_review_policy(raw: object) -> dict[str, str]:
    policy = _require_object(raw, "review policy")
    _require_exact_fields(policy, _REVIEW_POLICY_FIELDS, "review policy")
    expected = {
        "candidate_status": "pending-human-review",
        "approval_status": "human-reviewed",
        "required_reviewer": "Paweł Cyroń",
        "checklist_version": "corpus-v3-review-v1",
        "training_use": "prohibited",
    }
    if policy != expected:
        raise ValueError("corpus review policy must match the schema-v3 policy")
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


def derive_normalized_template(
    input_text: str, entity_spans: tuple[EntitySpan, ...]
) -> str:
    """Derive the only accepted template from input and exact entity spans."""

    value = input_text
    for span in sorted(entity_spans, key=lambda item: item.start, reverse=True):
        value = value[: span.start] + "<entity>" + value[span.end :]
    value = _normalized_text(value)
    value = re.sub(r"https?://\S+", "<url>", value)
    return re.sub(r"\b\d+(?:[.,]\d+)?\b", "<number>", value)


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
        if surface not in _CONTROLLED_ENTITY_SURFACES:
            raise ValueError("entity surface violates the controlled entity policy")
        spans.append(EntitySpan(start=start, end=end, surface=surface))
    ordered = tuple(sorted(spans, key=lambda item: item.start))
    for left, right in zip(ordered, ordered[1:], strict=False):
        if right.start < left.end:
            raise ValueError("entity spans must not overlap")
    if ordered != _detect_controlled_entity_spans(input_text):
        raise ValueError("case must include every controlled entity span")
    return ordered


def _entity_id(surface: str) -> str:
    override = _ENTITY_ID_OVERRIDES.get(surface.casefold())
    if override is not None:
        return override
    value = unicodedata.normalize("NFKD", surface.casefold()).replace("ł", "l")
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _entity_signature(spans: tuple[EntitySpan, ...]) -> tuple[str, ...]:
    return tuple(sorted(_entity_id(span.surface) for span in spans))


def _training_entity_signature(spans: tuple[EntitySpan, ...]) -> tuple[str, ...]:
    tokens = (
        token
        for span in spans
        for token in _canonical_name_surface(span.surface).split("_")
    )
    return tuple(sorted(tokens))


def _canonical_name_surface(surface: str) -> str:
    tokens = re.findall(r"[^\W\d_]+", surface, flags=re.UNICODE)
    return "_".join(_canonical_name_token(token) for token in tokens)


def _canonical_name_token(token: str) -> str:
    folded = unicodedata.normalize("NFC", token.casefold())
    removed_nasal_ending = folded.endswith(("ą", "ę"))
    if removed_nasal_ending:
        folded = folded[:-1]
    value = unicodedata.normalize("NFKD", folded).replace("ł", "l")
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    suffixes = (
        "iami",
        "iego",
        "ami",
        "ach",
        "iem",
        "owi",
        "iej",
        "emu",
        "ej",
        "om",
        "em",
        "im",
        "ym",
        "ie",
        "a",
        "e",
        "y",
        "i",
        "u",
    )
    if not removed_nasal_ending:
        for suffix in suffixes:
            if value.endswith(suffix) and len(value) - len(suffix) >= 3:
                value = value[: -len(suffix)]
                break
    if value.endswith("ek") and len(value) > 4:
        return value[:-2] + "k"
    return value


def _corpus_entity_alias_evidence(
    corpus: CorrectionCorpus,
) -> tuple[set[tuple[str, ...]], frozenset[str]]:
    signatures: set[tuple[str, ...]] = set()
    surfaces: set[str] = set()
    for case in corpus.cases:
        if not case.entity_spans:
            continue
        input_surfaces = tuple(span.surface for span in case.entity_spans)
        corrected_surfaces = tuple(
            _corrected_entity_surface(case, span) for span in case.entity_spans
        )
        for variants in (input_surfaces, corrected_surfaces):
            alias_spans = tuple(
                EntitySpan(0, len(surface), surface) for surface in variants
            )
            signatures.add(_training_entity_signature(alias_spans))
            surfaces.update(variants)
    return signatures, frozenset(surfaces)


def _corrected_entity_surface(case: CorrectionCorpusCase, span: EntitySpan) -> str:
    value = span.surface
    contained_edits = tuple(
        edit for edit in case.edits if span.start <= edit.start and edit.end <= span.end
    )
    for edit in sorted(contained_edits, key=lambda item: item.start, reverse=True):
        start = edit.start - span.start
        end = edit.end - span.start
        value = value[:start] + edit.suggestion + value[end:]
    return value


def _detect_training_entity_spans(
    input_text: str, known_surfaces: Iterable[str] = ()
) -> tuple[EntitySpan, ...]:
    words = tuple(re.finditer(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*", input_text))
    spans = list(_detect_known_entity_spans(input_text, known_surfaces))
    group: list[re.Match[str]] = []

    def finish_group() -> None:
        if not group:
            return
        first = group[0]
        last = group[-1]
        if len(group) > 1 or not _is_sentence_initial(input_text, first.start()):
            spans.append(
                EntitySpan(
                    start=first.start(),
                    end=last.end(),
                    surface=input_text[first.start() : last.end()],
                )
            )
        group.clear()

    for word in words:
        if any(word.start() < span.end and span.start < word.end() for span in spans):
            finish_group()
            continue
        if _is_name_shaped_token(word.group()):
            if group and input_text[group[-1].end() : word.start()].strip():
                finish_group()
            group.append(word)
        else:
            finish_group()
    finish_group()
    return tuple(sorted(spans, key=lambda item: item.start))


def _detect_known_entity_spans(
    input_text: str, known_surfaces: Iterable[str]
) -> tuple[EntitySpan, ...]:
    spans: list[EntitySpan] = []
    for surface in sorted(set(known_surfaces), key=len, reverse=True):
        for match in re.finditer(re.escape(surface), input_text, flags=re.IGNORECASE):
            start, end = match.span()
            left_boundary = start == 0 or not input_text[start - 1].isalpha()
            right_boundary = end == len(input_text) or not input_text[end].isalpha()
            overlaps = any(start < other.end and other.start < end for other in spans)
            if left_boundary and right_boundary and not overlaps:
                spans.append(
                    EntitySpan(start=start, end=end, surface=input_text[start:end])
                )
    return tuple(sorted(spans, key=lambda item: item.start))


def _is_name_shaped_token(token: str) -> bool:
    letters = tuple(character for character in token if character.isalpha())
    if not letters:
        return False
    return all(character.isupper() for character in letters) or letters[0].isupper()


def _is_sentence_initial(input_text: str, start: int) -> bool:
    prefix = input_text[:start].rstrip()
    return not prefix or prefix[-1] in ".!?"


def _valid_training_spans(input_text: str, spans: tuple[EntitySpan, ...]) -> bool:
    previous_end = -1
    for span in spans:
        if (
            span.start < 0
            or span.end <= span.start
            or span.end > len(input_text)
            or span.start < previous_end
            or input_text[span.start : span.end] != span.surface
        ):
            return False
        previous_end = span.end
    return True


def _detect_controlled_entity_spans(input_text: str) -> tuple[EntitySpan, ...]:
    candidates: list[EntitySpan] = []
    occupied: list[tuple[int, int]] = []
    for surface in sorted(_CONTROLLED_ENTITY_SURFACES, key=len, reverse=True):
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


def _validate_edit(raw: object, input_text: str, case_id: str) -> CorpusEdit:
    edit = _require_object(raw, f"case {case_id} edit")
    _require_exact_fields(edit, _EDIT_FIELDS, "edit")
    category = _require_member(edit["category"], _CATEGORIES, "edit category")
    start = _require_offset(edit["start"], "edit start")
    end = _require_offset(edit["end"], "edit end")
    if end < start or end > len(input_text):
        raise ValueError("edit range must be within input")
    original = edit["original"]
    suggestion = edit["suggestion"]
    if not isinstance(original, str) or not isinstance(suggestion, str):
        raise ValueError("edit original and suggestion must be strings")
    if input_text[start:end] != original:
        raise ValueError("edit original does not match input range")
    if original == suggestion:
        raise ValueError("edit suggestion must differ from original")
    rationale = _require_text(edit["rationale"], "edit rationale")
    return CorpusEdit(category, start, end, original, suggestion, rationale)


def _validate_non_overlapping(edits: tuple[CorpusEdit, ...], case_id: str) -> None:
    replacements = sorted(
        (edit.start, edit.end) for edit in edits if edit.start != edit.end
    )
    for (_, previous_end), (start, _) in zip(
        replacements, replacements[1:], strict=False
    ):
        if start < previous_end:
            raise ValueError(f"case {case_id} has overlapping edits")
    insertion_offsets = [edit.start for edit in edits if edit.start == edit.end]
    if len(insertion_offsets) != len(set(insertion_offsets)):
        raise ValueError(f"case {case_id} has duplicate insertion edits")
    for offset in insertion_offsets:
        if any(start <= offset < end for start, end in replacements):
            raise ValueError(f"case {case_id} has overlapping insertion edit")


def _validate_balance(cases: tuple[CorrectionCorpusCase, ...]) -> None:
    if len(cases) != 240:
        raise ValueError("corpus must contain exactly 240 cases")
    for stratum in _STRATA:
        stratum_cases = [case for case in cases if case.stratum == stratum]
        if len(stratum_cases) != 60:
            raise ValueError(f"stratum {stratum} must contain exactly 60 cases")
        counts = {
            split: sum(case.split == split for case in stratum_cases)
            for split in _SPLITS
        }
        if counts != {"development": 20, "holdout": 40}:
            raise ValueError(f"stratum {stratum} must use a 20/40 split")


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


def _validate_provenance(raw: object, label: str) -> CorpusProvenance:
    provenance = _require_object(raw, label)
    _require_exact_fields(provenance, _PROVENANCE_FIELDS, label)
    if provenance["license"] != "CC0-1.0":
        raise ValueError(f"{label} license must be CC0-1.0")
    values = {
        field: _require_text(provenance[field], f"{label} {field}")
        for field in ("source", "created", "method", "notes")
    }
    return CorpusProvenance(
        source=values["source"],
        license="CC0-1.0",
        created=values["created"],
        method=values["method"],
        notes=values["notes"],
    )


def _validate_review(raw: object, case_id: str, checklist_version: str) -> CaseReview:
    review = _require_object(raw, f"case {case_id} review")
    _require_exact_fields(review, _REVIEW_FIELDS, "case review")
    if review["checklist_version"] != checklist_version:
        raise ValueError("case review checklist version does not match corpus policy")
    status = review["status"]
    reviewer = review["reviewer"]
    reviewed_at = review["reviewed_at"]
    if status == "pending-human-review":
        if reviewer is not None or reviewed_at is not None:
            raise ValueError("pending review cannot name a reviewer or review date")
    elif status == "human-reviewed":
        if (
            reviewer != "Paweł Cyroń"
            or not isinstance(reviewed_at, str)
            or not reviewed_at
        ):
            raise ValueError(
                "human-reviewed case requires Paweł Cyroń and a review date"
            )
        try:
            parsed_review_date = date.fromisoformat(reviewed_at)
        except ValueError as error:
            raise ValueError("reviewed_at must be an ISO-8601 date") from error
        if reviewed_at != parsed_review_date.isoformat():
            raise ValueError("reviewed_at must be an ISO-8601 date")
    else:
        raise ValueError("case review status is invalid")
    return CaseReview(
        status=cast(str, status),
        reviewer=cast(str | None, reviewer),
        reviewed_at=cast(str | None, reviewed_at),
        checklist_version=checklist_version,
    )


def _apply_edits(input_text: str, edits: tuple[CorpusEdit, ...]) -> str:
    output = input_text
    for edit in sorted(edits, key=lambda item: item.start, reverse=True):
        output = output[: edit.start] + edit.suggestion + output[edit.end :]
    return output


def _templates_are_near(left: str, right: str) -> bool:
    left_tokens = _template_tokens(left)
    right_tokens = _template_tokens(right)
    similarity = SequenceMatcher(
        None, left_tokens, right_tokens, autojunk=False
    ).ratio()
    distance = _token_edit_distance(left_tokens, right_tokens)
    longest = max(len(left_tokens), len(right_tokens))
    return similarity >= 0.92 or (longest <= 8 and distance <= 1)


def _template_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"<[^>]+>|[^\W_]+|[^\w\s]", value, flags=re.UNICODE))


def _token_edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_token in enumerate(left, 1):
        current = [left_index]
        for right_index, right_token in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_token != right_token),
                )
            )
        previous = current
    return previous[-1]


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _require_object(raw: object, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], raw)


def _require_exact_fields(
    value: dict[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(f"{label} must contain exactly the schema-v3 fields")


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{label} must use Unicode NFC")
    return value


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _CASE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must use lowercase snake_case")
    return value


def _require_member(value: object, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{label} is invalid")
    return value


def _require_string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return tuple(value)


def _require_offset(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _xml_as_raw(root: ET.Element) -> dict[str, object]:
    if root.tag != "corpus":
        raise ValueError("XML root must be corpus")
    _validate_xml_structure(root)
    provenance = root.find("provenance")
    review_policy = root.find("review_policy")
    cases_node = root.find("cases")
    if provenance is None or review_policy is None or cases_node is None:
        raise ValueError("XML corpus is missing required sections")
    return {
        "schema_version": _xml_int(root.get("schema_version"), "schema_version"),
        "id": root.get("id"),
        "language": root.get("language"),
        "holdout_state": root.get("holdout_state"),
        "provenance": dict(provenance.attrib),
        "review_policy": dict(review_policy.attrib),
        "cases": [_xml_case(case) for case in cases_node.findall("case")],
    }


def _xml_case(node: ET.Element) -> dict[str, object]:
    protected = node.get("protected_phenomenon") or None
    provenance = node.find("provenance")
    review = node.find("review")
    tags = node.find("tags")
    entities = node.find("entity_ids")
    entity_spans = node.find("entity_spans")
    edits = node.find("edits")
    if any(
        item is None
        for item in (provenance, review, tags, entities, entity_spans, edits)
    ):
        raise ValueError("XML case is missing required sections")
    assert provenance is not None
    assert review is not None
    assert tags is not None
    assert entities is not None
    assert entity_spans is not None
    assert edits is not None
    reviewer = review.get("reviewer") or None
    reviewed_at = review.get("reviewed_at") or None
    return {
        "id": node.get("id"),
        "stratum": node.get("stratum"),
        "split": node.get("split"),
        "unit": node.get("unit"),
        "input": node.findtext("input"),
        "expected_output": node.findtext("expected_output"),
        "description": node.findtext("description"),
        "normalized_template": node.findtext("normalized_template"),
        "tags": [tag.text or "" for tag in tags.findall("tag")],
        "entity_ids": [entity.text or "" for entity in entities.findall("entity")],
        "entity_spans": [
            {
                "start": _xml_int(entity.get("start"), "entity start"),
                "end": _xml_int(entity.get("end"), "entity end"),
                "surface": entity.get("surface"),
            }
            for entity in entity_spans.findall("entity")
        ],
        "protected_phenomenon": protected,
        "provenance": dict(provenance.attrib),
        "review": {
            "status": review.get("status"),
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "checklist_version": review.get("checklist_version"),
        },
        "edits": [_xml_edit(edit) for edit in edits.findall("edit")],
    }


def _xml_edit(node: ET.Element) -> dict[str, object]:
    return {
        "category": node.get("category"),
        "start": _xml_int(node.get("start"), "edit start"),
        "end": _xml_int(node.get("end"), "edit end"),
        "original": node.get("original"),
        "suggestion": node.get("suggestion"),
        "rationale": node.get("rationale"),
    }


def _xml_int(value: str | None, label: str) -> int:
    try:
        return int(value or "")
    except ValueError as error:
        raise ValueError(f"XML {label} must be an integer") from error


def _validate_xml_structure(root: ET.Element) -> None:
    _require_xml_attributes(
        root, {"schema_version", "id", "language", "holdout_state"}, "corpus"
    )
    _require_xml_children(root, {"provenance", "review_policy", "cases"}, "corpus")
    provenance = root.find("provenance")
    policy = root.find("review_policy")
    cases = root.find("cases")
    assert provenance is not None
    assert policy is not None
    assert cases is not None
    _require_xml_attributes(provenance, set(_PROVENANCE_FIELDS), "provenance")
    _require_xml_leaf(provenance, "provenance")
    _require_xml_attributes(policy, set(_REVIEW_POLICY_FIELDS), "review_policy")
    _require_xml_leaf(policy, "review_policy")
    _require_xml_attributes(cases, set(), "cases")
    _require_xml_container_text(cases, "cases")
    if any(child.tag != "case" for child in cases):
        raise ValueError("unknown XML node below cases")
    for case in cases:
        _validate_xml_case_structure(case)


def _validate_xml_case_structure(case: ET.Element) -> None:
    _require_xml_attributes(
        case,
        {"id", "stratum", "split", "unit", "protected_phenomenon"},
        "case",
    )
    expected_children = {
        "input",
        "expected_output",
        "description",
        "normalized_template",
        "tags",
        "entity_ids",
        "entity_spans",
        "provenance",
        "review",
        "edits",
    }
    _require_xml_children(case, expected_children, "case")
    for text_tag in (
        "input",
        "expected_output",
        "description",
        "normalized_template",
    ):
        node = case.find(text_tag)
        assert node is not None
        _require_xml_attributes(node, set(), text_tag)
        _require_xml_leaf(node, text_tag, allow_text=True)
    tags = case.find("tags")
    entity_ids = case.find("entity_ids")
    entity_spans = case.find("entity_spans")
    provenance = case.find("provenance")
    review = case.find("review")
    edits = case.find("edits")
    assert tags is not None
    assert entity_ids is not None
    assert entity_spans is not None
    assert provenance is not None
    assert review is not None
    assert edits is not None
    for container, child_tag, label in (
        (tags, "tag", "tags"),
        (entity_ids, "entity", "entity_ids"),
        (entity_spans, "entity", "entity_spans"),
        (edits, "edit", "edits"),
    ):
        _require_xml_attributes(container, set(), label)
        _require_xml_container_text(container, label)
        if any(child.tag != child_tag for child in container):
            raise ValueError(f"unknown XML node below {label}")
    for tag_node in tags:
        _require_xml_attributes(tag_node, set(), "tag")
        _require_xml_leaf(tag_node, "tag", allow_text=True)
    for entity_id in entity_ids:
        _require_xml_attributes(entity_id, set(), "entity id")
        _require_xml_leaf(entity_id, "entity id", allow_text=True)
    for entity_span in entity_spans:
        _require_xml_attributes(entity_span, set(_ENTITY_SPAN_FIELDS), "entity span")
        _require_xml_leaf(entity_span, "entity span")
    _require_xml_attributes(provenance, set(_PROVENANCE_FIELDS), "provenance")
    _require_xml_leaf(provenance, "provenance")
    _require_xml_attributes(review, set(_REVIEW_FIELDS), "review")
    _require_xml_leaf(review, "review")
    for edit in edits:
        _require_xml_attributes(edit, set(_EDIT_FIELDS), "edit")
        _require_xml_leaf(edit, "edit")


def _require_xml_attributes(node: ET.Element, expected: set[str], label: str) -> None:
    actual = set(node.attrib)
    unknown = actual - expected
    if unknown:
        raise ValueError(f"unknown XML attribute on {label}: {sorted(unknown)[0]}")
    missing = expected - actual
    if missing:
        raise ValueError(
            f"missing required XML attribute on {label}: {sorted(missing)[0]}"
        )


def _require_xml_children(node: ET.Element, expected: set[str], label: str) -> None:
    _require_xml_container_text(node, label)
    actual = [child.tag for child in node]
    unknown = set(actual) - expected
    if unknown:
        raise ValueError(f"unknown XML node below {label}: {sorted(unknown)[0]}")
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError(f"missing or duplicate XML node below {label}")


def _require_xml_leaf(
    node: ET.Element, label: str, *, allow_text: bool = False
) -> None:
    if len(node):
        raise ValueError(f"unknown XML node below {label}")
    if not allow_text and node.text and node.text.strip():
        raise ValueError(f"unexpected XML text in {label}")


def _require_xml_container_text(node: ET.Element, label: str) -> None:
    if node.text and node.text.strip():
        raise ValueError(f"unexpected XML text in {label}")
    if any(child.tail and child.tail.strip() for child in node):
        raise ValueError(f"unexpected XML text in {label}")
