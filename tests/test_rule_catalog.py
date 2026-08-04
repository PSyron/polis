from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from polis.core import Category, Source, SourceKind
from polis.rules import (
    DuplicateRuleMetadataError,
    InvalidRuleMetadataError,
    RuleAvailability,
    RuleCatalog,
    RuleCatalogError,
    RuleMetadata,
)

PRIVATE_TEXT = "PRIVATE_ANALYZED_SENTENCE"


def _metadata(name: str = "example", /, **changes: object) -> RuleMetadata:
    values: dict[str, object] = {
        "source": Source(SourceKind.RULE, name),
        "operation": "analyze",
        "behavior_version": "1",
        "categories": frozenset({Category.SYNTAX}),
        "enabled_by_default": True,
        "availability": RuleAvailability.BUILT_IN,
        "description": "Checks example syntax.",
    }
    values.update(changes)
    return RuleMetadata(**cast(Any, values))


def test_rule_availability_has_stable_serialized_values() -> None:
    assert RuleAvailability.BUILT_IN.value == "built_in"
    assert RuleAvailability.REQUIRES_CONFIGURATION.value == "requires_configuration"


def test_rule_metadata_is_an_immutable_slotted_value() -> None:
    metadata = _metadata()

    assert metadata == _metadata()
    assert metadata.source == Source(SourceKind.RULE, "example")
    assert metadata.operation == "analyze"
    assert metadata.behavior_version == "1"
    assert metadata.categories == frozenset({Category.SYNTAX})
    assert metadata.enabled_by_default is True
    assert metadata.availability is RuleAvailability.BUILT_IN
    assert metadata.description == "Checks example syntax."
    assert not hasattr(metadata, "__dict__")
    with pytest.raises(FrozenInstanceError):
        metadata.description = "Changed"


def test_rule_catalog_preserves_declared_order_and_supports_exact_lookup() -> None:
    second = _metadata("second")
    first = _metadata("first")
    catalog = RuleCatalog((second, first))

    assert catalog.entries() == (second, first)
    assert catalog.get(first.source) is first
    assert catalog.get(Source(SourceKind.RULE, "missing")) is None
    assert not hasattr(catalog, "__dict__")
    with pytest.raises(FrozenInstanceError):
        catalog._entries = ()


def test_empty_rule_catalog_is_valid() -> None:
    assert RuleCatalog(()).entries() == ()


def test_rule_catalog_rejects_duplicate_sources() -> None:
    with pytest.raises(
        DuplicateRuleMetadataError,
        match=r"^duplicate rule metadata source: rule:example$",
    ):
        RuleCatalog((_metadata(), _metadata()))


def test_rule_metadata_rejects_source_subclasses_without_exposing_values() -> None:
    class PrivateSource(Source):  # type: ignore[misc]
        def __str__(self) -> str:
            return PRIVATE_TEXT

    with pytest.raises(
        InvalidRuleMetadataError,
        match=r"^invalid rule metadata field: source$",
    ) as error:
        _metadata(source=PrivateSource(SourceKind.RULE, "example"))

    assert PRIVATE_TEXT not in str(error.value)


def test_rule_metadata_rejects_source_name_subclasses_without_exposing_values() -> None:
    class PrivateName(str):
        def __str__(self) -> str:
            return PRIVATE_TEXT

    source = Source(SourceKind.RULE, PrivateName("example"))

    with pytest.raises(
        InvalidRuleMetadataError,
        match=r"^invalid rule metadata field: source$",
    ) as error:
        _metadata(source=source)

    assert PRIVATE_TEXT not in str(error.value)


def test_rule_metadata_rejects_string_subclasses() -> None:
    class FlippingString(str):
        comparisons = 0

        def __eq__(self, other: object) -> bool:
            type(self).comparisons += 1
            return type(self).comparisons % 2 == 1

        def __ne__(self, other: object) -> bool:
            return not self.__eq__(other)

        __hash__ = str.__hash__

        def strip(self, chars: str | None = None) -> FlippingString:
            return self

    with pytest.raises(
        InvalidRuleMetadataError,
        match=r"^invalid rule metadata field: operation$",
    ):
        _metadata(operation=FlippingString("analyze"))


def test_rule_metadata_rejects_frozenset_subclasses() -> None:
    class FlippingFrozenSet(frozenset[Category]):
        iterations = 0

        def __iter__(self):  # type: ignore[no-untyped-def]
            type(self).iterations += 1
            if type(self).iterations % 2 == 1:
                return super().__iter__()
            return iter(())

    categories = FlippingFrozenSet({Category.SYNTAX})

    with pytest.raises(
        InvalidRuleMetadataError,
        match=r"^invalid rule metadata field: categories$",
    ):
        _metadata(categories=categories)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("source", object()),
        ("source", Source(SourceKind.LLM, "example")),
        ("operation", ""),
        ("operation", " analyze"),
        ("behavior_version", ""),
        ("behavior_version", "1 "),
        ("categories", frozenset()),
        ("categories", {Category.SYNTAX}),
        ("categories", frozenset({"syntax"})),
        ("enabled_by_default", 1),
        ("availability", "built_in"),
        ("description", ""),
        ("description", f" {PRIVATE_TEXT} "),
    ),
)
def test_rule_metadata_rejects_malformed_fields_without_exposing_values(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(
        InvalidRuleMetadataError,
        match=rf"^invalid rule metadata field: {field_name}$",
    ) as error:
        _metadata(**{field_name: invalid_value})

    assert PRIVATE_TEXT not in str(error.value)


@pytest.mark.parametrize(
    "entries",
    (
        [_metadata()],
        {_metadata()},
        (_metadata() for _ in range(1)),
    ),
)
def test_rule_catalog_rejects_non_tuple_containers_without_exposing_values(
    entries: object,
) -> None:
    with pytest.raises(
        RuleCatalogError,
        match=r"^catalog entries must be an ordered tuple$",
    ) as error:
        RuleCatalog(cast(Any, entries))

    assert PRIVATE_TEXT not in str(error.value)


def test_rule_catalog_rejects_tuple_subclasses_with_custom_iteration() -> None:
    class ReorderingTuple(tuple[RuleMetadata, ...]):
        def __iter__(self):  # type: ignore[no-untyped-def]
            return reversed(tuple(super().__iter__()))

    entries = ReorderingTuple((_metadata("first"), _metadata("second")))

    with pytest.raises(
        RuleCatalogError,
        match=r"^catalog entries must be an ordered tuple$",
    ):
        RuleCatalog(entries)


def test_rule_catalog_rejects_metadata_subclasses() -> None:
    class ExtendedRuleMetadata(RuleMetadata):  # type: ignore[misc]
        pass

    metadata = _metadata()
    extended = ExtendedRuleMetadata(
        source=metadata.source,
        operation=metadata.operation,
        behavior_version=metadata.behavior_version,
        categories=metadata.categories,
        enabled_by_default=metadata.enabled_by_default,
        availability=metadata.availability,
        description=metadata.description,
    )

    with pytest.raises(
        RuleCatalogError,
        match=r"^catalog entries must contain RuleMetadata values$",
    ):
        RuleCatalog((extended,))


def test_rule_catalog_rejects_non_metadata_entries_without_exposing_values() -> None:
    invalid_entry = {"description": PRIVATE_TEXT}

    with pytest.raises(
        RuleCatalogError,
        match=r"^catalog entries must contain RuleMetadata values$",
    ) as error:
        RuleCatalog(cast(Any, (invalid_entry,)))

    assert PRIVATE_TEXT not in str(error.value)


def test_rule_catalog_rejects_invalid_lookup_without_exposing_values() -> None:
    with pytest.raises(
        RuleCatalogError,
        match=r"^catalog lookup source must be a Source$",
    ) as error:
        RuleCatalog(()).get(cast(Any, {"text": PRIVATE_TEXT}))

    assert PRIVATE_TEXT not in str(error.value)


def test_rule_catalog_rejects_source_subclasses_during_lookup() -> None:
    class PrivateSource(Source):  # type: ignore[misc]
        def __eq__(self, other: object) -> bool:
            raise ValueError(PRIVATE_TEXT)

        __hash__ = Source.__hash__

    with pytest.raises(
        RuleCatalogError,
        match=r"^catalog lookup source must be a Source$",
    ) as error:
        RuleCatalog((_metadata(),)).get(PrivateSource(SourceKind.RULE, "example"))

    assert PRIVATE_TEXT not in str(error.value)


def test_rule_catalog_contracts_are_internal_to_rules_package() -> None:
    import polis

    assert "RuleCatalog" not in polis.__all__
    assert "RuleMetadata" not in polis.__all__
    assert not hasattr(polis, "RuleCatalog")
    assert not hasattr(polis, "RuleMetadata")
