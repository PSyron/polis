"""Deterministic, privacy-safe Unicode cases for structural tests."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import sha256

GENERATOR_VERSION = "unicode-structural-v1"
DEFAULT_SEED = 95001
DEFAULT_CASES = 64
MAX_CASES = 256
_MAX_SEED = 2**64 - 1
_SAFE_INVARIANT = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")

_FAMILY_FRAGMENTS = (
    ("ascii", "Ala ma kota"),
    ("polish_diacritics", "Zażółć gęślą jaźń"),
    ("non_bmp", "🙂𐍈"),
    ("combining_marks", "e\u0301"),
    ("lf", "\n"),
    ("crlf", "\r\n"),
    ("punctuation", ".?!,;:—"),
    ("quotes", '"„”«»'),
)
UNICODE_FAMILIES = frozenset(name for name, _ in _FAMILY_FRAGMENTS)


@dataclass(frozen=True, slots=True)
class Replay:
    """Metadata that identifies a generated case without exposing its text."""

    generator_version: str
    seed: int
    case_index: int

    def __post_init__(self) -> None:
        if self.generator_version != GENERATOR_VERSION:
            raise ValueError("generator_version must match the current generator")
        _validate_seed(self.seed)
        if isinstance(self.case_index, bool) or not isinstance(self.case_index, int):
            raise TypeError("case_index must be an integer")
        if self.case_index < 0:
            raise ValueError("case_index must be non-negative")

    def __str__(self) -> str:
        return f"generator={GENERATOR_VERSION} seed={self.seed} case={self.case_index}"


@dataclass(frozen=True, slots=True)
class SyntheticTextCase:
    """An immutable synthetic case whose representation omits generated text."""

    replay: Replay
    families: frozenset[str]
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.replay, Replay):
            raise TypeError("replay must be a Replay")
        if not isinstance(self.families, frozenset):
            raise TypeError("families must be a frozenset")
        if not all(isinstance(family, str) for family in self.families):
            raise TypeError("families must contain strings")
        if not self.families.issubset(UNICODE_FAMILIES):
            raise ValueError("families must be supported Unicode families")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")


def generate_unicode_text_cases(
    *, seed: int = DEFAULT_SEED, count: int = DEFAULT_CASES
) -> tuple[SyntheticTextCase, ...]:
    """Return exactly ``count`` independently replayable synthetic text cases.

    ``seed`` must be an integer in the inclusive unsigned 64-bit range and
    ``count`` must be an integer from one through ``MAX_CASES``.
    """
    _validate_seed(seed)
    _validate_count(count)

    family_order = tuple(name for name, _ in _FAMILY_FRAGMENTS)
    cases: list[SyntheticTextCase] = []
    for index in range(count):
        replay = Replay(GENERATOR_VERSION, seed, index)
        if index == 0:
            cases.append(SyntheticTextCase(replay, frozenset(), ""))
            continue

        digest = sha256(f"{GENERATOR_VERSION}:{seed}:{index}".encode("ascii")).digest()
        mandatory_index = (index - 1) % len(family_order)
        selected_indexes = {
            family_index
            for family_index in range(len(family_order))
            if digest[family_index] % 3 == 0
        }
        selected_indexes.add(mandatory_index)
        ordered_indexes = sorted(
            selected_indexes,
            key=lambda family_index: (digest[16 + family_index], family_index),
        )
        fragments = [
            _FAMILY_FRAGMENTS[family_index][1] * (1 + digest[8 + family_index] % 2)
            for family_index in ordered_indexes
        ]
        separators = ("", " ", "\t")
        text = fragments[0] + "".join(
            separators[digest[24 + position % 8] % 3] + fragment
            for position, fragment in enumerate(fragments[1:])
        )
        families = frozenset(
            family_order[family_index] for family_index in selected_indexes
        )
        cases.append(SyntheticTextCase(replay, families, text))

    return tuple(cases)


def assert_structural_invariant(
    condition: bool, *, invariant: str, replay: Replay
) -> None:
    """Assert a named structural invariant without including generated text."""
    if not isinstance(condition, bool):
        raise TypeError("condition must be a bool")
    if not isinstance(invariant, str):
        raise TypeError("invariant must be a string")
    if _SAFE_INVARIANT.fullmatch(invariant) is None:
        raise ValueError("invariant must be a safe identifier")
    if not isinstance(replay, Replay):
        raise TypeError("replay must be a Replay")
    if not condition:
        raise AssertionError(f"structural invariant failed: {invariant}; {replay}")


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if not 0 <= seed <= _MAX_SEED:
        raise ValueError("seed must be between 0 and 2**64 - 1")


def _validate_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if not 1 <= count <= MAX_CASES:
        raise ValueError(f"count must be between 1 and {MAX_CASES}")
