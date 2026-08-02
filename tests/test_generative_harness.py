from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
from tests.generative import (
    DEFAULT_CASES,
    DEFAULT_SEED,
    GENERATOR_VERSION,
    MAX_CASES,
    UNICODE_FAMILIES,
    Replay,
    SyntheticTextCase,
    assert_structural_invariant,
    generate_unicode_text_cases,
)

_GOLDEN_CASE_FINGERPRINTS = {
    "unicode-structural-v1": (
        "c581990272f0660faf9ead3ad1d209c4aebd9cc82d9560c41f912cad4b44907e"
    ),
}
_CONFIGURATION_ENVIRONMENT = (
    "POLIS_GENERATIVE_GENERATOR_VERSION",
    "POLIS_GENERATIVE_SEED",
    "POLIS_GENERATIVE_CASES",
)
ROOT = Path(__file__).resolve().parents[1]
COMPLETED_PROPERTY_MODULES = (
    "tests/test_segmentation_properties.py",
    "tests/test_generated_finding_fidelity.py",
    "tests/test_correction_properties.py",
    "tests/test_rule_registry_properties.py",
    "tests/test_generated_pipeline_parity.py",
)


def _length_prefixed(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def _case_fingerprint(cases: tuple[SyntheticTextCase, ...]) -> str:
    fingerprint = sha256()
    for case in cases:
        fingerprint.update(
            _length_prefixed(str(case.replay.case_index).encode("ascii"))
        )
        families = tuple(sorted(case.families))
        fingerprint.update(_length_prefixed(str(len(families)).encode("ascii")))
        for family in families:
            fingerprint.update(_length_prefixed(family.encode("utf-8")))
        fingerprint.update(_length_prefixed(case.text.encode("utf-8")))
    return fingerprint.hexdigest()


def test_generated_cases_are_reproducible_and_seeded() -> None:
    first = generate_unicode_text_cases(seed=DEFAULT_SEED, count=DEFAULT_CASES)
    repeated = generate_unicode_text_cases(seed=DEFAULT_SEED, count=DEFAULT_CASES)
    different = generate_unicode_text_cases(seed=DEFAULT_SEED + 1, count=DEFAULT_CASES)

    assert first == repeated
    assert any(
        left.text != right.text for left, right in zip(first, different, strict=True)
    )
    assert len(first) == DEFAULT_CASES
    assert first[0].text == ""
    assert first[0].families == frozenset()


def test_default_cases_match_the_versioned_golden_fingerprint() -> None:
    expected = _GOLDEN_CASE_FINGERPRINTS.get(GENERATOR_VERSION)

    assert expected is not None
    assert _case_fingerprint(generate_unicode_text_cases()) == expected


def test_default_generator_configuration_uses_constants_when_environment_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in _CONFIGURATION_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)

    cases = generate_unicode_text_cases()

    assert len(cases) == DEFAULT_CASES
    assert all(case.replay.seed == DEFAULT_SEED for case in cases)


def test_default_generator_configuration_consumes_complete_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLIS_GENERATIVE_GENERATOR_VERSION", GENERATOR_VERSION)
    monkeypatch.setenv("POLIS_GENERATIVE_SEED", "95002")
    monkeypatch.setenv("POLIS_GENERATIVE_CASES", "8")

    cases = generate_unicode_text_cases()

    assert len(cases) == 8
    assert all(case.replay.seed == 95002 for case in cases)


def test_completed_properties_accept_alternate_generator_configuration() -> None:
    environment = {
        **os.environ,
        "POLIS_GENERATIVE_GENERATOR_VERSION": GENERATOR_VERSION,
        "POLIS_GENERATIVE_SEED": "95002",
        "POLIS_GENERATIVE_CASES": "8",
    }

    result = subprocess.run(
        [sys.executable, "-m", "pytest", *COMPLETED_PROPERTY_MODULES, "-q"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_default_generator_configuration_rejects_partial_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLIS_GENERATIVE_SEED", "95002")
    for name in (
        "POLIS_GENERATIVE_GENERATOR_VERSION",
        "POLIS_GENERATIVE_CASES",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="complete"):
        generate_unicode_text_cases()


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("POLIS_GENERATIVE_GENERATOR_VERSION", "unicode-structural-v2"),
        ("POLIS_GENERATIVE_SEED", "not-a-seed"),
        ("POLIS_GENERATIVE_SEED", str(2**64)),
        ("POLIS_GENERATIVE_CASES", "0"),
        ("POLIS_GENERATIVE_CASES", "many"),
        ("POLIS_GENERATIVE_CASES", "257"),
    ),
)
def test_default_generator_configuration_rejects_invalid_environment(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv("POLIS_GENERATIVE_GENERATOR_VERSION", GENERATOR_VERSION)
    monkeypatch.setenv("POLIS_GENERATIVE_SEED", str(DEFAULT_SEED))
    monkeypatch.setenv("POLIS_GENERATIVE_CASES", str(DEFAULT_CASES))
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        generate_unicode_text_cases()


def test_case_prefix_is_stable_across_budgets() -> None:
    assert generate_unicode_text_cases(count=8) == generate_unicode_text_cases()[:8]


def test_generated_cases_use_frozen_synthetic_text_case_records() -> None:
    case = generate_unicode_text_cases(count=2)[1]

    assert isinstance(case, SyntheticTextCase)
    with pytest.raises(FrozenInstanceError):
        case.text = "replacement"  # type: ignore[misc]


def test_default_run_covers_every_supported_unicode_family() -> None:
    cases = generate_unicode_text_cases()

    assert frozenset().union(*(case.families for case in cases)) == UNICODE_FAMILIES
    for case in cases:
        assert case.replay.generator_version == GENERATOR_VERSION
        assert case.replay.seed == DEFAULT_SEED


@pytest.mark.parametrize("count", [1, 8, MAX_CASES])
def test_generator_returns_the_exact_bounded_count(count: int) -> None:
    cases = generate_unicode_text_cases(count=count)

    assert len(cases) == count
    assert [case.replay.case_index for case in cases] == list(range(count))


@pytest.mark.parametrize("count", [0, -1, MAX_CASES + 1])
def test_generator_rejects_out_of_range_budgets(count: int) -> None:
    with pytest.raises(ValueError):
        generate_unicode_text_cases(count=count)


@pytest.mark.parametrize("count", [True, 1.5, "1"])
def test_generator_rejects_non_integer_budgets(count: object) -> None:
    with pytest.raises(TypeError):
        generate_unicode_text_cases(count=count)  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", [-1, 2**64])
def test_generator_rejects_out_of_range_seeds(seed: int) -> None:
    with pytest.raises(ValueError):
        generate_unicode_text_cases(seed=seed)


@pytest.mark.parametrize("seed", [True, 1.5, "1"])
def test_generator_rejects_non_integer_seeds(seed: object) -> None:
    with pytest.raises(TypeError):
        generate_unicode_text_cases(seed=seed)  # type: ignore[arg-type]


def test_replay_and_failures_do_not_expose_generated_text() -> None:
    # This catches adding text to SyntheticTextCase.__repr__ or to a shared
    # invariant failure path.
    sentinel = "PRIVATE_SENTINEL"
    replay = Replay(GENERATOR_VERSION, DEFAULT_SEED, 7)
    case = generate_unicode_text_cases(seed=DEFAULT_SEED, count=8)[7]
    object.__setattr__(case, "text", sentinel)

    assert sentinel not in repr(case)
    assert sentinel not in repr(replay)
    assert str(replay) == "generator=unicode-structural-v1 seed=95001 case=7"
    with pytest.raises(AssertionError) as error:
        assert_structural_invariant(
            False,
            invariant="harness.privacy",
            replay=replay,
        )
    assert sentinel not in str(error.value)
    assert str(error.value) == (
        "structural invariant failed: harness.privacy; "
        "generator=unicode-structural-v1 seed=95001 case=7"
    )


def test_invariant_name_must_be_a_safe_identifier() -> None:
    replay = Replay(GENERATOR_VERSION, DEFAULT_SEED, 0)
    with pytest.raises(ValueError):
        assert_structural_invariant(False, invariant="private text", replay=replay)
