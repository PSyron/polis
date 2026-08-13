"""Private qualified Morfeusz2 adapter for current closed consumers."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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


class _QualifiedMorfeuszBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


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


@dataclass(frozen=True, slots=True)
class _QualifiedMorfeusz:
    backend: _QualifiedMorfeuszBackend
    identity: _ProviderIdentity

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
        except (KeyError, RuntimeError, TypeError, ValueError):
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
        except (KeyError, RuntimeError, TypeError, ValueError):
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
        except (KeyError, RuntimeError, TypeError, ValueError):
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


def _qualified_identity() -> _ProviderIdentity:
    return _ProviderIdentity(_PACKAGE_VERSION, _DICTIONARY_ID, _NOTICE_SHA256)


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
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return None
    if identity != _qualified_identity():
        return None
    return _QualifiedMorfeusz(backend=backend, identity=identity)


__all__: list[str] = []
