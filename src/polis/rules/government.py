"""Closed, review-only morphology-backed government rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Source,
    SourceKind,
)
from polis.core.models import Severity
from polis.rules._morfeusz import (
    _analyses,
    _forms,
    _has_one_supported_lemma,
    _qualified_identity,
    _QualifiedMorfeusz,
    _tags_for_lemma,
)
from polis.segmentation import (
    _iter_sentence_template_matches as iter_sentence_template_matches,
)

_POTRZEBOWAC_PATTERN: Final = re.compile(
    r"Potrzebuję (?P<governed>pomoc)\.(?![.…\w])\Z"
)
_POTRZEBOWAC_TRAILING_PATTERN: Final = re.compile(
    r"(?<!\w)Potrzebuję (?P<governed>pomoc)(?=[ \t]+[^\W\d_]+)"
)
_POTRZEBOWAC_BEHAVIOR_VERSION: Final = (
    "inflection-government-potrzebowac-pomoc/2.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)
_CLOSING_QUOTES: Final = frozenset({'"', "”", "»", "'", "`"})


@dataclass(frozen=True, slots=True)
class _GovernedFormProp:
    governor_surface: str
    governor_lemma: str
    governor_tags: frozenset[str]
    governed_surface: str
    governed_lemma: str
    governed_tags: frozenset[str]
    target_tag: str
    target_form: str


_POTRZEBOWAC_FORM: Final = _GovernedFormProp(
    governor_surface="Potrzebuję",
    governor_lemma="potrzebować",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="pomoc",
    governed_lemma="pomoc",
    governed_tags=frozenset({"subst:sg:nom:f", "subst:sg:acc:f"}),
    target_tag="subst:sg:gen:f",
    target_form="pomocy",
)
_GOVERNED_FORMS: Final = (_POTRZEBOWAC_FORM,)

# Wave 4 (#342): closed morphology-backed government forms.
# NP-final set is only {. ! ?} or end-of-text; never , ; : (coordination).
# Trailing (?!\.\w) blocks filename/domain after the governed token.
# Title-case governed nouns abstain (proper-name / address guard).
_NOTICE: Final = (
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_NP_FINAL: Final = r"(?:(?P<end>[.!?])|\Z)"
_TRAIL: Final = r"(?!\w)(?!\.\w)"


class InflectionGovernmentPotrzebowacPomocRule:
    """Review the one qualified `Potrzebuję pomoc.` government mismatch."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(
            SourceKind.RULE,
            "inflection.government_potrzebowac_pomoc",
        )
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return _POTRZEBOWAC_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        matches: list[re.Match[str]] = []
        match = _POTRZEBOWAC_PATTERN.fullmatch(text)
        if match is not None:
            matches.append(match)
        if self._provider is not None:
            for _sentence, trailing_match in iter_sentence_template_matches(
                text, _POTRZEBOWAC_TRAILING_PATTERN
            ):
                if not _is_followed_by_nominal_group(
                    text,
                    trailing_match.end("governed"),
                    self._provider,
                ):
                    matches.append(trailing_match)
        if not matches or self._provider is None:
            return ()
        replacement = _governed_form_replacement(self._provider, _POTRZEBOWAC_FORM)
        if replacement != "pomocy":
            return ()
        findings: list[Finding] = []
        for match in sorted(matches, key=re.Match.start):
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message=(
                        "Niepoprawna forma dopełnienia po czasowniku „potrzebować”."
                    ),
                    explanation=(
                        "W tej zamkniętej konstrukcji czasownik „Potrzebuję” wymaga "
                        "formy dopełniacza „pomocy”."
                    ),
                    original=match.group("governed"),
                    suggestion=replacement,
                    start=match.start("governed"),
                    end=match.end("governed"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class InflectionGovernmentSzukacKluczRule:
    """Review the closed `Szukam klucz` government mismatch."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(
            SourceKind.RULE,
            "inflection.government_szukac_klucz",
        )
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return _wave4_behavior("inflection-government-szukac-klucz", 4)

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return _GeneralizedGovernmentRule(self._provider, _GENERALIZED_SPECS[0]).find(
            text, options=options
        )


@dataclass(frozen=True, slots=True)
class _Wave4GovernmentSpec:
    source_name: str
    behavior_stem: str
    pattern: re.Pattern[str]
    form: _GovernedFormProp
    message: str
    explanation: str
    behavior_major: int = 1


def _wave4_behavior(stem: str, major: int = 1) -> str:
    return f"{stem}/{major}.0+{_NOTICE}"


_SLUCHAC_FORM: Final = _GovernedFormProp(
    governor_surface="słucham",
    governor_lemma="słuchać",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="radio",
    governed_lemma="radio",
    governed_tags=frozenset({"subst:sg:nom.acc.voc:n:ncol"}),
    target_tag="subst:sg:gen:n:ncol",
    target_form="radia",
)
_UZYWAC_FORM: Final = _GovernedFormProp(
    governor_surface="używam",
    governor_lemma="używać",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="telefon",
    governed_lemma="telefon",
    governed_tags=frozenset({"subst:sg:nom.acc:m3"}),
    target_tag="subst:sg:gen:m3",
    target_form="telefonu",
)
_INTERESOWAC_FORM: Final = _GovernedFormProp(
    governor_surface="interesuję",
    governor_lemma="interesować",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="historia",
    governed_lemma="historia",
    governed_tags=frozenset({"subst:sg:nom:f"}),
    target_tag="subst:sg:inst:f",
    target_form="historią",
)
_BYC_FORM: Final = _GovernedFormProp(
    governor_surface="jestem",
    governor_lemma="być",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="nauczyciel",
    governed_lemma="nauczyciel",
    governed_tags=frozenset({"subst:sg:nom:m1"}),
    target_tag="subst:sg:inst:m1",
    target_form="nauczycielem",
)
_DO_SKLEP_FORM: Final = _GovernedFormProp(
    governor_surface="idę",
    governor_lemma="iść",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="sklep",
    governed_lemma="sklep",
    governed_tags=frozenset({"subst:sg:nom.acc:m3"}),
    target_tag="subst:sg:gen:m3",
    target_form="sklepu",
)
_UFAC_FORM: Final = _GovernedFormProp(
    governor_surface="ufam",
    governor_lemma="ufać",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="lekarz",
    governed_lemma="lekarz",
    governed_tags=frozenset({"subst:sg:nom:m1"}),
    target_tag="subst:sg:dat:m1",
    target_form="lekarzowi",
)
# Documented abstention: never build dative slices on nouns with a plausible
# address reading beyond this closed `lekarz` template (qualification #342).
_LUBIC_FORM: Final = _GovernedFormProp(
    governor_surface="lubię",
    governor_lemma="lubić",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="kawę",
    governed_lemma="kawa",
    governed_tags=frozenset({"subst:sg:acc:f"}),
    target_tag="subst:sg:gen:f",
    target_form="kawy",
)

_WAVE4_SPECS: Final = (
    _Wave4GovernmentSpec(
        source_name="inflection.government_sluchac_radio",
        behavior_stem="inflection-government-sluchac-radio",
        pattern=re.compile(
            rf"(?<!\w)(?P<governor>Słucham|słucham|SŁUCHAM) "
            rf"(?P<governed>radio|Radio|RADIO){_TRAIL}{_NP_FINAL}"
        ),
        form=_SLUCHAC_FORM,
        message="Niepoprawna forma dopełnienia po czasowniku „słuchać”.",
        explanation=(
            "W tej zamkniętej konstrukcji czasownik „Słucham” wymaga formy "
            "dopełniacza „radia”."
        ),
    ),
    _Wave4GovernmentSpec(
        source_name="inflection.government_uzywac_telefon",
        behavior_stem="inflection-government-uzywac-telefon",
        pattern=re.compile(
            rf"(?<!\w)(?P<governor>Używam|używam|UŻYWAM) "
            rf"(?P<governed>telefon|Telefon|TELEFON){_TRAIL}{_NP_FINAL}"
        ),
        form=_UZYWAC_FORM,
        message="Niepoprawna forma dopełnienia po czasowniku „używać”.",
        explanation=(
            "W tej zamkniętej konstrukcji czasownik „Używam” wymaga formy "
            "dopełniacza „telefonu”."
        ),
    ),
    _Wave4GovernmentSpec(
        source_name="inflection.government_interesowac_sie_historia",
        behavior_stem="inflection-government-interesowac-sie-historia",
        pattern=re.compile(
            rf"(?<!\w)(?P<governor>Interesuję|interesuję|INTERESUJĘ) się "
            rf"(?P<governed>historia|Historia|HISTORIA){_TRAIL}{_NP_FINAL}"
        ),
        form=_INTERESOWAC_FORM,
        message="Niepoprawna forma dopełnienia po „interesować się”.",
        explanation=(
            "W tej zamkniętej konstrukcji „interesować się” wymaga narzędnika "
            "„historią”."
        ),
    ),
    _Wave4GovernmentSpec(
        source_name="inflection.government_byc_nauczyciel",
        behavior_stem="inflection-government-byc-nauczyciel",
        pattern=re.compile(
            rf"(?<!\w)(?P<governor>Jestem|jestem|JESTEM) "
            rf"(?P<governed>nauczyciel|Nauczyciel|NAUCZYCIEL){_TRAIL}{_NP_FINAL}"
        ),
        form=_BYC_FORM,
        message="Niepoprawna forma orzecznika po „być”.",
        explanation=(
            "W tej zamkniętej konstrukcji „Jestem” wymaga narzędnika „nauczycielem”."
        ),
    ),
    _Wave4GovernmentSpec(
        source_name="inflection.government_do_sklep",
        behavior_stem="inflection-government-do-sklep",
        pattern=re.compile(
            rf"(?<!\w)(?:(?P<governor>Idę|idę|IDĘ) do "
            rf"(?P<governed>sklep|Sklep|SKLEP)|"
            rf"(?P<upper_governor>IDĘ) DO (?P<upper_governed>SKLEP))"
            rf"{_TRAIL}{_NP_FINAL}"
        ),
        form=_DO_SKLEP_FORM,
        message="Niepoprawna forma dopełnienia po przyimku „do”.",
        explanation=(
            "W tej zamkniętej konstrukcji po „do” wymagany jest dopełniacz „sklepu”."
        ),
        behavior_major=2,
    ),
    _Wave4GovernmentSpec(
        source_name="inflection.government_ufac_lekarz",
        behavior_stem="inflection-government-ufac-lekarz",
        pattern=re.compile(
            rf"(?<!\w)(?P<governor>Ufam|ufam|UFAM) "
            rf"(?P<governed>lekarz|Lekarz|LEKARZ){_TRAIL}{_NP_FINAL}"
        ),
        form=_UFAC_FORM,
        message="Niepoprawna forma dopełnienia po czasowniku „ufać”.",
        explanation=(
            "W tej zamkniętej konstrukcji „Ufam” wymaga celownika „lekarzowi”."
        ),
    ),
    _Wave4GovernmentSpec(
        source_name="inflection.negated_lubic_kawe",
        behavior_stem="inflection-negated-lubic-kawe",
        pattern=re.compile(
            rf"(?<!\w)(?P<neg>Nie|nie|NIE) (?P<governor>lubię|Lubię|LUBIĘ) "
            rf"(?P<governed>kawę|Kawę|KAWĘ){_TRAIL}{_NP_FINAL}"
        ),
        form=_LUBIC_FORM,
        message="Niepoprawna forma dopełnienia po zaprzeczonym „lubić”.",
        explanation=(
            "W tej zamkniętej konstrukcji zaprzeczone „lubić” wymaga "
            "dopełniacza „kawy”."
        ),
    ),
)

_GOVERNMENT_WORD: Final = r"[^\W\d_]+"
_GOVERNMENT_NOUN: Final = r"(?!(?:i|oraz|albo|lub|ani)\b)[^\W\d_]+"
_GOVERNMENT_TARGET: Final = (
    r"(?:(?P<terminator>\.(?![.\u2026\w])|[!?](?![.!?\u2026\w])|"
    r",(?=[ \t]+)|(?=[ \t]+(?:i|oraz|albo|lub|ani)\b)|\Z)"
    r"|(?P<material>(?![ \t]+(?:i|oraz|albo|lub|ani)\b)"
    r"(?=[ \t]+[^\W\d_]+)))"
)
_GOVERNMENT_GOVERNOR_TAGS: Final = frozenset({"fin:sg:pri:imperf"})
_NOMINAL_COORDINATION_PREFIXES: Final = frozenset(
    {
        "adj",
        "adja",
        "adjc",
        "adjp",
        "depr",
        "num",
        "numcol",
        "ppas",
        "ppron12",
        "ppron3",
        "subst",
        "winien",
    }
)


@dataclass(frozen=True, slots=True)
class _GeneralizedGovernmentSpec:
    source_name: str
    behavior_stem: str
    pattern: re.Pattern[str]
    governor_lemma: str
    governor_tags: frozenset[str]
    governor_label: str
    target_case: str
    target_case_label: str


def _generalized_pattern(prefix: str, suffix: str = "") -> re.Pattern[str]:
    return re.compile(
        rf"(?<!\w)(?P<governor>{prefix}){suffix}[ \t]+"
        rf"(?P<complement>(?:(?P<adjective>{_GOVERNMENT_WORD})[ \t]+)?"
        rf"(?P<noun>{_GOVERNMENT_NOUN}))"
        rf"{_GOVERNMENT_TARGET}",
        re.IGNORECASE,
    )


_GENERALIZED_SPECS: Final = (
    _GeneralizedGovernmentSpec(
        source_name="inflection.government_szukac_klucz",
        behavior_stem="inflection-government-szukac-klucz",
        pattern=_generalized_pattern("szukam"),
        governor_lemma="szukać",
        governor_tags=_GOVERNMENT_GOVERNOR_TAGS,
        governor_label="„szukać”",
        target_case="gen",
        target_case_label="dopełniacza",
    ),
    _GeneralizedGovernmentSpec(
        source_name="inflection.government_uzywac_telefon",
        behavior_stem="inflection-government-uzywac-telefon",
        pattern=_generalized_pattern("używam"),
        governor_lemma="używać",
        governor_tags=_GOVERNMENT_GOVERNOR_TAGS,
        governor_label="„używać”",
        target_case="gen",
        target_case_label="dopełniacza",
    ),
    _GeneralizedGovernmentSpec(
        source_name="inflection.government_ufac_lekarz",
        behavior_stem="inflection-government-ufac-lekarz",
        pattern=_generalized_pattern("ufam"),
        governor_lemma="ufać",
        governor_tags=_GOVERNMENT_GOVERNOR_TAGS,
        governor_label="„ufać”",
        target_case="dat",
        target_case_label="celownika",
    ),
    _GeneralizedGovernmentSpec(
        source_name="inflection.government_interesowac_sie_historia",
        behavior_stem="inflection-government-interesowac-sie-historia",
        pattern=_generalized_pattern("interesuję", r"[ \t]+się"),
        governor_lemma="interesować",
        governor_tags=_GOVERNMENT_GOVERNOR_TAGS,
        governor_label="„interesować się”",
        target_case="inst",
        target_case_label="narzędnika",
    ),
    _GeneralizedGovernmentSpec(
        source_name="inflection.government_do_sklep",
        behavior_stem="inflection-government-do-sklep",
        pattern=_generalized_pattern("do"),
        governor_lemma="do:P",
        governor_tags=frozenset({"prep:gen"}),
        governor_label="przyimku „do”",
        target_case="gen",
        target_case_label="dopełniacza",
    ),
)


class _GeneralizedGovernmentRule:
    _CATEGORY = Category.INFLECTION

    def __init__(
        self, provider: _QualifiedMorfeusz | None, spec: _GeneralizedGovernmentSpec
    ) -> None:
        self.source = Source(SourceKind.RULE, spec.source_name)
        self._provider = provider
        self._spec = spec
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return _wave4_behavior(self._spec.behavior_stem, 4)

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if self._provider is None:
            return ()
        findings: list[Finding] = []
        for match in self._spec.pattern.finditer(text):
            adjective = match.group("adjective")
            noun = match.group("noun")
            noun_start = match.start("noun")
            noun_end = match.end("noun")
            has_trailing_material = match.group("material") is not None
            if adjective is not None:
                candidate = self._provider.government_nominal_group_replacement(
                    match.group("governor"),
                    adjective,
                    noun,
                    governor_lemma=self._spec.governor_lemma,
                    governor_tags=self._spec.governor_tags,
                    target_case=self._spec.target_case,
                )
                if candidate is None:
                    noun = adjective
                    adjective = None
                    noun_start = match.start("adjective")
                    noun_end = match.end("adjective")
                    has_trailing_material = True
            legacy_szukac_klucz = (
                self._spec.source_name == "inflection.government_szukac_klucz"
                and adjective is None
                and noun.casefold() == "klucz"
                and not _is_followed_by_nominal_group(
                    text, noun_end, self._provider, comma=True
                )
            )
            if has_trailing_material and _is_followed_by_nominal_group(
                text, noun_end, self._provider
            ):
                continue
            if match.group("terminator") == "," and not legacy_szukac_klucz:
                continue
            if not legacy_szukac_klucz and (
                _is_quoted_position(text, match.start("governor"))
                or _is_wrapped_mention(text, match.start(0), match.end(0))
                or _is_after_coordinator(text, match.start("governor"))
                or _is_before_coordinator(text, noun_end)
                or (
                    self._spec.source_name == "inflection.government_do_sklep"
                    and _is_initial_do_case_boundary(text, match)
                )
            ):
                continue
            if _is_title_case(noun):
                continue
            replacement = self._provider.government_nominal_group_replacement(
                match.group("governor"),
                adjective,
                noun,
                governor_lemma=self._spec.governor_lemma,
                governor_tags=self._spec.governor_tags,
                target_case=self._spec.target_case,
            )
            if replacement is None:
                continue
            replacement_adjective, replacement_noun = replacement
            target_adjective = (
                _match_case(adjective, replacement_adjective)
                if adjective is not None and replacement_adjective is not None
                else None
            )
            target_noun = _match_case(noun, replacement_noun)
            adjective_changed = adjective is not None and target_adjective != adjective
            noun_changed = target_noun != noun
            if not adjective_changed and not noun_changed:
                continue
            if adjective_changed and noun_changed:
                assert target_adjective is not None
                start = match.start("complement")
                end = match.end("complement")
                original = match.group("complement")
                suggestion = f"{target_adjective} {target_noun}"
            elif adjective_changed:
                assert target_adjective is not None
                start = match.start("adjective")
                end = match.end("adjective")
                original = adjective
                suggestion = target_adjective
            else:
                start = noun_start
                end = noun_end
                original = noun
                suggestion = target_noun
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message=(
                        "Niepoprawna forma grupy nominalnej po "
                        f"{self._spec.governor_label}."
                    ),
                    explanation=(
                        "W tej zamkniętej konstrukcji wymagany jest "
                        f"{self._spec.target_case_label} dla jednoznacznego "
                        "dopełnienia."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=start,
                    end=end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class _Wave4MorphologyGovernmentRule:
    """Shared closed morphology-backed government consumer for Wave 4."""

    _CATEGORY = Category.INFLECTION

    def __init__(
        self, provider: _QualifiedMorfeusz | None, spec: _Wave4GovernmentSpec
    ) -> None:
        self.source = Source(SourceKind.RULE, spec.source_name)
        self._provider = provider
        self._spec = spec
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return _wave4_behavior(
            self._spec.behavior_stem,
            self._spec.behavior_major,
        )

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if self._provider is None:
            return ()
        # Pattern-first: avoid morphology work when the closed surface is absent.
        matches = tuple(self._spec.pattern.finditer(text))
        if not matches:
            return ()
        confirmed = _governed_form_replacement(self._provider, self._spec.form)
        if confirmed != self._spec.form.target_form:
            return ()
        replacement = confirmed
        findings: list[Finding] = []
        for match in matches:
            upper_branch = match.groupdict().get("upper_governed") is not None
            governed_group = "upper_governed" if upper_branch else "governed"
            start = match.start(governed_group)
            end = match.end(governed_group)
            if _is_wrapped_mention(text, match.start(0), match.end(0)):
                continue
            original = match.group(governed_group)
            # Title-case guard: morphology cannot replace proper-name / address
            # detection for mid-template capitalized nouns.
            if _is_title_case(original):
                continue
            suggestion = (
                replacement.upper()
                if upper_branch
                else _match_case(original, replacement)
            )
            if suggestion == original:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message=self._spec.message,
                    explanation=self._spec.explanation,
                    original=original,
                    suggestion=suggestion,
                    start=start,
                    end=end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class InflectionGovernmentSluchacRadioRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[0])


class InflectionGovernmentUzywacTelefonRule(_GeneralizedGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _GENERALIZED_SPECS[1])


class InflectionGovernmentInteresowacSieHistoriaRule(_GeneralizedGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _GENERALIZED_SPECS[3])


class InflectionGovernmentBycNauczycielRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[3])


class InflectionGovernmentDoSklepRule(_GeneralizedGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _GENERALIZED_SPECS[4])


class InflectionGovernmentUfacLekarzRule(_GeneralizedGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _GENERALIZED_SPECS[2])


class InflectionNegatedLubicKaweRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[6])


def _is_title_case(token: str) -> bool:
    return len(token) >= 2 and token[0].isupper() and token[1:].islower()


# Process-local cache of closed-form morphology qualifications. Keyed by
# provider identity, backend object id, and the exact surface/lemma/tag
# contract so identity drift still fails closed.
_GOVERNED_FORM_CACHE: dict[
    tuple[
        str,
        str,
        str,
        int,
        str,
        str,
        frozenset[str],
        str,
        str,
        frozenset[str],
        str,
        str,
    ],
    str | None,
] = {}


def _governed_form_replacement(
    provider: _QualifiedMorfeusz, row: _GovernedFormProp
) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    cache_key = (
        provider.identity.package_version,
        provider.identity.dictionary_id,
        provider.identity.dictionary_notice_sha256,
        id(provider.backend),
        row.governor_surface,
        row.governor_lemma,
        row.governor_tags,
        row.governed_surface,
        row.governed_lemma,
        row.governed_tags,
        row.target_tag,
        row.target_form,
    )
    if cache_key in _GOVERNED_FORM_CACHE:
        return _GOVERNED_FORM_CACHE[cache_key]
    try:
        governor_analyses = _analyses(
            provider.backend.analyse(row.governor_surface),
            row.governor_surface,
        )
        governed_analyses = _analyses(
            provider.backend.analyse(row.governed_surface),
            row.governed_surface,
        )
        target_forms = _forms(
            provider.backend.generate(row.governed_lemma),
            lemma=row.governed_lemma,
            target_tag=row.target_tag,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        _GOVERNED_FORM_CACHE[cache_key] = None
        return None
    if (
        not _has_one_supported_lemma(
            governor_analyses,
            lemma=row.governor_lemma,
            source_tags=row.governor_tags,
        )
        or not _has_one_supported_lemma(
            governed_analyses,
            lemma=row.governed_lemma,
            source_tags=row.governed_tags,
        )
        or _tags_for_lemma(governor_analyses, row.governor_lemma) != row.governor_tags
        or _tags_for_lemma(governed_analyses, row.governed_lemma) != row.governed_tags
        or target_forms != {row.target_form}
    ):
        _GOVERNED_FORM_CACHE[cache_key] = None
        return None
    _GOVERNED_FORM_CACHE[cache_key] = row.target_form
    return row.target_form


def _match_case(reference: str, replacement: str) -> str:
    if reference.isupper():
        return replacement.upper()
    if reference[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _is_wrapped_mention(text: str, start: int, end: int) -> bool:
    if start <= 0 or end > len(text):
        return False
    if end < len(text):
        left = text[start - 1]
        right = text[end]
        if (left, right) in _MENTION_WRAPPERS:
            return True
        if left == "`":
            rest = text[end:]
            if rest.startswith("`") or rest.startswith("()`"):
                return True
        if right in _CLOSING_QUOTES:
            return True
    return False


def _is_quoted_position(text: str, position: int) -> bool:
    for opening, closing in (
        ('"', '"'),
        ("'", "'"),
        ("`", "`"),
        ("„", "”"),
        ("“", "”"),
        ("«", "»"),
    ):
        before = text[:position]
        if opening == closing:
            if before.count(opening) % 2 == 1:
                return True
        elif before.rfind(opening) > before.rfind(closing):
            return True
    return False


def _is_after_coordinator(text: str, position: int) -> bool:
    sentence = re.split(r"[.!?]", text[:position])[-1]
    return (
        re.search(
            r"(?:^|[ \t])(?:i|oraz|albo|lub|ani)"
            r"(?:[ \t]+(?:znów|znowu))?[ \t]+$",
            sentence,
            re.IGNORECASE,
        )
        is not None
    )


def _is_before_coordinator(text: str, position: int) -> bool:
    suffix = text[position:]
    match = re.match(
        r"[ \t]+(?:i|oraz|albo|lub|ani)\b[ \t]+(?P<next>[^\W\d_]+)",
        suffix,
        re.IGNORECASE,
    )
    if match is None:
        return False
    return True


def _is_followed_by_nominal_group(
    text: str,
    position: int,
    provider: _QualifiedMorfeusz,
    *,
    comma: bool = False,
) -> bool:
    separator = r",[ \t]+" if comma else r"[ \t]+"
    match = re.match(
        rf"{separator}(?P<next>[^\W\d_]+)",
        text[position:],
        re.IGNORECASE,
    )
    if match is None:
        return False
    next_token = match.group("next")
    if next_token.casefold() in {"i", "oraz", "albo", "lub", "ani"}:
        return True
    try:
        analyses = _analyses(
            provider.backend.analyse(next_token),
            next_token,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return True
    if not analyses:
        return True
    prefixes = {tag.partition(":")[0] for _lemma, tag in analyses}
    if "prep" in prefixes:
        if not prefixes & _NOMINAL_COORDINATION_PREFIXES:
            return False
        return (
            re.match(
                r"[ \t]+[^\W\d_]+",
                text[position + match.end("next") :],
            )
            is None
        )
    return bool(prefixes & _NOMINAL_COORDINATION_PREFIXES)


def _is_initial_do_case_boundary(text: str, match: re.Match[str]) -> bool:
    sentence = re.split(r"[.!?]", text[: match.start("governor")])[-1].strip()
    return sentence.casefold() == "idę" and match.group("governor") != "do"


__all__ = [
    "InflectionGovernmentBycNauczycielRule",
    "InflectionGovernmentDoSklepRule",
    "InflectionGovernmentInteresowacSieHistoriaRule",
    "InflectionGovernmentPotrzebowacPomocRule",
    "InflectionGovernmentSluchacRadioRule",
    "InflectionGovernmentSzukacKluczRule",
    "InflectionGovernmentUfacLekarzRule",
    "InflectionGovernmentUzywacTelefonRule",
    "InflectionNegatedLubicKaweRule",
]
