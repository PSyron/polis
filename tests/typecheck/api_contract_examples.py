"""Strictly type-checked examples for the ADR-0003 typing-only contract."""

from __future__ import annotations

import polis
import polis.core
from polis import (
    AnalysisOptions,
    AnalysisTimeoutError,
    Analyzer,
    BackendUnavailableError,
    ConfigurationError,
    CorrectionConflictError,
    InvalidBackendResponseError,
    PolisError,
    UncorrectableFindingError,
    UnknownFindingError,
)


def analyze_successfully() -> str:
    analyzer = Analyzer.from_config("polis.toml")
    result: polis.AnalysisResult = analyzer.analyze(
        "Te zdanie zawiera błąd.",
        options=AnalysisOptions(categories={"agreement"}, minimum_confidence=0.8),
    )
    return result.apply(issue_ids=())


async def analyze_without_blocking_an_event_loop() -> str:
    analyzer = Analyzer.from_config("polis.toml")
    result: polis.AnalysisResult = await analyzer.analyze_async(
        "Te zdanie zawiera błąd."
    )
    return result.apply(issue_ids=())


async def correct_without_blocking_an_event_loop() -> str:
    analyzer = Analyzer.from_config("polis.toml")
    result = await analyzer.correct_async("Zeby zacząć, przyjdź jutro.")
    return result.corrected_text


def correction_result_exposes_active_policy_identity(
    result: polis.CorrectionResult,
) -> bool:
    return result.source_policy_version == "1.2" and all(
        outcome.source_policy_version == result.source_policy_version
        for outcome in result.suggestion_outcomes
    )


def root_result_as_core(
    result: polis.AnalysisResult,
) -> polis.core.AnalysisResult:
    return result


def core_result_as_root(
    result: polis.core.AnalysisResult,
) -> polis.AnalysisResult:
    return result


def analyzer_result_as_core(analyzer: Analyzer) -> polis.core.AnalysisResult:
    return analyzer.analyze("Tekst")


def analyzer_result_as_root(analyzer: Analyzer) -> polis.AnalysisResult:
    return analyzer.analyze("Tekst")


def morphology_status_exposes_public_provider_identities(
    analyzer: Analyzer,
) -> tuple[str, str, str | None]:
    status: polis.MorphologyStatus = analyzer.morphology_status
    expected: polis.MorphologyProviderIdentity = status.expected_identity
    actual = status.actual_identity
    return (
        status.state,
        expected.dictionary_id,
        None if actual is None else actual.dictionary_id,
    )


def classify_configuration_failure() -> tuple[str, bool, str]:
    try:
        Analyzer.from_config("missing.toml")
    except ConfigurationError as error:
        return error.code, error.retryable, error.context["path"]
    raise AssertionError("example expects a configuration failure")


def classify_backend_unavailability() -> tuple[str, bool, str]:
    try:
        Analyzer.from_config("polis.toml").analyze("Tekst")
    except BackendUnavailableError as error:
        return error.code, error.retryable, error.context["backend"]
    raise AssertionError("example expects backend unavailability")


def classify_timeout() -> tuple[str, bool, str]:
    try:
        Analyzer.from_config("polis.toml").analyze("Tekst")
    except AnalysisTimeoutError as error:
        return error.code, error.retryable, error.context["backend"]
    raise AssertionError("example expects an analysis timeout")


def classify_invalid_response() -> tuple[str, bool, str]:
    try:
        Analyzer.from_config("polis.toml").analyze("Tekst")
    except InvalidBackendResponseError as error:
        return error.code, error.retryable, error.context["backend"]
    raise AssertionError("example expects an invalid response")


def classify_unknown_finding() -> tuple[str, bool, str]:
    result = Analyzer.from_config("polis.toml").analyze("Tekst")
    try:
        result.apply(issue_ids=("finding_missing",))
    except UnknownFindingError as error:
        return error.code, error.retryable, error.context["finding_ids"]
    raise AssertionError("example expects an unknown finding")


def classify_uncorrectable_finding() -> tuple[str, bool, str]:
    result = Analyzer.from_config("polis.toml").analyze("Tekst")
    try:
        result.apply(issue_ids=(result.issues[0].id,))
    except UncorrectableFindingError as error:
        return error.code, error.retryable, error.context["finding_ids"]
    raise AssertionError("example expects an uncorrectable finding")


def classify_correction_conflict() -> tuple[str, bool, str]:
    result = Analyzer.from_config("polis.toml").analyze("Te zdanie")
    try:
        result.apply(issue_ids=("first", "second"))
    except CorrectionConflictError as error:
        return error.code, error.retryable, error.context["finding_ids"]
    raise AssertionError("example expects a correction conflict")


def classify_all_controlled_failures(error: PolisError) -> tuple[str, bool, str]:
    return error.code, error.retryable, error.context["operation"]
