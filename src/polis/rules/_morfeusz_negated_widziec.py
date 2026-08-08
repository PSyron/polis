"""Private Morfeusz2 adapter for one closed negated-government consumer."""

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
_ADJECTIVE_LEMMA: Final = "czerwony:A"
_NOUN_LEMMA: Final = "samochód"
_ADJECTIVE_SOURCE_TAGS: Final = frozenset(
    {
        "adj:sg:acc:m3:pos",
        "adj:sg:nom.voc:m1.m2.m3:pos",
    }
)
_NOUN_SOURCE_TAGS: Final = frozenset({"subst:sg:nom.acc:m3"})
_ADJECTIVE_TARGET_TAG: Final = "adj:sg:gen:m1.m2.m3.n:pos"
_NOUN_TARGET_TAG: Final = "subst:sg:gen:m3"


class _NegatedWidziecBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


@runtime_checkable
class _QualifiedBackend(_NegatedWidziecBackend, Protocol):
    def dict_id(self) -> str: ...

    def dict_copyright(self) -> str: ...


@runtime_checkable
class _MorfeuszModule(Protocol):
    Morfeusz: Callable[[], _QualifiedBackend]


@dataclass(frozen=True, slots=True)
class _ProviderIdentity:
    package_version: str
    dictionary_id: str
    dictionary_notice_sha256: str


@dataclass(frozen=True, slots=True)
class _NegatedWidziecMorphology:
    backend: _NegatedWidziecBackend
    identity: _ProviderIdentity

    def replacement(self, adjective: str, noun: str) -> str | None:
        if self.identity != _qualified_identity():
            return None
        try:
            adjective_analyses = _analyses(self.backend.analyse(adjective), adjective)
            noun_analyses = _analyses(self.backend.analyse(noun), noun)
            adjective_forms = _forms(
                self.backend.generate(_ADJECTIVE_LEMMA),
                lemma=_ADJECTIVE_LEMMA,
                target_tag=_ADJECTIVE_TARGET_TAG,
            )
            noun_forms = _forms(
                self.backend.generate(_NOUN_LEMMA),
                lemma=_NOUN_LEMMA,
                target_tag=_NOUN_TARGET_TAG,
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            return None
        if (
            not _has_one_supported_lemma(
                adjective_analyses,
                lemma=_ADJECTIVE_LEMMA,
                source_tags=_ADJECTIVE_SOURCE_TAGS,
            )
            or not _has_one_supported_lemma(
                noun_analyses,
                lemma=_NOUN_LEMMA,
                source_tags=_NOUN_SOURCE_TAGS,
            )
            or adjective_forms != {"czerwonego"}
            or noun_forms != {"samochodu"}
        ):
            return None
        return "czerwonego samochodu"


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


def _load_qualified_negated_widziec_morphology() -> _NegatedWidziecMorphology | None:
    try:
        module = importlib.import_module("morfeusz2")
        if not isinstance(module, _MorfeuszModule):
            return None
        backend = module.Morfeusz()
        if not isinstance(backend, _QualifiedBackend):
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
    return _NegatedWidziecMorphology(backend=backend, identity=identity)


__all__: list[str] = []
