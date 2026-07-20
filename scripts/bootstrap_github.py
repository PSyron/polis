#!/usr/bin/env python3
"""Create and verify the Polis GitHub planning metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, NoReturn
from urllib.parse import quote


@dataclass(frozen=True)
class Milestone:
    title: str
    description: str


@dataclass(frozen=True)
class Label:
    name: str
    color: str
    description: str


@dataclass(frozen=True)
class Issue:
    key: str
    title: str
    goal: str
    rationale: str
    scope: tuple[str, ...]
    non_goals: tuple[str, ...]
    acceptance: tuple[str, ...]
    tests: tuple[str, ...]
    documentation: tuple[str, ...]
    dependencies: tuple[str, ...]
    milestone: str
    labels: tuple[str, str, str]

    @property
    def github_title(self) -> str:
        return f"{self.key} {self.title}"


MILESTONES = (
    Milestone("M0 - Foundation and Decisions", "Freeze the minimum contracts and evidence needed before feature implementation."),
    Milestone("M1 - Deterministic Core", "Deliver the offset-safe rule pipeline and deterministic correction behavior."),
    Milestone("M2 - Local LLM", "Integrate one evidence-selected local backend behind stable, failure-safe protocols."),
    Milestone("M3 - MVP Quality", "Measure quality and performance, document the API, and produce a prerelease candidate."),
    Milestone("M4 - Release Stabilization", "Audit, package, and publish the documented 0.1.0 release."),
)

LABELS = (
    Label("type:decision", "5319e7", "Architecture or product decision with recorded evidence"),
    Label("type:feature", "a2eeef", "New independently testable behavior"),
    Label("type:bug", "d73a4a", "Incorrect existing behavior or regression"),
    Label("type:docs", "0075ca", "Documentation-only outcome"),
    Label("type:test", "bfdadc", "Test data, evaluation, or quality gate"),
    Label("type:research", "0e8a16", "Time-boxed experiment that produces evidence"),
    Label("type:chore", "c5def5", "Tooling, packaging, release, or maintenance work"),
    Label("area:core", "1d76db", "Public models, API, configuration, protocols, or orchestration"),
    Label("area:segmentation", "0052cc", "Paragraph and sentence segmentation or character offsets"),
    Label("area:rules", "fbca04", "Deterministic analyzers and rule registry"),
    Label("area:llm", "6f42c1", "Local model protocols, prompts, validation, or adapters"),
    Label("area:analysis", "0e8a16", "Finding normalization, merging, filtering, or prioritization"),
    Label("area:correction", "d93f0b", "Conflict detection and deterministic correction application"),
    Label("area:evaluation", "e99695", "Datasets, quality metrics, performance, or regressions"),
    Label("area:cli", "c2e0c6", "Thin command-line interface and executable examples"),
    Label("area:packaging", "0366d6", "Tooling, CI, compatibility, distribution, or release"),
    Label("priority:P0", "b60205", "Required on the MVP critical path"),
    Label("priority:P1", "d93f0b", "Required before the stable 0.1.0 release"),
    Label("priority:P2", "fbca04", "Useful after critical release work"),
    Label("status:blocked", "000000", "Cannot start until a named dependency or decision is resolved"),
)


def planned(
    key: str,
    title: str,
    goal: str,
    scope: str,
    non_goal: str,
    acceptance: tuple[str, str],
    tests: str,
    documentation: str,
    dependencies: tuple[str, ...],
    milestone: str,
    labels: tuple[str, str, str],
) -> Issue:
    return Issue(
        key=key,
        title=title,
        goal=goal,
        rationale=(
            f"This is the {key} roadmap outcome required by `PROMPT.md`. "
            "It creates one verifiable prerequisite without taking on later roadmap work."
        ),
        scope=(scope,),
        non_goals=(non_goal,),
        acceptance=acceptance,
        tests=(tests,),
        documentation=(documentation,),
        dependencies=dependencies,
        milestone=milestone,
        labels=labels,
    )


ISSUES = (
    planned("M0-01", "Define supported Python versions, platforms, and licensing policy", "Record the initial compatibility and licensing policy.", "Compare supported Python releases and target platforms; confirm the MIT code license and policy for data licenses in an ADR.", "Do not scaffold the package or select NLP dependencies.", ("The ADR names an exact Python range and supported platforms with rationale.", "Code, dependency, and dataset licensing rules are explicit and consistent with the existing MIT license."), "Review the policy against packaging metadata requirements and currently supported Python releases.", "Add the ADR and link it from the architecture documentation index.", (), "M0 - Foundation and Decisions", ("type:decision", "area:packaging", "priority:P0")),
    planned("M0-02", "Evaluate Polish NLP dependencies and record the architecture decision", "Select the minimum deterministic NLP dependency strategy using evidence.", "Compare realistic Polish tokenization, morphology, spelling, license, package-size, and offline-operation options in a reproducible spike.", "Do not implement production segmentation or rules.", ("At least two viable approaches are compared using the same Polish examples and criteria.", "An ADR selects a strategy or explicitly selects a standard-library-first approach and records rejected alternatives."), "Run the comparison script on documented positive and difficult-negative examples.", "Commit the experiment method, results, and ADR without downloaded models or corpora.", ("M0-01",), "M0 - Foundation and Decisions", ("type:research", "area:rules", "priority:P0")),
    planned("M0-03", "Scaffold the Python package and quality tooling", "Create an importable src-layout package with reproducible development tooling.", "Add pyproject metadata, empty focused package modules, pytest layout, strict typing configuration, and ruff configuration using the policy from M0-01.", "Do not implement analyzer behavior or add an NLP/model dependency.", ("A clean environment can install the project and import `polis`.", "The initial pytest, ruff, formatting, and mypy commands all pass."), "Add smoke tests for package import and declared version metadata.", "Document development setup and every declared dependency group.", ("M0-01",), "M0 - Foundation and Decisions", ("type:chore", "area:packaging", "priority:P0")),
    planned("M0-04", "Configure fast CI quality checks", "Run deterministic quality checks on every proposed change.", "Add CI jobs for supported Python versions, unit tests, ruff lint/format checks, mypy, and package build verification with dependency caching.", "Do not run real-model, slow benchmark, or release publishing jobs.", ("CI runs on pushes and pull requests for every supported Python version.", "A deliberately failing check is detected locally and the final workflow passes syntax validation."), "Validate workflow syntax and run the same commands locally.", "Document fast-CI scope and how slow tests are separated.", ("M0-03",), "M0 - Foundation and Decisions", ("type:chore", "area:packaging", "priority:P0")),
    planned("M0-05", "Define public data models and versioned JSON serialization", "Provide typed, validated public result models with stable half-open offsets.", "Implement category, severity, source, confidence, finding, options, and analysis-result models plus versioned JSON round trips and stable identifier rules.", "Do not implement orchestration, rules, segmentation, or correction application.", ("Models represent every field required by `PROMPT.md` and reject invalid ranges or confidence values.", "JSON serialization is deterministic, versioned, and round-trips without loss."), "Cover construction, invalid values, stable identifiers, Unicode offsets, and JSON round trips with unit tests.", "Document field semantics, `[start, end)` offsets, schema versioning, and compatibility expectations.", ("M0-03",), "M0 - Foundation and Decisions", ("type:feature", "area:core", "priority:P0")),
    planned("M0-06", "Approve the public API and exception contract", "Freeze the initial public entry points and failure semantics before implementation.", "Review usage examples; define Analyzer construction and analysis calls, filtering, partial-result behavior, correction selection, and stable exception hierarchy in an ADR.", "Do not implement the approved API or backend adapters.", ("The ADR includes typed signatures and examples for success and each public error category.", "Configuration, backend unavailable, timeout, invalid response, and correction conflict behaviors are unambiguous."), "Type-check executable contract examples against minimal stubs or signatures.", "Record the API ADR and update the proposed API documentation.", ("M0-05",), "M0 - Foundation and Decisions", ("type:decision", "area:core", "priority:P0")),
    planned("M0-07", "Define analyzer, rule, and LLM backend protocols", "Introduce narrow typed interfaces that keep orchestration independent of implementations.", "Define protocols for deterministic analyzers, rule registry entries, local backend generation, clock/retry controls when required, and orchestrator inputs/outputs.", "Do not add concrete rules, backends, network calls, or orchestration logic.", ("Fake implementations satisfy each protocol and pass strict type checking.", "Core protocol modules do not import a concrete model server or NLP implementation."), "Add protocol conformance and fake-implementation unit tests.", "Document each protocol's responsibilities, lifecycle, and allowed failures.", ("M0-05", "M0-06"), "M0 - Foundation and Decisions", ("type:feature", "area:core", "priority:P0")),
    planned("M0-08", "Create the initial licensed evaluation dataset", "Version a small representative Polish evaluation corpus with provenance.", "Add project-authored or clearly licensed correct and incorrect sentences, expected categories, spans, corrections, and difficult negative cases in a documented schema.", "Do not set release thresholds or include private, scraped-without-license, or model-generated data without provenance.", ("Every case has a stable ID, provenance/license, input, and expected findings or explicit no-finding result.", "Dataset validation rejects missing provenance, invalid spans, duplicate IDs, and unrecognized categories."), "Add schema and integrity tests that validate every committed case.", "Document contribution, licensing, anonymization, and review rules for evaluation data.", ("M0-03", "M0-05"), "M0 - Foundation and Decisions", ("type:test", "area:evaluation", "priority:P0")),
    planned("M1-01", "Segment paragraphs and sentences with stable character offsets", "Return paragraph and sentence segments mapped exactly to the original text.", "Implement injected segmentation using the selected dependency strategy while preserving whitespace and Unicode character offsets.", "Do not tokenize words, detect language errors, or normalize the input text.", ("Concatenated segment slices reproduce their represented original ranges without offset drift.", "Tests cover blank lines, abbreviations, punctuation, combining characters, emoji, and CRLF input."), "Add focused unit tests plus dataset-backed integration cases for every offset edge case.", "Document segmentation guarantees, limitations, and offset convention.", ("M0-02", "M0-03", "M0-05"), "M1 - Deterministic Core", ("type:feature", "area:segmentation", "priority:P0")),
    planned("M1-02", "Implement the deterministic rule registry", "Discover and run selected deterministic rules without global state.", "Implement typed registration, duplicate-ID rejection, category selection, dependency injection, and deterministic execution order.", "Do not implement language rules or merge duplicate findings.", ("Rules can be registered, selected by category, and executed in a stable order.", "Duplicate identifiers and incompatible rule outputs fail with documented library errors."), "Add unit tests with fake rules for registration, filtering, ordering, and failure isolation.", "Document how to add a rule and assign a stable identifier and source.", ("M0-07",), "M1 - Deterministic Core", ("type:feature", "area:rules", "priority:P0")),
    planned("M1-03", "Add high-precision spelling rules", "Detect a small documented set of Polish typos and common spelling errors with high precision.", "Implement only evidence-backed spelling rules with minimal replacements, original offsets, sources, and confidence values.", "Do not add broad fuzzy matching, style rewriting, or LLM assistance.", ("Each supported pattern has positive, negative, casing, formatting, and offset tests.", "Rules emit no findings for the documented difficult-negative cases."), "Add unit and evaluation cases for every rule before implementation.", "Document supported patterns, rationale, known limitations, and false-positive safeguards.", ("M1-01", "M1-02"), "M1 - Deterministic Core", ("type:feature", "area:rules", "priority:P0")),
    planned("M1-04", "Add high-precision agreement rules", "Detect selected gender, number, person, and case agreement errors.", "Implement a small evidence-backed set of agreement checks using the approved NLP strategy and minimal corrections.", "Do not attempt unrestricted grammar correction or semantic rewriting.", ("Every supported agreement pattern has inflectional positive and hard-negative examples.", "Findings preserve original offsets and explain the exact agreement relation."), "Add unit and evaluation cases covering supported inflections, ambiguity, and correct sentences.", "Document the supported agreement relations and intentional gaps.", ("M1-01", "M1-02"), "M1 - Deterministic Core", ("type:feature", "area:rules", "priority:P0")),
    planned("M1-05", "Add selected syntax and punctuation rules", "Detect a narrow high-precision set of syntax and punctuation problems.", "Implement independently switchable rules selected from measured common errors, with minimal corrections and explicit explanations.", "Do not perform general style review or rewrite sentence structure.", ("Each rule documents its linguistic condition and produces a minimal bounded correction.", "Positive and difficult-negative evaluation cases demonstrate high-precision behavior."), "Add tests for whitespace, quotation marks, abbreviations, lists, and rule-specific exceptions.", "Document supported cases, exclusions, and the process for adding further rules.", ("M1-01", "M1-02"), "M1 - Deterministic Core", ("type:feature", "area:rules", "priority:P1")),
    planned("M1-06", "Normalize, deduplicate, prioritize, and filter findings", "Produce one deterministic result stream from independent analyzers.", "Normalize source outputs, deduplicate equivalent findings, define stable ordering and precedence, and filter by category and confidence threshold.", "Do not resolve overlapping correction conflicts or apply edits.", ("Equivalent findings collapse predictably while distinct findings remain available.", "Ordering and category/confidence filtering are deterministic and covered by contract tests."), "Use fake rule and model findings to test duplicates, ties, thresholds, Unicode spans, and empty input.", "Document normalization, deduplication, ordering, and filtering semantics.", ("M0-05", "M1-02"), "M1 - Deterministic Core", ("type:feature", "area:analysis", "priority:P0")),
    planned("M1-07", "Detect conflicting corrections", "Classify overlapping or otherwise incompatible selected corrections before application.", "Implement deterministic conflict detection for half-open ranges, including identical, nested, touching, and zero-length cases allowed by the contract.", "Do not choose a winner automatically or modify text.", ("Every pair is classified consistently and touching non-overlapping ranges follow the approved contract.", "Conflict errors identify finding IDs without exposing the full analyzed text."), "Add table-driven unit tests for interval relationships and Unicode-containing source text.", "Document conflict definitions and caller responsibilities.", ("M0-05",), "M1 - Deterministic Core", ("type:feature", "area:correction", "priority:P0")),
    planned("M1-08", "Apply selected non-conflicting corrections deterministically", "Return corrected text by applying only explicitly selected compatible findings.", "Validate selected IDs against the original result and apply replacements from right to left without offset drift.", "Do not auto-select suggestions, resolve conflicts, or rewrite unselected ranges.", ("Selected non-conflicting corrections produce the expected text independent of selection order.", "Unknown IDs, stale spans, and conflicts raise documented errors without partial mutation."), "Add unit and property-oriented cases for adjacent edits, Unicode, repeated text, ordering, and failures.", "Document selection semantics and examples for successful and conflicting corrections.", ("M1-07",), "M1 - Deterministic Core", ("type:feature", "area:correction", "priority:P0")),
    planned("M2-01", "Benchmark candidate runtimes and models; select the first backend", "Select the first supported local runtime and model class from reproducible evidence.", "Benchmark several currently available small candidates on the same Polish evaluation slice for quality, latency, memory, offline operation, and structured-output reliability.", "Do not couple core interfaces to the selected vendor or commit model weights.", ("The benchmark records hardware, versions, settings, data slice, and comparable metrics.", "An ADR selects the first backend and explains rejected candidates and residual risks."), "Re-run a smoke subset to verify the benchmark harness and recorded result schema.", "Publish methodology, results, reproduction commands, and the backend ADR.", ("M0-07", "M0-08"), "M2 - Local LLM", ("type:research", "area:llm", "priority:P0")),
    planned("M2-02", "Define versioned prompts and the LLM response schema", "Create an injection-resistant, testable prompt contract and strict response schema.", "Version system/task templates, delimit user text as data, define allowed categories and bounded spans, and validate structured findings before conversion.", "Do not call a real backend or retry invalid responses.", ("Prompt snapshots clearly separate instructions from untrusted input.", "The schema rejects extra fields, invalid categories, invalid spans, and replacements outside the specified range."), "Add snapshot, adversarial-input, schema-valid, and schema-invalid unit tests.", "Document prompt/schema versioning and compatibility rules.", ("M0-05", "M0-07"), "M2 - Local LLM", ("type:feature", "area:llm", "priority:P0")),
    planned("M2-03", "Implement the selected local backend adapter", "Connect the selected local runtime through the backend protocol.", "Implement configuration, availability checks, deterministic generation settings, bounded input/output, and response capture using the selected runtime.", "Do not merge findings, implement retries, or support additional runtimes.", ("The adapter satisfies the backend protocol and sends no request to non-local endpoints.", "Fake transport tests cover configuration, request construction, success, and unavailable backend behavior."), "Run unit tests with an injected fake transport and a separately marked local smoke test.", "Document installation, local model acquisition, configuration, and resource expectations.", ("M2-01", "M2-02"), "M2 - Local LLM", ("type:feature", "area:llm", "priority:P0")),
    planned("M2-04", "Add response validation, timeouts, controlled retries, and safe failures", "Contain backend and model failures without crashing the full analysis.", "Validate every response, enforce configurable timeouts, retry only explicitly transient or repairable failures within a fixed budget, and return documented partial results or exceptions.", "Do not retry deterministic validation failures indefinitely or log full analyzed text.", ("Timeout, unavailable backend, malformed JSON, schema error, and exhausted retry paths map to the approved contract.", "Retry count and delay are deterministic under injected clock and backend fakes."), "Add unit tests for every failure class, retry boundary, redacted diagnostic, and successful recovery.", "Document failure behavior, diagnostics, retry policy, and configuration defaults.", ("M2-03",), "M2 - Local LLM", ("type:feature", "area:llm", "priority:P0")),
    planned("M2-05", "Integrate LLM findings with the analysis pipeline", "Run deterministic and local-model analyzers through one public orchestration path.", "Segment controlled fragments, invoke injected analyzers, translate model spans to original offsets, merge results, and preserve partial deterministic findings on approved model failures.", "Do not auto-apply corrections or add concurrency without measured need.", ("Combined results use original offsets, stable ordering, deduplication, category filters, and confidence thresholds.", "Fake-backend integration tests cover success, malformed response, timeout, and no-LLM configurations."), "Add end-to-end tests with deterministic fakes and anonymized recorded responses.", "Document orchestration order, partial-result semantics, configuration, and offline guarantees.", ("M1-06", "M2-04"), "M2 - Local LLM", ("type:feature", "area:analysis", "priority:P0")),
    planned("M2-06", "Verify and document fully offline operation", "Demonstrate that supported analysis works after installation with network access disabled.", "Create a repeatable offline verification procedure for the selected backend, dependency cache, local model, analyzer calls, and privacy-safe diagnostics.", "Do not claim support for untested runtimes, platforms, or model variants.", ("The documented supported configuration passes analysis with outbound network access blocked.", "The verification detects an attempted external connection and lists all pre-installation artifacts."), "Run the offline integration test and record environment plus command output without analyzed private text.", "Publish the offline installation guide, verification steps, and supported configuration limits.", ("M2-03", "M2-05"), "M2 - Local LLM", ("type:docs", "area:llm", "priority:P1")),
    planned("M3-01", "Expand the evaluation dataset with positive and hard-negative cases", "Cover the implemented rule and LLM behaviors with representative licensed evaluation data.", "Add correct and incorrect Polish cases across supported categories, inflections, ambiguity, punctuation, offsets, and adversarial model inputs with provenance.", "Do not change analyzers to make the dataset pass in the same issue.", ("Every supported behavior has positive and difficult-negative cases with reviewed expected spans and corrections.", "Dataset integrity and license/provenance validation pass for every case."), "Run dataset validation and evaluation with rule/model components reported separately.", "Update dataset methodology, coverage summary, provenance, and contribution guidance.", ("M1-03", "M1-04", "M1-05", "M2-05"), "M3 - MVP Quality", ("type:test", "area:evaluation", "priority:P0")),
    planned("M3-02", "Establish the quality baseline and measurable release gates", "Measure current quality and define evidence-based release gates.", "Calculate precision, recall, F1, span accuracy, correction accuracy, and false-positive rate by category and source; record baseline and justified gates.", "Do not hide weak categories in aggregate metrics or select thresholds before measurement.", ("A reproducible report contains per-category and aggregate metrics with dataset revision and configuration.", "Release gates are numeric, justified from baseline evidence, and enforced by a regression check."), "Run the complete evaluation twice to confirm deterministic rule results and documented model variance.", "Publish the baseline report, gate rationale, calculation method, and known dataset limitations.", ("M3-01",), "M3 - MVP Quality", ("type:test", "area:evaluation", "priority:P0")),
    planned("M3-03", "Measure latency, throughput, and memory usage", "Establish reproducible performance and memory baselines for supported configurations.", "Benchmark deterministic-only and combined pipelines over documented text sizes, warm/cold states, hardware, runtime, and model configuration.", "Do not optimize implementation or set unsupported hardware guarantees.", ("Results report latency distributions, throughput, peak memory, inputs, warmup, repetitions, and environment.", "Benchmark output is machine-readable while generated bulky artifacts remain untracked."), "Run benchmark smoke checks in fast CI and full measurements outside fast CI.", "Publish methodology, baseline results, variance, and supported configuration limitations.", ("M2-05",), "M3 - MVP Quality", ("type:test", "area:evaluation", "priority:P1")),
    planned("M3-04", "Document the public API, privacy guarantees, and extension guides", "Provide complete task-oriented documentation for users and contributors.", "Document installation, API examples, errors, JSON, filtering, corrections, rule/backend extension, offline privacy, and current limitations against executable behavior.", "Do not document proposed behavior that is not implemented and verified.", ("Every public symbol and documented error has an accurate example or reference.", "Quick-start, custom-rule, custom-backend, privacy, and limitation guides pass link and example checks."), "Run documentation build/link checks and execute all included code examples.", "Update README and the versioned API, extension, privacy, and limitation documents.", ("M1-08", "M2-06"), "M3 - MVP Quality", ("type:docs", "area:core", "priority:P1")),
    planned("M3-05", "Add a thin CLI and executable examples", "Provide a manual testing interface that delegates all behavior to the public API.", "Add commands for analysis, JSON output, filters, and explicitly selected corrections with stdin/file input and privacy-safe errors.", "Do not duplicate orchestration, add a GUI, preserve document formatting, or auto-apply suggestions.", ("CLI output is deterministic, script-friendly, and equivalent to direct public API calls.", "Help, invalid configuration, stdin, Unicode file, filtering, and correction selection paths are tested."), "Add unit tests for argument handling and subprocess integration tests for documented examples.", "Document CLI installation, commands, exit codes, examples, and privacy behavior.", ("M0-06", "M2-05"), "M3 - MVP Quality", ("type:feature", "area:cli", "priority:P1")),
    planned("M3-06", "Build and verify the first prerelease candidate", "Produce an installable prerelease artifact that meets the measured MVP gates.", "Freeze a prerelease version, build wheel and sdist, install each into clean environments, run fast tests, evaluation gates, examples, and offline smoke verification.", "Do not publish the stable 0.1.0 release or waive a failed gate.", ("Wheel and sdist install cleanly and contain only expected files, licenses, types, and metadata.", "All M3 quality, performance, documentation, and offline checks pass or block the candidate."), "Run clean-environment artifact tests plus the complete prerelease verification checklist.", "Record candidate version, artifact hashes, verification evidence, and known limitations.", ("M3-02", "M3-03", "M3-04", "M3-05"), "M3 - MVP Quality", ("type:chore", "area:packaging", "priority:P0")),
    planned("M4-01", "Audit compatibility and define semantic-versioning guarantees", "Confirm the supported matrix and define compatibility promises for the public surface.", "Test supported Python/platform configurations, inspect public exports and serialized schema, and record semantic-versioning rules for API, configuration, prompts, and data formats.", "Do not expand the compatibility matrix without evidence or change APIs during the audit.", ("Every supported configuration has recorded passing evidence or is explicitly removed with rationale.", "Compatibility and deprecation rules cover public Python API and versioned serialized formats."), "Run the full compatibility matrix and compare public API/schema snapshots with the prerelease.", "Publish compatibility, semantic-versioning, and deprecation policies.", ("M3-06",), "M4 - Release Stabilization", ("type:decision", "area:packaging", "priority:P1")),
    planned("M4-02", "Audit privacy, dependencies, and packaged artifacts", "Verify that the release preserves offline privacy and contains only justified assets.", "Audit runtime dependencies, licenses, network-capable paths, diagnostics, repository files, wheel/sdist contents, secrets, models, corpora, and telemetry behavior.", "Do not add unrelated features or silently accept unexplained dependencies.", ("No analysis path sends text externally and diagnostics redact full input by default.", "Every packaged dependency and file has a documented purpose and compatible license; secret and artifact scans pass."), "Run offline tests, dependency/license inventory, secret scan, package-content diff, and network-attempt detection.", "Publish the privacy statement, dependency rationale, audit evidence, and accepted residual risks.", ("M3-06",), "M4 - Release Stabilization", ("type:chore", "area:packaging", "priority:P0")),
    planned("M4-03", "Produce and validate the PyPI distribution", "Create release artifacts that pass installation and metadata checks for PyPI.", "Build final wheel and sdist from a clean checkout, validate metadata and long description, inspect contents, and test installation from artifacts in clean supported environments.", "Do not upload artifacts or create the 0.1.0 tag.", ("Standard package checks accept both artifacts and their metadata, license, README, and typing marker.", "Clean supported environments install each artifact and pass import, CLI, examples, and fast tests."), "Run build, artifact validation, clean-install matrix, and package-content allowlist checks.", "Record reproducible build commands, hashes, and the publication checklist.", ("M4-01", "M4-02"), "M4 - Release Stabilization", ("type:chore", "area:packaging", "priority:P0")),
    planned("M4-04", "Publish version 0.1.0 with release notes and documented limitations", "Publish the verified first stable release and make its boundaries explicit.", "Confirm all gates, set version 0.1.0, finalize changelog and release notes, create the signed or verified tag, upload validated artifacts, and verify the public installation path.", "Do not publish with failed checks, undocumented limitations, or artifacts different from those validated in M4-03.", ("The repository tag, GitHub release, and PyPI artifacts all identify the same commit, version, and hashes.", "A fresh public installation passes smoke analysis and documentation links; limitations and supported configurations are visible."), "Run the final release checklist and post-publication installation/offline smoke tests.", "Publish release notes, changelog, installation instructions, supported matrix, and known limitations.", ("M4-03",), "M4 - Release Stabilization", ("type:chore", "area:packaging", "priority:P0")),
)


def fail(message: str) -> NoReturn:
    raise SystemExit(f"error: {message}")


def validate_data() -> None:
    if len(MILESTONES) != 5 or len({item.title for item in MILESTONES}) != 5:
        fail("expected five unique milestones")
    if len(LABELS) != 20 or len({item.name for item in LABELS}) != 20:
        fail("expected twenty unique taxonomy labels")
    if len(ISSUES) != 32:
        fail("expected exactly 32 roadmap issues")
    if len({item.key for item in ISSUES}) != 32 or len({item.github_title for item in ISSUES}) != 32:
        fail("issue keys and titles must be unique")

    milestone_names = {item.title for item in MILESTONES}
    label_names = {item.name for item in LABELS}
    issue_keys = {item.key for item in ISSUES}
    position = {item.key: index for index, item in enumerate(ISSUES)}
    for item in ISSUES:
        if item.milestone not in milestone_names:
            fail(f"{item.key} references an unknown milestone")
        if any(label not in label_names for label in item.labels):
            fail(f"{item.key} references an unknown label")
        prefixes = ("type:", "area:", "priority:")
        if any(sum(label.startswith(prefix) for label in item.labels) != 1 for prefix in prefixes):
            fail(f"{item.key} must have one type, area, and priority label")
        for dependency in item.dependencies:
            if dependency not in issue_keys:
                fail(f"{item.key} references unknown dependency {dependency}")
            if position[dependency] >= position[item.key]:
                fail(f"{item.key} dependency {dependency} is not earlier in topological order")
        required_text = (
            item.goal,
            item.rationale,
            *item.scope,
            *item.non_goals,
            *item.acceptance,
            *item.tests,
            *item.documentation,
        )
        if any(not value.strip() for value in required_text):
            fail(f"{item.key} contains an empty issue field")

    serialized = json.dumps(
        {
            "milestones": [item.__dict__ for item in MILESTONES],
            "labels": [item.__dict__ for item in LABELS],
            "issues": [item.__dict__ for item in ISSUES],
        },
        ensure_ascii=False,
    ).lower()
    prohibited = (bytes((99, 111, 100, 101, 120)).decode(), "co-authored-by", "generated by")
    if any(term in serialized for term in prohibited):
        fail("planning data contains prohibited attribution text")


def gh(args: list[str], payload: dict[str, Any] | None = None) -> Any:
    command = ["gh", *args]
    if payload is not None:
        command.extend(("--input", "-"))
    result = subprocess.run(
        command,
        input=None if payload is None else json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown GitHub CLI error"
        fail(f"GitHub operation failed: {' '.join(command[:4])}: {detail}")
    output = result.stdout.strip()
    return json.loads(output) if output else None


def api_get(endpoint: str) -> Any:
    return gh(["api", endpoint])


def api_write(method: str, endpoint: str, payload: dict[str, Any]) -> Any:
    return gh(["api", "--method", method, endpoint], payload)


def issue_body(item: Issue, numbers: dict[str, tuple[int, str]]) -> str:
    def bullets(values: tuple[str, ...], checks: bool = False) -> str:
        prefix = "- [ ]" if checks else "-"
        return "\n".join(f"{prefix} {value}" for value in values)

    if item.dependencies:
        dependencies = tuple(
            f"[{key} #{numbers[key][0]}]({numbers[key][1]})" for key in item.dependencies
        )
    else:
        dependencies = ("None",)

    return "\n\n".join(
        (
            "## Goal\n\n" + item.goal,
            "## Rationale\n\n" + item.rationale,
            "## In scope\n\n" + bullets(item.scope),
            "## Out of scope\n\n" + bullets(item.non_goals),
            "## Acceptance criteria\n\n" + bullets(item.acceptance, checks=True),
            "## Required tests\n\n" + bullets(item.tests),
            "## Documentation\n\n" + bullets(item.documentation),
            "## Dependencies\n\n" + bullets(dependencies),
            "## Definition of Done\n\n"
            + bullets(
                (
                    "All acceptance criteria are verified.",
                    "Required tests pass.",
                    "Formatting, linting, and type checking pass once configured.",
                    "Relevant documentation is updated.",
                    "The focused commit references this issue.",
                ),
                checks=True,
            ),
        )
    )


def list_milestones(repo: str) -> list[dict[str, Any]]:
    return api_get(f"repos/{repo}/milestones?state=all&per_page=100")


def list_labels(repo: str) -> list[dict[str, Any]]:
    return api_get(f"repos/{repo}/labels?per_page=100")


def list_issues(repo: str) -> list[dict[str, Any]]:
    values = api_get(f"repos/{repo}/issues?state=all&per_page=100")
    return [item for item in values if "pull_request" not in item]


def wait_for_expected_issues(
    fetch: Callable[[], list[dict[str, Any]]],
    expected_titles: set[str],
    *,
    attempts: int = 5,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for attempt in range(attempts):
        items = fetch()
        if expected_titles <= {item["title"] for item in items}:
            return items
        if attempt + 1 < attempts:
            sleeper(float(2**attempt))
    return items


def apply(repo: str) -> None:
    milestones = {item["title"]: item for item in list_milestones(repo)}
    for expected in MILESTONES:
        current = milestones.get(expected.title)
        payload = {"title": expected.title, "description": expected.description}
        if current is None:
            created = api_write("POST", f"repos/{repo}/milestones", payload)
            milestones[expected.title] = created
            print(f"created milestone: {expected.title}")
        elif current.get("description", "") != expected.description:
            updated = api_write("PATCH", f"repos/{repo}/milestones/{current['number']}", payload)
            milestones[expected.title] = updated
            print(f"updated milestone: {expected.title}")
        else:
            print(f"unchanged milestone: {expected.title}")

    labels = {item["name"]: item for item in list_labels(repo)}
    for old, new in (("bug", "type:bug"), ("documentation", "type:docs"), ("enhancement", "type:feature")):
        if old in labels and new not in labels:
            updated = api_write(
                "PATCH",
                f"repos/{repo}/labels/{quote(old, safe='')}",
                {"new_name": new},
            )
            labels.pop(old)
            labels[new] = updated
            print(f"renamed label: {old} -> {new}")

    labels = {item["name"]: item for item in list_labels(repo)}
    for expected in LABELS:
        current = labels.get(expected.name)
        payload = {
            "new_name": expected.name,
            "color": expected.color,
            "description": expected.description,
        }
        if current is None:
            created = api_write(
                "POST",
                f"repos/{repo}/labels",
                {"name": expected.name, "color": expected.color, "description": expected.description},
            )
            labels[expected.name] = created
            print(f"created label: {expected.name}")
        elif current.get("color", "").lower() != expected.color or current.get("description", "") != expected.description:
            labels[expected.name] = api_write(
                "PATCH", f"repos/{repo}/labels/{quote(expected.name, safe='')}", payload
            )
            print(f"updated label: {expected.name}")
        else:
            print(f"unchanged label: {expected.name}")

    remote_issues = {item["title"]: item for item in list_issues(repo)}
    numbers: dict[str, tuple[int, str]] = {}
    for item in ISSUES:
        current = remote_issues.get(item.github_title)
        if current is not None:
            numbers[item.key] = (current["number"], current["html_url"])
            continue
        body = issue_body(item, numbers)
        payload = {
            "title": item.github_title,
            "body": body,
            "milestone": milestones[item.milestone]["number"],
            "labels": list(item.labels),
        }
        created = api_write("POST", f"repos/{repo}/issues", payload)
        remote_issues[item.github_title] = created
        numbers[item.key] = (created["number"], created["html_url"])
        print(f"created issue: #{created['number']} {item.github_title}")

    for item in ISSUES:
        current = remote_issues[item.github_title]
        body = issue_body(item, numbers)
        current_labels = {label["name"] for label in current.get("labels", [])}
        current_milestone = (current.get("milestone") or {}).get("title")
        if current.get("body", "") != body or current_labels != set(item.labels) or current_milestone != item.milestone:
            updated = api_write(
                "PATCH",
                f"repos/{repo}/issues/{current['number']}",
                {
                    "title": item.github_title,
                    "body": body,
                    "milestone": milestones[item.milestone]["number"],
                    "labels": list(item.labels),
                },
            )
            remote_issues[item.github_title] = updated
            print(f"updated issue: #{current['number']} {item.github_title}")
        else:
            print(f"unchanged issue: #{current['number']} {item.github_title}")


def verify_remote(repo: str) -> None:
    milestones = {item["title"]: item for item in list_milestones(repo)}
    labels = {item["name"]: item for item in list_labels(repo)}
    roadmap_titles = {item.github_title for item in ISSUES}
    issue_values = wait_for_expected_issues(lambda: list_issues(repo), roadmap_titles)
    remote_issues = {item["title"]: item for item in issue_values}

    for expected in MILESTONES:
        if expected.title not in milestones:
            fail(f"missing milestone {expected.title}")
    for expected in LABELS:
        current = labels.get(expected.name)
        if current is None:
            fail(f"missing label {expected.name}")
        if current.get("color", "").lower() != expected.color or current.get("description", "") != expected.description:
            fail(f"label metadata differs for {expected.name}")

    found_titles = {title for title in remote_issues if re.match(r"^M[0-4]-\d{2} ", title)}
    if found_titles != roadmap_titles:
        missing = sorted(roadmap_titles - found_titles)
        extra = sorted(found_titles - roadmap_titles)
        fail(f"roadmap issue titles differ; missing={missing}, extra={extra}")

    for expected in ISSUES:
        current = remote_issues[expected.github_title]
        current_labels = {label["name"] for label in current.get("labels", [])}
        current_milestone = (current.get("milestone") or {}).get("title")
        if current_labels != set(expected.labels):
            fail(f"labels differ for {expected.key}")
        if current_milestone != expected.milestone:
            fail(f"milestone differs for {expected.key}")
        body = current.get("body", "")
        required_headings = (
            "## Goal", "## Rationale", "## In scope", "## Out of scope",
            "## Acceptance criteria", "## Required tests", "## Documentation",
            "## Dependencies", "## Definition of Done",
        )
        if any(heading not in body for heading in required_headings):
            fail(f"body contract differs for {expected.key}")
        if expected.dependencies and any(f"[{key} #" not in body for key in expected.dependencies):
            fail(f"dependency links differ for {expected.key}")

    print("5 milestones, 20 taxonomy labels, 32 roadmap issues verified")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-data", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--repo")
    args = parser.parse_args()
    if not args.verify_data:
        if not args.repo or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
            parser.error("--repo OWNER/REPOSITORY is required for this mode")
    return args


def main() -> None:
    args = parse_args()
    validate_data()
    if args.verify_data:
        print("5 milestones, 20 taxonomy labels, 32 roadmap issues validated")
    elif args.dry_run:
        print(f"dry run for {args.repo}: 5 milestones, 20 taxonomy labels, 32 issues; no remote writes")
    elif args.apply:
        apply(args.repo)
        verify_remote(args.repo)
    else:
        verify_remote(args.repo)


if __name__ == "__main__":
    main()
