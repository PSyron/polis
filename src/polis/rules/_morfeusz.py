"""Private qualified Morfeusz2 adapter for current closed consumers."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Protocol, runtime_checkable

type _AnalysisRow = tuple[object, ...]
type _GenerationRow = tuple[object, ...]

_PACKAGE_VERSION: Final = "1.99.15"
_DICTIONARY_ID: Final = "pl.sgjp.sgjp-2026.06.01"
_NOTICE_SHA256: Final = (
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_NEGATED_ADJECTIVE_LEMMA: Final = "czerwony:A"
_NEGATED_NOUN_LEMMA: Final = "samochód"
_NEGATED_ADJECTIVE_SOURCE_TAGS: Final = frozenset(
    {
        "adj:sg:acc:m3:pos",
        "adj:sg:nom.voc:m1.m2.m3:pos",
    }
)
_NEGATED_NOUN_SOURCE_TAGS: Final = frozenset({"subst:sg:nom.acc:m3"})
_NEGATED_ADJECTIVE_TARGET_TAG: Final = "adj:sg:gen:m1.m2.m3.n:pos"
_NEGATED_NOUN_TARGET_TAG: Final = "subst:sg:gen:m3"
_DEMONSTRATIVE_LEMMA: Final = "ten"
_DEMONSTRATIVE_SOURCE_TAGS: Final = frozenset(
    {
        "adj:pl:acc:m2.m3.f.n:pos",
        "adj:pl:nom.voc:m2.m3.f.n:pos",
    }
)
_ADJECTIVE_LEMMA: Final = "duży"
_ADJECTIVE_SOURCE_TAGS: Final = frozenset(
    {
        "adj:pl:acc:m2.m3.f.n:pos",
        "adj:pl:nom.voc:m2.m3.f.n:pos",
        "adj:sg:acc:n:pos",
        "adj:sg:nom.voc:n:pos",
    }
)
_NOMINAL_HEAD_LEMMA: Final = "okno"
_NOMINAL_HEAD_SOURCE_TAGS: Final = frozenset({"subst:sg:nom.acc.voc:n:ncol"})
_DEMONSTRATIVE_TARGET_TAG: Final = "adj:sg:nom.voc:n:pos"
_TA_DEMONSTRATIVE_LEMMA: Final = "ten"
_TA_DEMONSTRATIVE_SOURCE_TAGS: Final = frozenset({"adj:sg:nom.voc:f:pos"})
_TA_ADJECTIVE_LEMMA: Final = "nowy:A"
_TA_ADJECTIVE_SOURCE_TAGS: Final = frozenset(
    {
        "adj:sg:acc:m3:pos",
        "adj:sg:nom.voc:m1.m2.m3:pos",
    }
)
_TA_NOMINAL_HEAD_LEMMA: Final = "książka"
_TA_NOMINAL_HEAD_SOURCE_TAGS: Final = frozenset({"subst:sg:nom:f"})
_TA_ADJECTIVE_TARGET_TAG: Final = "adj:sg:nom.voc:f:pos"
_PRZYGLADAC_GOVERNOR_LEMMA: Final = "przyglądać"
_PRZYGLADAC_GOVERNOR_TAGS: Final = frozenset({"fin:sg:pri:imperf"})
_PRZYGLADAC_ADJECTIVE_LEMMA: Final = "nowy:A"
_PRZYGLADAC_ADJECTIVE_SOURCE_TAGS: Final = frozenset(
    {
        "adj:sg:acc:m3:pos",
        "adj:sg:nom.voc:m1.m2.m3:pos",
    }
)
_PRZYGLADAC_NOUN_LEMMA: Final = "budynek"
_PRZYGLADAC_NOUN_SOURCE_TAGS: Final = frozenset({"subst:sg:nom.acc:m3"})
_PRZYGLADAC_ADJECTIVE_TARGET_TAG: Final = "adj:sg:dat:m1.m2.m3.n:pos"
_PRZYGLADAC_NOUN_TARGET_TAG: Final = "subst:sg:dat:m3"
_NON_ADJECTIVE_LEMMAS: Final = frozenset(
    {"jaki", "który", "mój", "nasz", "taki", "ten", "twój", "wasz", "żaden"}
)
_GOVERNMENT_PRONOUN_LEMMAS: Final = frozenset(
    {"mój", "mój:A", "nasz", "swój", "ten", "twój", "twój:A", "wasz"}
)
_GOVERNMENT_PRONOUN_QUALIFIED_AMBIGUITY: Final = (
    "program",
    "sg",
    "gen",
    "m3",
    "programu",
)
_VERB_TAG_PREFIXES: Final = frozenset(
    {"fin", "ger", "impt", "imps", "inf", "pant", "pcon", "praet"}
)
_COMPETING_NOMINAL_TAG_PREFIXES: Final = frozenset(
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
        "winien",
    }
)
_KNOWN_TAG_PREFIXES: Final = frozenset(
    {
        "adj",
        "adja",
        "adjc",
        "adjp",
        "adv",
        "brev",
        "burk",
        "comp",
        "conj",
        "depr",
        "fin",
        "ger",
        "ign",
        "imps",
        "impt",
        "inf",
        "interj",
        "num",
        "numcol",
        "pant",
        "part",
        "pcon",
        "ppron12",
        "ppron3",
        "ppas",
        "praet",
        "pred",
        "prep",
        "qub",
        "subst",
        "winien",
    }
)
_KNOWN_NOUN_TAG_SUFFIXES: Final = frozenset({"col", "ncol"})
_GOVERNMENT_CASES: Final = frozenset({"gen", "dat", "inst"})

type _AgreementFeature = tuple[str, str, str]


class _QualifiedMorfeuszBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


@dataclass(frozen=True, slots=True)
class _CanonicalMorfeuszBackend:
    backend: _QualifiedMorfeuszBackend
    normalize_exact_duplicates: bool = False

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        rows = self.backend.analyse(text)
        return (
            _deduplicate_provider_rows(rows)
            if self.normalize_exact_duplicates
            else rows
        )

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        rows = self.backend.generate(lemma)
        return (
            _deduplicate_provider_rows(rows)
            if self.normalize_exact_duplicates
            else rows
        )


@runtime_checkable
class _IdentityBackend(_QualifiedMorfeuszBackend, Protocol):
    def dict_id(self) -> str: ...

    def dict_copyright(self) -> str: ...


@runtime_checkable
class _MorfeuszModule(Protocol):
    Morfeusz: Callable[[], _IdentityBackend]


@dataclass(frozen=True, slots=True)
class _ProviderIdentity:
    package_version: str
    dictionary_id: str
    dictionary_notice_sha256: str


_OBSERVED_PROVIDER_IDENTITY: ContextVar[_ProviderIdentity | None] = ContextVar(
    "polis_observed_morfeusz_identity",
    default=None,
)


@dataclass(frozen=True, slots=True)
class _ParsedAnalysis:
    lemma: str
    tag: str
    labels: tuple[str, ...]
    qualifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _QualifiedMorfeusz:
    backend: _QualifiedMorfeuszBackend
    identity: _ProviderIdentity

    @lru_cache(maxsize=64)  # noqa: B019 - bounded provider lifecycle cache
    def negated_widziec_nominal_group_replacement(
        self, adjective: str, noun: str
    ) -> str | None:
        if self.identity != _qualified_identity():
            return None
        try:
            adjective_analyses = _analyses(self.backend.analyse(adjective), adjective)
            noun_analyses = _analyses(self.backend.analyse(noun), noun)
            adjective_forms = _forms(
                self.backend.generate(_NEGATED_ADJECTIVE_LEMMA),
                lemma=_NEGATED_ADJECTIVE_LEMMA,
                target_tag=_NEGATED_ADJECTIVE_TARGET_TAG,
            )
            noun_forms = _forms(
                self.backend.generate(_NEGATED_NOUN_LEMMA),
                lemma=_NEGATED_NOUN_LEMMA,
                target_tag=_NEGATED_NOUN_TARGET_TAG,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None
        if (
            not _has_one_supported_lemma(
                adjective_analyses,
                lemma=_NEGATED_ADJECTIVE_LEMMA,
                source_tags=_NEGATED_ADJECTIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                noun_analyses,
                lemma=_NEGATED_NOUN_LEMMA,
                source_tags=_NEGATED_NOUN_SOURCE_TAGS,
            )
            or adjective_forms != {"czerwonego"}
            or noun_forms != {"samochodu"}
        ):
            return None
        return "czerwonego samochodu"

    @lru_cache(maxsize=8)  # noqa: B019 - bounded provider lifecycle cache
    def nominal_group_te_duze_okno_replacement(self) -> str | None:
        if self.identity != _qualified_identity():
            return None
        try:
            demonstrative_analyses = _analyses(self.backend.analyse("Te"), "Te")
            adjective_analyses = _analyses(self.backend.analyse("duże"), "duże")
            nominal_head_analyses = _analyses(self.backend.analyse("okno"), "okno")
            demonstrative_forms = _forms(
                self.backend.generate(_DEMONSTRATIVE_LEMMA),
                lemma=_DEMONSTRATIVE_LEMMA,
                target_tag=_DEMONSTRATIVE_TARGET_TAG,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None
        if (
            not _has_one_supported_lemma(
                demonstrative_analyses,
                lemma=_DEMONSTRATIVE_LEMMA,
                source_tags=_DEMONSTRATIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                adjective_analyses,
                lemma=_ADJECTIVE_LEMMA,
                source_tags=_ADJECTIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                nominal_head_analyses,
                lemma=_NOMINAL_HEAD_LEMMA,
                source_tags=_NOMINAL_HEAD_SOURCE_TAGS,
            )
            or _tags_for_lemma(demonstrative_analyses, _DEMONSTRATIVE_LEMMA)
            != _DEMONSTRATIVE_SOURCE_TAGS
            or _tags_for_lemma(adjective_analyses, _ADJECTIVE_LEMMA)
            != _ADJECTIVE_SOURCE_TAGS
            or _tags_for_lemma(nominal_head_analyses, _NOMINAL_HEAD_LEMMA)
            != _NOMINAL_HEAD_SOURCE_TAGS
            or demonstrative_forms != {"to"}
        ):
            return None
        return "To"

    @lru_cache(maxsize=8)  # noqa: B019 - bounded provider lifecycle cache
    def nominal_group_ta_nowy_ksiazka_replacement(self) -> str | None:
        if self.identity != _qualified_identity():
            return None
        try:
            demonstrative_analyses = _analyses(self.backend.analyse("Ta"), "Ta")
            adjective_analyses = _analyses(self.backend.analyse("nowy"), "nowy")
            nominal_head_analyses = _analyses(
                self.backend.analyse("książka"), "książka"
            )
            adjective_forms = _forms(
                self.backend.generate(_TA_ADJECTIVE_LEMMA),
                lemma=_TA_ADJECTIVE_LEMMA,
                target_tag=_TA_ADJECTIVE_TARGET_TAG,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None
        if (
            not _has_one_supported_lemma(
                demonstrative_analyses,
                lemma=_TA_DEMONSTRATIVE_LEMMA,
                source_tags=_TA_DEMONSTRATIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                adjective_analyses,
                lemma=_TA_ADJECTIVE_LEMMA,
                source_tags=_TA_ADJECTIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                nominal_head_analyses,
                lemma=_TA_NOMINAL_HEAD_LEMMA,
                source_tags=_TA_NOMINAL_HEAD_SOURCE_TAGS,
            )
            or _tags_for_lemma(demonstrative_analyses, _TA_DEMONSTRATIVE_LEMMA)
            != _TA_DEMONSTRATIVE_SOURCE_TAGS
            or _tags_for_lemma(adjective_analyses, _TA_ADJECTIVE_LEMMA)
            != _TA_ADJECTIVE_SOURCE_TAGS
            or _tags_for_lemma(nominal_head_analyses, _TA_NOMINAL_HEAD_LEMMA)
            != _TA_NOMINAL_HEAD_SOURCE_TAGS
            or adjective_forms != {"nowa"}
        ):
            return None
        return "nowa"

    @lru_cache(maxsize=64)  # noqa: B019 - bounded provider lifecycle cache
    def nominal_group_agreement_replacement(
        self, adjective: str, noun: str, demonstrative: str | None = None
    ) -> str | None:
        if self.identity != _qualified_identity():
            return None
        adjective_input = adjective.casefold() if adjective.isupper() else adjective
        noun_input = noun.casefold() if noun.isupper() else noun
        demonstrative_input = (
            demonstrative.casefold()
            if demonstrative is not None and demonstrative.isupper()
            else demonstrative
        )
        try:
            adjective_analyses = _analyses_with_metadata(
                self.backend.analyse(adjective_input), adjective_input
            )
            noun_analyses = _analyses_with_metadata(
                self.backend.analyse(noun_input), noun_input
            )
            demonstrative_analyses = (
                _analyses_with_metadata(
                    self.backend.analyse(demonstrative_input), demonstrative_input
                )
                if demonstrative_input is not None
                else None
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None

        adjective_selection = _select_agreement_analyses(
            adjective_analyses, prefix="adj"
        )
        noun_selection = _select_agreement_analyses(
            noun_analyses, prefix="subst", require_common_noun=True
        )
        if adjective_selection is None or noun_selection is None:
            return None
        adjective_lemma, adjective_features = adjective_selection
        if adjective_lemma in _NON_ADJECTIVE_LEMMAS:
            return None
        _, target_features = noun_selection
        if demonstrative is not None:
            demonstrative_selection = _select_agreement_analyses(
                demonstrative_analyses, prefix="adj"
            )
            if demonstrative_selection is None:
                return None
            demonstrative_lemma, demonstrative_features = demonstrative_selection
            if demonstrative_lemma != _DEMONSTRATIVE_LEMMA:
                return None
            target_features &= demonstrative_features
        if not target_features:
            return None
        if len(target_features) != 1:
            return None
        if adjective_features & target_features:
            return None

        try:
            generated_rows = _generation_rows(self.backend.generate(adjective_lemma))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None
        if generated_rows is None:
            return None
        forms: set[str] = set()
        for feature in target_features:
            feature_forms = {
                form
                for form, lemma, tag in generated_rows
                if lemma == adjective_lemma
                and tag.startswith("adj:")
                and tag.rsplit(":", 1)[-1] == "pos"
                and (tag_features := _tag_features(tag, prefix="adj")) is not None
                and feature in tag_features
            }
            if not feature_forms:
                return None
            forms.update(feature_forms)
        if len(forms) != 1:
            return None
        return next(iter(forms))

    def government_nominal_group_replacement(
        self,
        governor: str,
        adjective: str | None,
        noun: str,
        *,
        governor_lemma: str,
        governor_tags: frozenset[str],
        target_case: str,
    ) -> tuple[str | None, str] | None:
        if (
            self.identity != _qualified_identity()
            or target_case not in _GOVERNMENT_CASES
        ):
            return None
        governor_input = governor.casefold() if governor.isupper() else governor
        adjective_input = (
            adjective.casefold()
            if adjective is not None and adjective.isupper()
            else adjective
        )
        noun_input = noun.casefold() if noun.isupper() else noun
        try:
            governor_analyses = _analyses_with_metadata(
                self.backend.analyse(governor_input), governor_input
            )
            noun_analyses = _analyses_with_metadata(
                self.backend.analyse(noun_input), noun_input
            )
            adjective_analyses = (
                _analyses_with_metadata(
                    self.backend.analyse(adjective_input), adjective_input
                )
                if adjective_input is not None
                else None
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None

        if governor_analyses is None or len(governor_analyses) != len(
            set(governor_analyses)
        ):
            return None
        governor_analysis_set = {(item.lemma, item.tag) for item in governor_analyses}
        if (
            not _has_one_supported_lemma(
                governor_analysis_set,
                lemma=governor_lemma,
                source_tags=governor_tags,
            )
            or _tags_for_lemma(governor_analysis_set, governor_lemma) != governor_tags
        ):
            return None
        noun_selection = _select_government_noun_analyses(noun_analyses)
        if noun_selection is None:
            return None
        noun_lemma, noun_features = noun_selection
        noun_shapes = {(number, gender) for number, _case, gender in noun_features}
        if len(noun_shapes) != 1:
            return None
        number, gender = next(iter(noun_shapes))
        target_feature = (number, target_case, gender)

        adjective_lemma: str | None = None
        if adjective_input is not None:
            adjective_selection = _select_agreement_analyses(
                adjective_analyses, prefix="adj"
            )
            if adjective_selection is None:
                return None
            adjective_lemma, adjective_features = adjective_selection
            adjective_shapes = {
                (number, gender) for number, _case, gender in adjective_features
            }
            compatible_shapes = noun_shapes & adjective_shapes
            if len(compatible_shapes) != 1:
                return None
            if (
                adjective_lemma in _NON_ADJECTIVE_LEMMAS
                and adjective_lemma not in _GOVERNMENT_PRONOUN_LEMMAS
            ):
                return None

        try:
            noun_rows = _government_generation_rows(self.backend.generate(noun_lemma))
            adjective_rows = (
                _government_generation_rows(self.backend.generate(adjective_lemma))
                if adjective_lemma is not None
                else None
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None
        if noun_rows is None or (
            adjective_lemma is not None and adjective_rows is None
        ):
            return None
        if len(noun_rows) != len(set(noun_rows)) or (
            adjective_rows is not None
            and len(adjective_rows) != len(set(adjective_rows))
        ):
            return None

        noun_forms = _government_forms_for_feature(
            noun_rows,
            lemma=noun_lemma,
            prefix="subst",
            feature=target_feature,
        )
        noun_replacement = next(iter(noun_forms)) if len(noun_forms) == 1 else None
        if (
            noun_replacement is None
            and adjective_lemma in _GOVERNMENT_PRONOUN_LEMMAS
            and (noun_lemma, *target_feature, "programu")
            == _GOVERNMENT_PRONOUN_QUALIFIED_AMBIGUITY
            and noun_forms == {"programa", "programu"}
        ):
            noun_replacement = "programu"
        if noun_replacement is None:
            return None
        if adjective_lemma is None:
            return None, noun_replacement

        adjective_forms = _government_forms_for_feature(
            adjective_rows or (),
            lemma=adjective_lemma,
            prefix="adj",
            feature=target_feature,
        )
        if len(adjective_forms) == 1:
            adjective_replacement = next(iter(adjective_forms))
        elif adjective_input is not None and adjective_input in adjective_forms:
            assert adjective is not None
            adjective_replacement = adjective
        else:
            return None
        return adjective_replacement, noun_replacement

    @lru_cache(maxsize=8)  # noqa: B019 - bounded provider lifecycle cache
    def przygladac_sie_nowy_budynek_replacement(self) -> str | None:
        if self.identity != _qualified_identity():
            return None
        try:
            governor_analyses = _analyses(
                self.backend.analyse("przyglądam"), "przyglądam"
            )
            adjective_analyses = _analyses(self.backend.analyse("nowy"), "nowy")
            noun_analyses = _analyses(self.backend.analyse("budynek"), "budynek")
            adjective_forms = _forms(
                self.backend.generate(_PRZYGLADAC_ADJECTIVE_LEMMA),
                lemma=_PRZYGLADAC_ADJECTIVE_LEMMA,
                target_tag=_PRZYGLADAC_ADJECTIVE_TARGET_TAG,
            )
            noun_forms = _forms(
                self.backend.generate(_PRZYGLADAC_NOUN_LEMMA),
                lemma=_PRZYGLADAC_NOUN_LEMMA,
                target_tag=_PRZYGLADAC_NOUN_TARGET_TAG,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None
        if (
            not _has_one_supported_lemma(
                governor_analyses,
                lemma=_PRZYGLADAC_GOVERNOR_LEMMA,
                source_tags=_PRZYGLADAC_GOVERNOR_TAGS,
            )
            or not _has_one_supported_lemma(
                adjective_analyses,
                lemma=_PRZYGLADAC_ADJECTIVE_LEMMA,
                source_tags=_PRZYGLADAC_ADJECTIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                noun_analyses,
                lemma=_PRZYGLADAC_NOUN_LEMMA,
                source_tags=_PRZYGLADAC_NOUN_SOURCE_TAGS,
            )
            or _tags_for_lemma(governor_analyses, _PRZYGLADAC_GOVERNOR_LEMMA)
            != _PRZYGLADAC_GOVERNOR_TAGS
            or _tags_for_lemma(adjective_analyses, _PRZYGLADAC_ADJECTIVE_LEMMA)
            != _PRZYGLADAC_ADJECTIVE_SOURCE_TAGS
            or _tags_for_lemma(noun_analyses, _PRZYGLADAC_NOUN_LEMMA)
            != _PRZYGLADAC_NOUN_SOURCE_TAGS
            or adjective_forms != {"nowemu"}
            or noun_forms != {"budynkowi"}
        ):
            return None
        return "nowemu budynkowi"


def _qualified_identity() -> _ProviderIdentity:
    return _ProviderIdentity(_PACKAGE_VERSION, _DICTIONARY_ID, _NOTICE_SHA256)


def _analyses_with_metadata(
    rows: Sequence[_AnalysisRow], input_form: str
) -> tuple[_ParsedAnalysis, ...] | None:
    if isinstance(rows, (str, bytes)):
        return None
    parsed: list[_ParsedAnalysis] = []
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 3:
            return None
        start, end, interpretation = row
        if (
            type(start) is not int
            or type(end) is not int
            or (start, end) != (0, 1)
            or not isinstance(interpretation, tuple)
            or len(interpretation) != 5
        ):
            return None
        surface, lemma, tag, labels, qualifiers = interpretation
        if (
            not isinstance(surface, str)
            or surface != input_form
            or not isinstance(lemma, str)
            or not lemma
            or not isinstance(tag, str)
            or not tag
            or tag.partition(":")[0] not in _KNOWN_TAG_PREFIXES
            or not isinstance(labels, list)
            or not isinstance(qualifiers, list)
            or not all(isinstance(value, str) for value in labels)
            or not all(isinstance(value, str) for value in qualifiers)
        ):
            return None
        parsed.append(
            _ParsedAnalysis(
                lemma=lemma,
                tag=tag,
                labels=tuple(labels),
                qualifiers=tuple(qualifiers),
            )
        )
    return tuple(
        sorted(
            parsed,
            key=lambda item: (item.lemma, item.tag, item.labels, item.qualifiers),
        )
    )


def _generation_rows(
    rows: Sequence[_GenerationRow],
) -> tuple[tuple[str, str, str], ...] | None:
    if isinstance(rows, (str, bytes)):
        return None
    parsed: set[tuple[str, str, str]] = set()
    for row in rows:
        if (
            not isinstance(row, tuple)
            or len(row) != 5
            or not isinstance(row[0], str)
            or not row[0]
            or not isinstance(row[1], str)
            or not row[1]
            or not isinstance(row[2], str)
            or not isinstance(row[3], list)
            or not isinstance(row[4], list)
            or not all(isinstance(value, str) for value in row[3])
            or not all(isinstance(value, str) for value in row[4])
        ):
            return None
        tag_prefix = row[2].partition(":")[0]
        if tag_prefix not in _KNOWN_TAG_PREFIXES:
            return None
        if tag_prefix != "adj":
            continue
        if _tag_features(row[2], prefix="adj") is None:
            return None
        parsed.add((row[0], row[1], row[2]))
    return tuple(sorted(parsed))


def _select_agreement_analyses(
    analyses: tuple[_ParsedAnalysis, ...] | None,
    *,
    prefix: str,
    require_common_noun: bool = False,
) -> tuple[str, frozenset[_AgreementFeature]] | None:
    if analyses is None or any(item.tag == "ign" for item in analyses):
        return None
    selected = tuple(item for item in analyses if item.tag.startswith(f"{prefix}:"))
    if not selected:
        return None
    if prefix == "adj" and any(
        item.tag.rsplit(":", 1)[-1] != "pos" for item in selected
    ):
        return None
    if len(selected) != len(set(selected)):
        return None
    if require_common_noun and any(
        item.labels != ("nazwa_pospolita",) for item in selected
    ):
        return None
    lemmas = {item.lemma for item in selected}
    if len(lemmas) != 1:
        return None
    if prefix == "subst" and any(
        item.tag.partition(":")[0] in _VERB_TAG_PREFIXES for item in analyses
    ):
        return None
    features: set[_AgreementFeature] = set()
    for item in selected:
        parsed = _tag_features(item.tag, prefix=prefix)
        if parsed is None:
            return None
        features.update(parsed)
    return next(iter(lemmas)), frozenset(features)


def _select_government_noun_analyses(
    analyses: tuple[_ParsedAnalysis, ...] | None,
) -> tuple[str, frozenset[_AgreementFeature]] | None:
    if analyses is None or any(item.tag == "ign" for item in analyses):
        return None
    selected = tuple(item for item in analyses if item.tag.startswith("subst:"))
    if (
        not selected
        or len(selected) != 1
        or any(item.labels != ("nazwa_pospolita",) for item in selected)
        or any(
            item.tag.partition(":")[0] in _COMPETING_NOMINAL_TAG_PREFIXES
            for item in analyses
        )
    ):
        return None
    lemmas = {item.lemma for item in selected}
    if len(lemmas) != 1:
        return None
    features: set[_AgreementFeature] = set()
    for item in selected:
        parsed = _tag_features(item.tag, prefix="subst")
        if parsed is None:
            return None
        if any(case == "voc" for _number, case, _gender in parsed):
            return None
        features.update(parsed)
    return next(iter(lemmas)), frozenset(features)


def _government_generation_rows(
    rows: Sequence[_GenerationRow],
) -> tuple[tuple[str, str, str], ...] | None:
    if isinstance(rows, (str, bytes)):
        return None
    parsed: list[tuple[str, str, str]] = []
    for row in rows:
        if (
            not isinstance(row, tuple)
            or len(row) != 5
            or not isinstance(row[0], str)
            or not row[0]
            or not isinstance(row[1], str)
            or not row[1]
            or not isinstance(row[2], str)
            or not isinstance(row[3], list)
            or not isinstance(row[4], list)
            or not all(isinstance(value, str) for value in row[3])
            or not all(isinstance(value, str) for value in row[4])
        ):
            return None
        prefix = row[2].partition(":")[0]
        if prefix not in _KNOWN_TAG_PREFIXES:
            return None
        if prefix in {"adj", "subst"} and _tag_features(row[2], prefix=prefix) is None:
            return None
        parsed.append((row[0], row[1], row[2]))
    return tuple(parsed)


def _deduplicate_provider_rows(
    rows: Sequence[_AnalysisRow] | Sequence[_GenerationRow],
) -> Sequence[_AnalysisRow] | Sequence[_GenerationRow]:
    if isinstance(rows, (str, bytes)):
        return rows
    unique: list[tuple[object, ...]] = []
    for row in rows:
        if not any(_provider_rows_equal(row, candidate) for candidate in unique):
            unique.append(row)
    return tuple(unique)


def _provider_rows_equal(left: tuple[object, ...], right: tuple[object, ...]) -> bool:
    if len(left) != len(right):
        return False
    for left_value, right_value in zip(left, right, strict=True):
        if type(left_value) is not type(right_value):
            return False
        if isinstance(left_value, (list, tuple)) and isinstance(
            right_value, (list, tuple)
        ):
            if len(left_value) != len(right_value):
                return False
            if not _provider_rows_equal(tuple(left_value), tuple(right_value)):
                return False
        elif left_value != right_value:
            return False
    return True


def _government_forms_for_feature(
    rows: tuple[tuple[str, str, str], ...],
    *,
    lemma: str,
    prefix: str,
    feature: _AgreementFeature,
) -> set[str]:
    return {
        form
        for form, row_lemma, tag in rows
        if row_lemma == lemma
        and tag.startswith(f"{prefix}:")
        and (prefix != "adj" or tag.rsplit(":", 1)[-1] == "pos")
        and (tag_features := _tag_features(tag, prefix=prefix)) is not None
        and feature in tag_features
    }


def _tag_features(tag: str, *, prefix: str) -> frozenset[_AgreementFeature] | None:
    parts = tag.split(":")
    if prefix == "adj":
        if (
            len(parts) != 5
            or parts[0] != "adj"
            or parts[4] not in {"pos", "com", "sup"}
        ):
            return None
        number_part, case_part, gender_part = parts[1:4]
    elif prefix == "subst":
        if (
            len(parts) not in {4, 5}
            or parts[0] != "subst"
            or (len(parts) == 5 and parts[4] not in _KNOWN_NOUN_TAG_SUFFIXES)
        ):
            return None
        number_part, case_part, gender_part = parts[1:4]
    else:
        return None
    numbers = _tag_values(number_part, frozenset({"sg", "pl"}))
    cases = _tag_values(
        case_part,
        frozenset({"nom", "acc", "gen", "dat", "inst", "loc", "voc"}),
    )
    genders = _tag_values(gender_part, frozenset({"m1", "m2", "m3", "f", "n"}))
    if numbers is None or cases is None or genders is None:
        return None
    return frozenset(
        (number, case, gender)
        for number in numbers
        for case in cases
        for gender in genders
    )


def _tag_values(value: str, allowed: frozenset[str]) -> frozenset[str] | None:
    values = frozenset(value.split("."))
    if not values or "" in values or not values <= allowed:
        return None
    return values


def _analyses(
    rows: Sequence[_AnalysisRow], input_form: str
) -> set[tuple[str, str]] | None:
    if isinstance(rows, (str, bytes)):
        return None
    parsed: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 3:
            return None
        start, end, interpretation = row
        if (
            type(start) is not int
            or type(end) is not int
            or not isinstance(interpretation, tuple)
            or len(interpretation) != 5
        ):
            return None
        surface, lemma, tag, labels, qualifiers = interpretation
        if (
            not isinstance(surface, str)
            or not isinstance(lemma, str)
            or not isinstance(tag, str)
            or not isinstance(labels, list)
            or not all(isinstance(label, str) for label in labels)
            or not isinstance(qualifiers, list)
            or not all(isinstance(qualifier, str) for qualifier in qualifiers)
            or (start, end) != (0, 1)
            or surface != input_form
            or not lemma
            or not tag
        ):
            return None
        parsed.add((lemma, tag))
    return parsed


def _forms(
    rows: Sequence[_GenerationRow], *, lemma: str, target_tag: str
) -> set[str] | None:
    if isinstance(rows, (str, bytes)):
        return None
    parsed: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 5:
            return None
        form, row_lemma, tag, labels, qualifiers = row
        if (
            not isinstance(form, str)
            or not isinstance(row_lemma, str)
            or not isinstance(tag, str)
            or not isinstance(labels, list)
            or not all(isinstance(label, str) for label in labels)
            or not isinstance(qualifiers, list)
            or not all(isinstance(qualifier, str) for qualifier in qualifiers)
            or not form
            or not row_lemma
            or not tag
        ):
            return None
        parsed.add((form, row_lemma, tag))
    return {
        form
        for form, row_lemma, tag in parsed
        if row_lemma == lemma and tag == target_tag
    }


def _has_one_supported_lemma(
    analyses: set[tuple[str, str]] | None,
    *,
    lemma: str,
    source_tags: frozenset[str],
) -> bool:
    if not analyses or any(tag == "ign" for _, tag in analyses):
        return False
    source_pos = next(iter(source_tags)).partition(":")[0]
    selected = {
        (row_lemma, tag)
        for row_lemma, tag in analyses
        if tag.partition(":")[0] == source_pos
    }
    selected_lemmas = {row_lemma for row_lemma, _ in selected}
    return selected_lemmas == {lemma} and all(tag in source_tags for _, tag in selected)


def _tags_for_lemma(analyses: set[tuple[str, str]] | None, lemma: str) -> set[str]:
    if analyses is None:
        return set()
    return {tag for row_lemma, tag in analyses if row_lemma == lemma}


def _load_qualified_morfeusz() -> _QualifiedMorfeusz | None:
    _OBSERVED_PROVIDER_IDENTITY.set(None)
    try:
        module = importlib.import_module("morfeusz2")
        if not isinstance(module, _MorfeuszModule):
            return None
        backend = module.Morfeusz()
        if not isinstance(backend, _IdentityBackend):
            return None
        identity = _ProviderIdentity(
            package_version=importlib.metadata.version("morfeusz2"),
            dictionary_id=backend.dict_id(),
            dictionary_notice_sha256=hashlib.sha256(
                backend.dict_copyright().encode("utf-8")
            ).hexdigest(),
        )
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
        return None
    if type(backend).__module__ != "morfeusz2" or type(backend).__name__ != "Morfeusz":
        return None
    _OBSERVED_PROVIDER_IDENTITY.set(identity)
    if identity != _qualified_identity():
        return None
    return _QualifiedMorfeusz(
        backend=_CanonicalMorfeuszBackend(
            backend,
            normalize_exact_duplicates=True,
        ),
        identity=identity,
    )


def _observed_morfeusz_identity() -> _ProviderIdentity | None:
    return _OBSERVED_PROVIDER_IDENTITY.get()


__all__: list[str] = []
