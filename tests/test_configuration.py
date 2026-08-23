from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from polis import Analyzer, AnalyzerConfig, Category, ConfigurationError

_MESSAGE = "'analysis.categories' must be None or a frozenset of Category values"


@pytest.mark.parametrize(
    "value",
    (
        frozenset({"bogus"}),
        frozenset({"spelling"}),
        frozenset({1}),
        frozenset({True}),
        frozenset({Category.SPELLING, "syntax"}),
        "spelling",
        b"spelling",
        set(),
        {Category.SPELLING},
        [Category.SPELLING],
        0,
    ),
)
def test_invalid_direct_categories_fail_during_configuration_construction(
    value: (
        frozenset[str]
        | frozenset[int]
        | frozenset[bool]
        | frozenset[Category | str]
        | str
        | bytes
        | set[Category]
        | list[Category]
        | int
    ),
) -> None:
    with pytest.raises(ConfigurationError, match=_MESSAGE) as raised:
        AnalyzerConfig(**{"categories": value})

    assert raised.value.code == "configuration.invalid"
    assert raised.value.retryable is False
    assert raised.value.context == {"operation": "configuration.construct"}


def test_invalid_categories_error_does_not_expose_the_value() -> None:
    with pytest.raises(ConfigurationError) as raised:
        AnalyzerConfig(categories=frozenset({"bogus"}))

    assert "bogus" not in str(raised.value)
    assert "bogus" not in str(raised.value.context)


class _StatefulFrozenSet(frozenset[Category]):
    iterations: int

    def __new__(cls) -> _StatefulFrozenSet:
        value = super().__new__(cls, {Category.SPELLING})
        value.iterations = 0
        return value

    def __iter__(self) -> Iterator[Category | str]:
        self.iterations += 1
        if self.iterations == 1:
            return iter((Category.SPELLING,))
        return iter(("bogus",))


def test_frozenset_subclass_is_rejected_during_configuration_construction() -> None:
    categories = _StatefulFrozenSet()

    with pytest.raises(ConfigurationError, match=_MESSAGE) as raised:
        AnalyzerConfig(categories=categories)

    assert raised.value.code == "configuration.invalid"
    assert raised.value.retryable is False
    assert raised.value.context == {"operation": "configuration.construct"}
    assert categories.iterations == 0


def test_toml_unknown_category_keeps_invalid_value_contract(
    tmp_path: Path,
) -> None:
    path = tmp_path / "polis.toml"
    path.write_text('[analysis]\ncategories = ["bogus"]\n', encoding="utf-8")

    with pytest.raises(ConfigurationError) as raised:
        AnalyzerConfig.from_toml(path)

    assert raised.value.code == "configuration.invalid_value"
    assert raised.value.retryable is False
    assert raised.value.context == {"path": str(path)}


def test_toml_invalid_confidence_wraps_constructor_contract(
    tmp_path: Path,
) -> None:
    path = tmp_path / "polis.toml"
    path.write_text('[analysis]\nminimum_confidence = 2.0\n', encoding="utf-8")

    with pytest.raises(ConfigurationError) as raised:
        AnalyzerConfig.from_toml(path)

    assert raised.value.code == "configuration.invalid"
    assert raised.value.retryable is False
    assert raised.value.context == {
        "operation": "configuration.load",
        "path": str(path),
    }


@pytest.mark.parametrize("category", Category)
def test_each_category_value_is_accepted(category: Category) -> None:
    config = AnalyzerConfig(categories=frozenset({category}))

    assert config.categories == frozenset({category})


def test_none_categories_remain_accepted() -> None:
    assert AnalyzerConfig().categories is None


def test_empty_frozenset_selects_no_categories() -> None:
    config = AnalyzerConfig(categories=frozenset())

    assert config.categories == frozenset()
    assert Analyzer(config).analyze("zeby").issues == ()


def test_none_categories_analyze_every_category() -> None:
    assert Analyzer(AnalyzerConfig()).analyze("zeby").issues


def test_toml_categories_are_mapped_to_category_before_construction(
    tmp_path: Path,
) -> None:
    path = tmp_path / "polis.toml"
    path.write_text(
        '[analysis]\ncategories = ["spelling", "syntax"]\n',
        encoding="utf-8",
    )

    config = AnalyzerConfig.from_toml(path)

    assert config.categories == frozenset({Category.SPELLING, Category.SYNTAX})
