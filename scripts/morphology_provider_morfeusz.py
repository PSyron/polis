from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts.morphology_provider_contract import QualificationCase

type AnalysisRow = tuple[object, ...]
type GenerationRow = tuple[object, ...]


class MorfeuszBackend(Protocol):
    def analyse(self, text: str) -> Sequence[AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[GenerationRow]: ...

    def dict_id(self) -> str: ...

    def dict_copyright(self) -> str: ...


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    package_version: str
    dictionary_id: str
    dictionary_notice_sha256: str
    installed_bytes: int


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    kind: str
    form: str | None
    reason: str


def _analyses(rows: object, input_form: str) -> set[tuple[str, str]] | None:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
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


def _generated_forms(rows: object, lemma: str, target_tag: str) -> set[str] | None:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
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


@dataclass(frozen=True, slots=True)
class MorfeuszProvider:
    backend: MorfeuszBackend
    identity: ProviderIdentity

    def evaluate(self, case: QualificationCase) -> CaseOutcome:
        analyses = _analyses(self.backend.analyse(case.input_form), case.input_form)
        if analyses is None:
            return CaseOutcome(case.id, "abstain", None, "invalid-analysis-schema")
        if not analyses or any(tag == "ign" for _, tag in analyses):
            return CaseOutcome(case.id, "abstain", None, "unknown-source")
        if case.source_lemma is None:
            if len(analyses) != 1:
                return CaseOutcome(case.id, "abstain", None, "ambiguous-source")
            lemma, _ = next(iter(analyses))
        else:
            selected = {
                lemma
                for lemma, tag in analyses
                if lemma == case.source_lemma
                and (case.source_pos is None or tag.split(":", 1)[0] == case.source_pos)
            }
            if len(selected) != 1:
                return CaseOutcome(case.id, "abstain", None, "source-filter-mismatch")
            lemma = next(iter(selected))
        target_pos = case.target_tag.split(":", 1)[0]
        if case.source_pos is not None and case.source_pos != target_pos:
            return CaseOutcome(case.id, "abstain", None, "incompatible-pos")
        forms = _generated_forms(self.backend.generate(lemma), lemma, case.target_tag)
        if forms is None:
            return CaseOutcome(case.id, "abstain", None, "invalid-generation-schema")
        if len(forms) != 1:
            reason = "no-exact-candidate" if not forms else "ambiguous-candidate"
            return CaseOutcome(case.id, "abstain", None, reason)
        form = next(iter(forms))
        if form == case.input_form:
            return CaseOutcome(case.id, "abstain", None, "already-satisfied")
        return CaseOutcome(case.id, "suggest", form, "unique-exact-candidate")


def _installed_bytes(distribution: importlib.metadata.Distribution) -> int:
    total = 0
    for item in distribution.files or ():
        path = Path(str(distribution.locate_file(item)))
        if path.is_file():
            total += path.stat().st_size
    return total


def load_provider() -> MorfeuszProvider:
    module = importlib.import_module("morfeusz2")
    backend = module.Morfeusz()
    distribution = importlib.metadata.distribution("morfeusz2")
    notice = backend.dict_copyright()
    identity = ProviderIdentity(
        package_version=distribution.version,
        dictionary_id=backend.dict_id(),
        dictionary_notice_sha256=hashlib.sha256(notice.encode()).hexdigest(),
        installed_bytes=_installed_bytes(distribution),
    )
    return MorfeuszProvider(backend=backend, identity=identity)
