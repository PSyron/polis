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

_POTRZEBOWAC_PATTERN: Final = re.compile(r"Potrzebuję (?P<governed>pomoc)\.\Z")
_POTRZEBOWAC_BEHAVIOR_VERSION: Final = (
    "inflection-government-potrzebowac-pomoc/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_SZUKAC_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<phrase>(?P<governor>Szukam) (?P<governed>klucz))(?!\w)",
    re.IGNORECASE,
)
_SZUKAC_BEHAVIOR_VERSION: Final = (
    "inflection-government-szukac-klucz/1.0+"
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
_SZUKAC_FORM: Final = _GovernedFormProp(
    governor_surface="szukam",
    governor_lemma="szukać",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="klucz",
    governed_lemma="klucz",
    governed_tags=frozenset({"subst:sg:nom.acc:m3"}),
    target_tag="subst:sg:gen:m3",
    target_form="klucza",
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
        match = _POTRZEBOWAC_PATTERN.fullmatch(text)
        if match is None or self._provider is None:
            return ()
        replacement = _governed_form_replacement(self._provider, _POTRZEBOWAC_FORM)
        if replacement != "pomocy":
            return ()
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Niepoprawna forma dopełnienia po czasowniku „potrzebować”.",
                explanation=(
                    "W tej zamkniętej konstrukcji czasownik „Potrzebuję” wymaga formy "
                    "dopełniacza „pomocy”."
                ),
                original=match.group("governed"),
                suggestion=replacement,
                start=match.start("governed"),
                end=match.end("governed"),
                confidence=self._confidence,
                source=self.source,
            ),
        )


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
        return _SZUKAC_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        matches = tuple(
            match
            for match in _SZUKAC_PATTERN.finditer(text)
            if not _is_wrapped_mention(text, match.start("phrase"), match.end("phrase"))
        )
        if (
            not matches
            or self._provider is None
            or _governed_form_replacement(self._provider, _SZUKAC_FORM) != "klucza"
        ):
            return ()

        findings: list[Finding] = []
        for match in matches:
            original = match.group("governed")
            suggestion = _match_case(original, "klucza")
            if suggestion == original:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepoprawna forma dopełnienia po czasowniku „szukać”.",
                    explanation=(
                        "W tej zamkniętej konstrukcji czasownik „Szukam” wymaga formy "
                        "dopełniacza „klucza”."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=match.start("governed"),
                    end=match.end("governed"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


@dataclass(frozen=True, slots=True)
class _Wave4GovernmentSpec:
    source_name: str
    behavior_stem: str
    pattern: re.Pattern[str]
    form: _GovernedFormProp
    message: str
    explanation: str


def _wave4_behavior(stem: str) -> str:
    return f"{stem}/1.0+{_NOTICE}"


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
            rf"(?<!\w)(?P<governor>Idę|idę|IDĘ) (?P<preposition>do|DO) "
            rf"(?P<governed>sklep|Sklep|SKLEP){_TRAIL}{_NP_FINAL}"
        ),
        form=_DO_SKLEP_FORM,
        message="Niepoprawna forma dopełnienia po przyimku „do”.",
        explanation=(
            "W tej zamkniętej konstrukcji po „do” wymagany jest dopełniacz „sklepu”."
        ),
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
        return _wave4_behavior(self._spec.behavior_stem)

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
            start = match.start("governed")
            end = match.end("governed")
            if _is_wrapped_mention(text, match.start(0), match.end(0)):
                continue
            original = match.group("governed")
            if match.groupdict().get("preposition") == "DO" and not (
                match.group("governor").isupper() and original.isupper()
            ):
                continue
            # Title-case guard: morphology cannot replace proper-name / address
            # detection for mid-template capitalized nouns.
            if _is_title_case(original):
                continue
            suggestion = _match_case(original, replacement)
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


class InflectionGovernmentUzywacTelefonRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[1])


class InflectionGovernmentInteresowacSieHistoriaRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[2])


class InflectionGovernmentBycNauczycielRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[3])


class InflectionGovernmentDoSklepRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[4])


class InflectionGovernmentUfacLekarzRule(_Wave4MorphologyGovernmentRule):
    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        super().__init__(provider, _WAVE4_SPECS[5])


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
    except (KeyError, RuntimeError, TypeError, ValueError):
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
