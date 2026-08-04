from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "PROMPT.md"
ADR = (
    ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / ("0020-runtime-first-product-charter.md")
)
ARCHITECTURE_INDEX = ROOT / "docs" / "architecture" / "README.md"
ROADMAP = ROOT / "docs" / "project" / "ROADMAP.md"
PORTFOLIO = ROOT / "docs" / "project" / "runtime-first-portfolio-disposition.md"
PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / ("2026-08-01-runtime-first-product-charter.md")
)

GOVERNED_RELEASE_DOCUMENTS = (
    pytest.param(ROOT / "README.md", id="readme"),
    pytest.param(ROOT / "docs" / "limitations.md", id="limitations"),
    pytest.param(ROOT / "docs" / "llm-quality-gates.md", id="llm-quality-gates"),
    pytest.param(ROOT / "docs" / "prerelease-candidate.md", id="prerelease"),
    pytest.param(ROOT / "docs" / "compatibility.md", id="compatibility"),
)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_PUNCTUATION_BOUNDARY = re.compile(r"\s*(?:[;:]|—)\s*")
_CONTRAST_BOUNDARY = re.compile(
    r"\s*(?:,\s*)?\b(?:even though|granted that|although|though|despite|but|"
    r"while|yet|however|nevertheless|nonetheless|whereas)\b(?:\s*,\s*|\s+)",
    flags=re.IGNORECASE,
)
_LEADING_CONCESSION = re.compile(
    r"^(?:even though|granted that|although|though|despite)\b\s*",
    flags=re.IGNORECASE,
)
_CURRENT_RELEASE_CLAUSE_BOUNDARY = re.compile(
    r"\s*(?:,\s*(?:and\s+)?|\band\s+)(?="
    r"(?:the\s+)?(?:current\s+|next\s+)?(?:(?:runtime|product)\s+)?"
    r"(?:releases?|publication|publishing|shipping|ships?)\b)",
    flags=re.IGNORECASE,
)


def _compile_concept_group(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns)


_RELEASE_CONCEPTS = _compile_concept_group(
    r"\breleases?\b",
    r"\bpublications?\b",
    r"\bpublish(?:es|ed|ing)?\b",
    r"\bprereleases?\b",
    r"\brelease[- ]candidates?\b",
    r"\bships?\b",
    r"\bshipped\b",
    r"\bshipping\b",
)

_PROHIBITED_MODEL_OR_LLM_CONCEPTS = _compile_concept_group(
    r"\bLLMs?\b",
    r"\b(?:a|the|any)\s+(?:(?:local|qualified)\s+)*"
    r"(?:language\s+)?models?\b",
    r"\b(?:local|qualified)(?:\s+(?:local|qualified))*\s+"
    r"(?:language\s+)?models?\b",
    r"\bmodel (?:servers?|backends?|runtimes?|artifacts?|providers?|rankers?)\b",
)

_PROHIBITED_OPTIONAL_RESEARCH_OR_QUALIFICATION_CONCEPTS = _compile_concept_group(
    r"\boptional\s+(?:(?:model|LLM)\s+)?research\b",
    r"\b(?:model|LLM)\s+(?:research|qualification)\b",
    r"\boptional\s+(?:(?:model|LLM)\s+)?qualification"
    r"(?:\s+(?:research|study|work))?\b",
    r"\bqualification\s+(?:research|study|work)\b",
)

_PROHIBITED_JAVA_OR_JVM_CONCEPTS = _compile_concept_group(
    r"\bJava\b",
    r"\bJVM\b",
)

_PROHIBITED_NETWORK_ACCESS_CONCEPTS = _compile_concept_group(
    r"\bnetwork (?:access|services?|availability|connectivity)\b",
)

_PROHIBITED_RESEARCH_CORPUS_OR_EVIDENCE_CONCEPTS = _compile_concept_group(
    r"\bresearch (?:corp(?:us|ora)|evidence)\b",
)

_PROHIBITED_CONSUMED_HOLDOUT_CONCEPTS = _compile_concept_group(
    r"\bconsumed holdouts?\b",
)

_PROHIBITED_LEGACY_RELEASE_AUTHORITY_CONCEPTS = _compile_concept_group(
    r"\bM5\b",
    r"#93\b",
)

_PROHIBITED_LEGACY_DEPENDENCY_CONCEPTS = _compile_concept_group(
    r"#(?:43|76)\b",
)

_PROHIBITED_PREREQUISITE_CONCEPT_GROUPS = (
    _PROHIBITED_MODEL_OR_LLM_CONCEPTS,
    _PROHIBITED_OPTIONAL_RESEARCH_OR_QUALIFICATION_CONCEPTS,
    _PROHIBITED_JAVA_OR_JVM_CONCEPTS,
    _PROHIBITED_NETWORK_ACCESS_CONCEPTS,
    _PROHIBITED_RESEARCH_CORPUS_OR_EVIDENCE_CONCEPTS,
    _PROHIBITED_CONSUMED_HOLDOUT_CONCEPTS,
    _PROHIBITED_LEGACY_RELEASE_AUTHORITY_CONCEPTS,
    _PROHIBITED_LEGACY_DEPENDENCY_CONCEPTS,
)

_EXPLICIT_NON_BLOCKING_CONTEXTS = _compile_concept_group(
    r"\b(?:does|do|did) not (?:(?:execute|run) or )?"
    r"(?:require|block|depend (?:on|upon)|wait for)\b",
    r"\bnever blocks?\b",
    r"\bcannot block\b",
    r"\bno longer depends? (?:on|upon)\b",
    r"\bneed not (?:wait for|await)\b",
    r"\b(?:is|are|was|were) no (?:release )?prerequisites?\b",
    r"\bno (?:(?:current|runtime|product|release|publication|shipping)[- ]+)*"
    r"(?:dependenc(?:y|ies)|prerequisites?|conditions?|gates?|blockers?|authority)\b",
    r"\b(?:is|are|was|were) not (?:directly )?"
    r"(?:contingent|dependent|conditional)(?: (?:on|upon))?\b",
    r"\b(?:is|are|was|were) not (?:(?:an?|the) )?"
    r"(?:(?:current|runtime|product|release|publication|shipping)[- ]+)*"
    r"(?:dependenc(?:y|ies)|prerequisites?|conditions?|gates?|gatekeepers?|"
    r"blockers?|authorit(?:y|ies))\b",
    r"\bwithout\b[^.;:—]{0,80}\b(?:becoming|being|making)\b"
    r"[^.;:—]{0,80}\b(?:dependenc(?:y|ies)|prerequisites?|conditions?|gates?|"
    r"blockers?|authority)\b",
    r"\bmust not become\b[^.;:—]{0,80}\bdependenc(?:y|ies)\b",
    r"\bindependent (?:of|from)\b",
    r"\b(?:is|are|remains?|stays?) non[- ]blocking\b",
    r"\bnon[- ]blocking (?:for|to)\b",
    r"\b(?:has|have|had) not (?:passed|met|cleared|satisfied)\b"
    r"[^.;:—]{0,80}\b(?:release|publication|shipping)?[- ]?gates?\b",
)

_EXPLICIT_SUPERSESSION_CONTEXTS = _compile_concept_group(
    r"\b(?:is|are|was|were|has been|have been) (?:explicitly )?"
    r"(?:archived|obsolete|retired|superseded)\b",
    r"\b(?:superseded|replaced) by ADR-\d+\b",
)

_CURRENT_POLICY_SCOPE = _compile_concept_group(
    r"\bcurrent(?:ly)?\b",
    r"\bstill\b",
    r"\bnow\b",
    r"\bremains?\b",
    r"\bcontinues?\b",
)

_PAST_AUXILIARY_AUTHORITY = _compile_concept_group(
    r"\b(?:was|were|had been)\b[^.;:—]{0,40}\b"
    r"(?:authoritative|authority|prerequisite|condition|gate|gatekeeper|blocker|"
    r"dependent|conditional|contingent|predicated|governed|controlled|required|"
    r"blocked)\b",
)
_SIMPLE_PAST_AUTHORITY_VERB = re.compile(
    r"\b(?:governed|controlled|decided|determined|depended|rested|hinged|served|"
    r"treated|recorded|made|required|blocked)\b",
    flags=re.IGNORECASE,
)
_PRESENT_OR_CONTINUING_AUXILIARY = re.compile(
    r"\b(?:is|are|has|have|remains?|continues?)\s+$",
    flags=re.IGNORECASE,
)


def _matches_concept_group(unit: str, group: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(unit) for pattern in group)


def assert_no_runtime_release_dependency_conflict(document: str) -> None:
    """Reject ambiguous release/prerequisite co-occurrence unless clearly safe.

    This policy deliberately fails closed: relation wording is not part of the
    risk predicate. Authors must state a scoped negative or historical context
    explicitly rather than relying on a dependency synonym the checker knows.
    """

    for unit in _release_policy_units(document):
        if not _is_conservative_release_dependency_risk(unit):
            continue
        if _has_explicit_non_blocking_scope(unit):
            continue
        if _has_historical_policy_scope(unit):
            continue
        msg = f"release dependency policy violation: {unit}"
        raise AssertionError(msg)


def _release_policy_units(document: str) -> tuple[str, ...]:
    """Return independently classified clauses without sharing safe context."""

    units: list[str] = []
    for raw_line in document.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        for sentence in _SENTENCE_BOUNDARY.split(line):
            units.extend(_policy_units_from_sentence(sentence))
    return tuple(dict.fromkeys(units))


def _policy_units_from_sentence(sentence: str) -> tuple[str, ...]:
    units: list[str] = []
    for punctuation_clause in _PUNCTUATION_BOUNDARY.split(sentence):
        for contrast_scope in _split_contrast_scopes(punctuation_clause):
            units.extend(
                _normalized_units(
                    _CURRENT_RELEASE_CLAUSE_BOUNDARY.split(contrast_scope)
                )
            )
    return tuple(units)


def _split_contrast_scopes(clause: str) -> tuple[str, ...]:
    """Split concessions and contrasts before applying scoped exceptions."""

    normalized = clause.strip(" ,;:—")
    if not normalized:
        return ()

    concession = _LEADING_CONCESSION.match(normalized)
    if concession is not None:
        normalized = normalized[concession.end() :]
        before_comma, comma, after_comma = normalized.partition(",")
        if comma:
            return _normalized_units((before_comma, after_comma))

    return _normalized_units(_CONTRAST_BOUNDARY.split(normalized))


def _normalized_units(clauses: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(
        normalized for clause in clauses if (normalized := clause.strip(" ,;:—"))
    )


def _has_runtime_release_concept(unit: str) -> bool:
    return _matches_concept_group(unit, _RELEASE_CONCEPTS)


def _has_prohibited_prerequisite_concept(unit: str) -> bool:
    return any(
        _matches_concept_group(unit, group)
        for group in _PROHIBITED_PREREQUISITE_CONCEPT_GROUPS
    )


def _is_conservative_release_dependency_risk(unit: str) -> bool:
    """Flag semantic co-occurrence without guessing how the concepts relate.

    Ambiguous prose is intentionally rejected. This may require a harmless
    sentence to be rewritten, but it cannot silently restore research authority
    through an unseen dependency verb.
    """

    return _has_runtime_release_concept(unit) and _has_prohibited_prerequisite_concept(
        unit
    )


def _has_explicit_non_blocking_scope(unit: str) -> bool:
    """Accept only explicit negative or independent relationships in this clause."""

    return _matches_concept_group(unit, _EXPLICIT_NON_BLOCKING_CONTEXTS)


def _has_past_policy_authority(unit: str) -> bool:
    """Recognize ordinary past authority while excluding present passives."""

    if _matches_concept_group(unit, _PAST_AUXILIARY_AUTHORITY):
        return True

    for match in _SIMPLE_PAST_AUTHORITY_VERB.finditer(unit):
        if not _PRESENT_OR_CONTINUING_AUXILIARY.search(unit[: match.start()]):
            return True
    return False


def _has_historical_policy_scope(unit: str) -> bool:
    """Accept only clearly past, retired, or superseded policy in this clause."""

    if _matches_concept_group(unit, _EXPLICIT_SUPERSESSION_CONTEXTS):
        return True
    if _matches_concept_group(unit, _CURRENT_POLICY_SCOPE):
        return False
    return _has_past_policy_authority(unit)


def test_prompt_defines_a_complete_runtime_without_a_model() -> None:
    prompt = PROMPT.read_text(encoding="utf-8")
    normalized_prompt = " ".join(prompt.split())

    for phrase in (
        "Polis jest kompletnym produktem bez lokalnego modelu językowego",
        "Model lokalny jest opcjonalnym rozszerzeniem",
        "nie blokuje wydania runtime'u",
        "zawsze pozostaje sugestią wymagającą jawnej akceptacji",
        "Wspierana ścieżka wydania runtime'u wymaga wyłącznie domyślnych zależności",
        "nie wymaga modelu lokalnego, serwera modeli, procesu Java, sieci, "
        "korpusu badawczego ani zużytego holdoutu",
    ):
        assert phrase in normalized_prompt

    assert "po zainstalowaniu zależności i lokalnego modelu" not in prompt
    assert (
        "Powinien łączyć szybkie, deterministyczne reguły z lokalnym, "
        "niewielkim modelem językowym"
    ) not in prompt


def test_accepted_charter_adr_supersedes_only_the_mandatory_model_path() -> None:
    assert ADR.exists()
    decision = ADR.read_text(encoding="utf-8")

    for phrase in (
        "Status: Accepted",
        "complete product without a local language model",
        "always review-only",
        "never blocks a runtime release",
        "Java process",
        "research corpus",
        "consumed holdouts",
        "consumed holdout",
        "This ADR supersedes only the mandatory-model critical path",
        "Issue #120",
    ):
        assert phrase in decision


def test_architecture_index_links_the_runtime_first_charter() -> None:
    index = ARCHITECTURE_INDEX.read_text(encoding="utf-8")
    assert "0020-runtime-first-product-charter.md" in index


def test_roadmap_separates_product_delivery_from_optional_research() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")

    for heading in (
        "## Active product lane",
        "## Optional research lane",
        "## Future product architecture",
        "## Historical delivery record",
    ):
        assert heading in roadmap

    for phrase in (
        "#120 -> #84 -> #95",
        "#119 -> #76 -> (#85 + #86) -> #87 -> (#88 + #89) -> #90",
        "Research outcomes do not block runtime releases",
    ):
        assert phrase in roadmap

    assert "#76 -> #84" not in roadmap
    assert "M5 majority-error graph from umbrella #93 is authoritative" not in roadmap


def test_roadmap_records_product_safety_priority_without_blocking_on_p1() -> None:
    roadmap = " ".join(ROADMAP.read_text(encoding="utf-8").split())

    for phrase in (
        "#84 is P0 product-safety work",
        "#95 is P1 hardening",
        "The `#120 -> #84 -> #95` arrow records sequencing; it does not mean "
        "that #95 blocks the current runtime release.",
        "Shared `Runtime 0.x Hardening` milestone membership does not make #95 "
        "a release blocker unless a separate accepted issue says so.",
    ):
        assert phrase in roadmap


def test_release_docs_do_not_require_model_research() -> None:
    documents = {
        path.name: path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "docs" / "limitations.md",
            ROOT / "docs" / "llm-quality-gates.md",
            ROOT / "docs" / "prerelease-candidate.md",
            ROOT / "docs" / "compatibility.md",
        )
    }

    joined = "\n".join(documents.values())
    assert "optional model research never blocks a runtime release" in joined
    prerelease = " ".join(documents["prerelease-candidate.md"].split())
    assert (
        "opcjonalne badania nad modelem nigdy nie blokują wydania runtime'u"
        in prerelease
    )
    assert "documentation-contract" not in documents["prerelease-candidate.md"]
    assert "tracked by M5 and [#43]" not in joined
    assert "until later M5 selection" not in joined


@pytest.mark.parametrize(
    ("document", "break_it_catches"),
    (
        pytest.param(
            (
                "A runtime release remains blocked until #76 completes and "
                "requires a qualified local model."
            ),
            "#76 plus qualified-local-model current release blocking",
            id="qualified-model-and-76-block-runtime-release",
        ),
        pytest.param(
            "The runtime can ship only after a Java process is available.",
            "Java as a runtime shipment prerequisite",
            id="java-process-release-prerequisite",
        ),
        pytest.param(
            "Publication depends on network access for verification.",
            "network access as publication prerequisite",
            id="network-publication-prerequisite",
        ),
        pytest.param(
            ("The product release requires the research corpus before publishing."),
            "research corpus as product release prerequisite",
            id="research-corpus-release-prerequisite",
        ),
        pytest.param(
            ("A runtime release cannot proceed until the consumed holdout is rerun."),
            "consumed holdout as runtime release prerequisite",
            id="consumed-holdout-release-prerequisite",
        ),
        pytest.param(
            "The next runtime release is governed by M5 and #93.",
            "M5 and #93 as current release authority",
            id="m5-93-release-authority",
        ),
        pytest.param(
            "Publishing the runtime waits for #43 and #76.",
            "#43 and #76 as runtime publication prerequisites",
            id="43-76-publication-prerequisites",
        ),
        pytest.param(
            (
                "The current runtime release is contingent upon completion of "
                "#76 and model qualification."
            ),
            "contingent #76 plus model qualification release prerequisite",
            id="contingent-76-model-qualification",
        ),
        pytest.param(
            "M5 and #93 remain the gatekeepers for publishing the runtime.",
            "M5 and #93 as publication gatekeepers",
            id="m5-93-publication-gatekeepers",
        ),
        pytest.param(
            (
                "Optional research is documented here, but the current runtime "
                "release requires #76."
            ),
            "optional-research clause cannot allowlist #76 release requirement",
            id="optional-research-but-76-required",
        ),
        pytest.param(
            (
                "Historical evidence remains archived, while publication "
                "depends on a local model."
            ),
            (
                "historical-evidence clause cannot allowlist local-model "
                "publication dependency"
            ),
            id="historical-evidence-while-local-model-required",
        ),
        pytest.param(
            (
                "The runtime release hinges on completion of #76 and model "
                "qualification."
            ),
            "hinge wording for #76 and model qualification",
            id="runtime-release-hinges-on-76-and-model-qualification",
        ),
        pytest.param(
            "A local model remains a condition for publication.",
            "condition wording for a local-model publication dependency",
            id="local-model-condition-for-publication",
        ),
        pytest.param(
            (
                "Although optional research is archived, the current runtime "
                "release requires #76."
            ),
            "although prefix cannot allowlist a current #76 requirement",
            id="although-optional-research-current-release-requires-76",
        ),
        pytest.param(
            "M5 and #93 control whether the runtime may ship.",
            "control-whether wording for M5 and #93 release authority",
            id="m5-93-control-whether-runtime-ships",
        ),
        pytest.param(
            (
                "Research evidence remains available, yet publication depends "
                "on network access."
            ),
            "yet contrast cannot allowlist a network publication dependency",
            id="research-evidence-yet-network-required",
        ),
        pytest.param(
            "Network access is the deciding factor in whether the runtime ships.",
            "deciding-factor synonym for network release authority",
            id="network-decides-whether-runtime-ships",
        ),
        pytest.param(
            (
                "Even though model research is optional, publication is "
                "contingent on a model."
            ),
            "even-though prefix cannot allowlist a generic model dependency",
            id="even-though-optional-research-model-publication-dependency",
        ),
        pytest.param(
            ("Despite the archived M5 plan, publication is controlled by #93."),
            "despite prefix cannot allowlist legacy publication control",
            id="despite-archived-m5-plan-93-controls-publication",
        ),
        pytest.param(
            "Publication is conditional upon a local model.",
            "conditional-upon wording for a local-model publication prerequisite",
            id="publication-conditional-upon-local-model",
        ),
        pytest.param(
            "Model qualification is necessary for the runtime release.",
            "necessary-for wording for model qualification",
            id="model-qualification-necessary-for-runtime-release",
        ),
        pytest.param(
            "M5 and #93 decide whether the runtime ships.",
            "decide-whether wording for legacy release authority",
            id="m5-93-decide-whether-runtime-ships",
        ),
        pytest.param(
            "The runtime release rests on completion of #76.",
            "rests-on wording for a #76 release prerequisite",
            id="runtime-release-rests-on-76",
        ),
        pytest.param(
            "The runtime release depends upon #76.",
            "depends-upon wording for a #76 release prerequisite",
            id="runtime-release-depends-upon-76",
        ),
        pytest.param(
            "The runtime release is predicated on network access.",
            "predicated-on wording for a network release prerequisite",
            id="runtime-release-predicated-on-network",
        ),
        pytest.param(
            "Publication requires LLM qualification.",
            "LLM qualification as a publication prerequisite",
            id="publication-requires-llm-qualification",
        ),
        pytest.param(
            (
                "Before ADR-0020, M5 governed publication, nevertheless the "
                "current release requires #76."
            ),
            "nevertheless must split past M5 authority from a current requirement",
            id="before-adr-nevertheless-current-release-requires-76",
        ),
        pytest.param(
            (
                "The archived M5 plan was authoritative for publication—"
                "nevertheless, the current release requires #76."
            ),
            "em dash and nevertheless must scope archived authority separately",
            id="archived-m5-em-dash-nevertheless-current-release-requires-76",
        ),
        pytest.param(
            (
                "Granted that the archived M5 plan was authoritative for "
                "publication, the current release requires #76."
            ),
            "granted-that history cannot allowlist a current #76 requirement",
            id="granted-that-archived-m5-current-release-requires-76",
        ),
    ),
)
def test_release_dependency_policy_rejects_semantic_contradiction_probes(
    document: str,
    break_it_catches: str,
) -> None:
    assert break_it_catches

    with pytest.raises(AssertionError, match="release dependency policy violation"):
        assert_no_runtime_release_dependency_conflict(document)


@pytest.mark.parametrize(
    ("release_form", "prohibited_family", "document", "expected_conflict"),
    (
        pytest.param(
            "runtime release",
            "model-or-llm",
            "The runtime release gets its go-ahead from an LLM.",
            True,
            id="runtime-release-x-model-or-llm",
        ),
        pytest.param(
            "runtime release",
            "optional-research-or-qualification",
            "The runtime release advances after optional model research signs off.",
            True,
            id="runtime-release-x-optional-research-or-qualification",
        ),
        pytest.param(
            "runtime release",
            "java-or-jvm",
            "The runtime release receives its readiness signal from the JVM.",
            True,
            id="runtime-release-x-java-or-jvm",
        ),
        pytest.param(
            "runtime release",
            "network-access",
            "The runtime release moves forward with network access in place.",
            True,
            id="runtime-release-x-network-access",
        ),
        pytest.param(
            "runtime release",
            "research-corpus-or-evidence",
            "The runtime release takes its cue from research evidence.",
            True,
            id="runtime-release-x-research-corpus-or-evidence",
        ),
        pytest.param(
            "runtime release",
            "consumed-holdout",
            "The runtime release proceeds after acceptance of the consumed holdout.",
            True,
            id="runtime-release-x-consumed-holdout",
        ),
        pytest.param(
            "runtime release",
            "legacy-m5-or-93",
            "The runtime release takes the M5 and #93 verdict as final.",
            True,
            id="runtime-release-x-legacy-m5-or-93",
        ),
        pytest.param(
            "runtime release",
            "issue-43-or-76",
            "The runtime release moves in lockstep with completion of #43 and #76.",
            True,
            id="runtime-release-x-issue-43-or-76",
        ),
        pytest.param(
            "publication",
            "model-or-llm",
            "Publication receives its green light from a qualified LLM.",
            True,
            id="publication-x-model-or-llm",
        ),
        pytest.param(
            "publication",
            "optional-research-or-qualification",
            "Publication proceeds once model qualification signs off.",
            True,
            id="publication-x-optional-research-or-qualification",
        ),
        pytest.param(
            "publication",
            "java-or-jvm",
            "Publication is coupled to Java readiness.",
            True,
            id="publication-x-java-or-jvm",
        ),
        pytest.param(
            "publication",
            "network-access",
            "Publication takes network availability as its launch signal.",
            True,
            id="publication-x-network-access",
        ),
        pytest.param(
            "publication",
            "research-corpus-or-evidence",
            "Publication proceeds under clearance from the research corpus.",
            True,
            id="publication-x-research-corpus-or-evidence",
        ),
        pytest.param(
            "publication",
            "consumed-holdout",
            "Publication is unlocked by acceptance of the consumed holdout.",
            True,
            id="publication-x-consumed-holdout",
        ),
        pytest.param(
            "publication",
            "legacy-m5-or-93",
            "Publication takes #93 as the final arbiter.",
            True,
            id="publication-x-legacy-m5-or-93",
        ),
        pytest.param(
            "publication",
            "issue-43-or-76",
            "Publication follows clearance of #76.",
            True,
            id="publication-x-issue-43-or-76",
        ),
        pytest.param(
            "ships",
            "model-or-llm",
            "The runtime ships once a local model gives approval.",
            True,
            id="ships-x-model-or-llm",
        ),
        pytest.param(
            "ships",
            "optional-research-or-qualification",
            "The runtime ships following the optional qualification study.",
            True,
            id="ships-x-optional-research-or-qualification",
        ),
        pytest.param(
            "ships",
            "java-or-jvm",
            "The runtime ships with JVM readiness as the deciding input.",
            True,
            id="ships-x-java-or-jvm",
        ),
        pytest.param(
            "ships",
            "network-access",
            "The runtime ships when network access gives the go-ahead.",
            True,
            id="ships-x-network-access",
        ),
        pytest.param(
            "ships",
            "research-corpus-or-evidence",
            "The runtime ships after research evidence receives sign-off.",
            True,
            id="ships-x-research-corpus-or-evidence",
        ),
        pytest.param(
            "ships",
            "consumed-holdout",
            "The runtime ships on clearance of the consumed holdout.",
            True,
            id="ships-x-consumed-holdout",
        ),
        pytest.param(
            "ships",
            "legacy-m5-or-93",
            "The runtime ships according to the M5 verdict.",
            True,
            id="ships-x-legacy-m5-or-93",
        ),
        pytest.param(
            "ships",
            "issue-43-or-76",
            "The runtime ships following sign-off on #43.",
            True,
            id="ships-x-issue-43-or-76",
        ),
        pytest.param(
            "shipping",
            "model-or-llm",
            "Runtime shipping advances after the qualified model is approved.",
            True,
            id="shipping-x-model-or-llm",
        ),
        pytest.param(
            "shipping",
            "optional-research-or-qualification",
            "Runtime shipping starts once LLM qualification produces a verdict.",
            True,
            id="shipping-x-optional-research-or-qualification",
        ),
        pytest.param(
            "shipping",
            "java-or-jvm",
            "Runtime shipping gets its signal from Java readiness.",
            True,
            id="shipping-x-java-or-jvm",
        ),
        pytest.param(
            "shipping",
            "network-access",
            "Runtime shipping is unlocked by network access.",
            True,
            id="shipping-x-network-access",
        ),
        pytest.param(
            "shipping",
            "research-corpus-or-evidence",
            "Runtime shipping advances on acceptance of the research corpus.",
            True,
            id="shipping-x-research-corpus-or-evidence",
        ),
        pytest.param(
            "shipping",
            "consumed-holdout",
            "Runtime shipping receives authorization from the consumed holdout result.",
            True,
            id="shipping-x-consumed-holdout",
        ),
        pytest.param(
            "shipping",
            "legacy-m5-or-93",
            "Runtime shipping follows the #93 decision.",
            True,
            id="shipping-x-legacy-m5-or-93",
        ),
        pytest.param(
            "shipping",
            "issue-43-or-76",
            "Runtime shipping proceeds according to #76.",
            True,
            id="shipping-x-issue-43-or-76",
        ),
    ),
)
def test_release_dependency_policy_rejects_literal_mutation_matrix(
    release_form: str,
    prohibited_family: str,
    document: str,
    expected_conflict: bool,
) -> None:
    conflict_detected = False
    try:
        assert_no_runtime_release_dependency_conflict(document)
    except AssertionError:
        conflict_detected = True

    assert conflict_detected is expected_conflict, (
        f"{release_form}/{prohibited_family}: {document}"
    )


def test_release_dependency_policy_allows_historical_and_optional_contexts() -> None:
    assert_no_runtime_release_dependency_conflict(
        """
        Optional model research never blocks a runtime release. The runtime
        release path does not require a model, Java process, network service,
        research corpus, or consumed holdout.

        The following M5 majority-error graph from umbrella #93 is historical
        evidence for the earlier combined product-and-research plan; it is not
        current product-release authority.

        Superseded by ADR-0020: runtime publication no longer depends on the
        combined M5 artifact graph, and the acceptance criteria were not
        completed.
        """
    )


@pytest.mark.parametrize(
    "document",
    (
        pytest.param(
            (
                "Optional research is documented here while the runtime release "
                "path does not require a model, Java process, network service, "
                "research corpus, or consumed holdout."
            ),
            id="optional-research-with-negative-runtime-boundary",
        ),
        pytest.param(
            (
                "Historical evidence remains archived, but publication no "
                "longer depends on the combined M5 artifact graph."
            ),
            id="historical-evidence-with-no-longer-depends-boundary",
        ),
        pytest.param(
            (
                "Before ADR-0020, the next release was governed by M5; that "
                "policy is superseded."
            ),
            id="superseded-pre-adr-m5-release-policy",
        ),
        pytest.param(
            ("The archived M5 plan treated #93 as authoritative for publication."),
            id="archived-m5-plan-publication-authority",
        ),
        pytest.param(
            (
                "Optional model research can inform future work without "
                "becoming a runtime release dependency."
            ),
            id="optional-model-research-without-release-dependency",
        ),
        pytest.param(
            "A local model is not a gate for runtime publication.",
            id="local-model-is-not-publication-gate",
        ),
        pytest.param(
            ("Under the retired M5 policy, #76 was a prerequisite for publication."),
            id="retired-m5-policy-publication-prerequisite",
        ),
        pytest.param(
            "A local model is no prerequisite for publication.",
            id="local-model-no-prerequisite-for-publication",
        ),
        pytest.param(
            "Publication need not wait for model qualification.",
            id="publication-need-not-wait-for-model-qualification",
        ),
        pytest.param(
            "The runtime release is not contingent on #76.",
            id="runtime-release-not-contingent-on-76",
        ),
        pytest.param(
            "In the pre-ADR-0020 plan, publication was governed by M5.",
            id="pre-adr-plan-publication-governed-by-m5",
        ),
        pytest.param(
            "At that time, #93 was authoritative for publication.",
            id="at-that-time-93-authoritative-for-publication",
        ),
        pytest.param(
            "The obsolete M5 policy made #76 a prerequisite for publication.",
            id="obsolete-m5-policy-76-publication-prerequisite",
        ),
    ),
)
def test_release_dependency_policy_allows_nearby_non_contradictory_probes(
    document: str,
) -> None:
    assert_no_runtime_release_dependency_conflict(document)


@pytest.mark.parametrize(
    ("prohibited_family", "context_kind", "document", "expected_conflict"),
    (
        pytest.param(
            "model-or-llm",
            "negative",
            "Runtime publication is independent of any local LLM.",
            False,
            id="model-or-llm-negative",
        ),
        pytest.param(
            "model-or-llm",
            "historical",
            (
                "The former model policy made a local LLM a prerequisite for "
                "publication."
            ),
            False,
            id="model-or-llm-historical",
        ),
        pytest.param(
            "optional-research-or-qualification",
            "negative",
            "Optional model research is non-blocking for the runtime release.",
            False,
            id="optional-research-or-qualification-negative",
        ),
        pytest.param(
            "optional-research-or-qualification",
            "historical",
            (
                "Under the previous qualification policy, model research "
                "governed publication."
            ),
            False,
            id="optional-research-or-qualification-historical",
        ),
        pytest.param(
            "java-or-jvm",
            "negative",
            "The runtime release does not require a JVM.",
            False,
            id="java-or-jvm-negative",
        ),
        pytest.param(
            "java-or-jvm",
            "historical",
            "Before ADR-0020, Java readiness controlled whether the runtime shipped.",
            False,
            id="java-or-jvm-historical",
        ),
        pytest.param(
            "network-access",
            "negative",
            "Publication is independent of network access.",
            False,
            id="network-access-negative",
        ),
        pytest.param(
            "network-access",
            "historical",
            "At that time, network access was a prerequisite for publication.",
            False,
            id="network-access-historical",
        ),
        pytest.param(
            "research-corpus-or-evidence",
            "negative",
            "Research evidence does not block runtime shipping.",
            False,
            id="research-corpus-or-evidence-negative",
        ),
        pytest.param(
            "research-corpus-or-evidence",
            "historical",
            (
                "The obsolete evidence policy made the research corpus a gate "
                "for the runtime release."
            ),
            False,
            id="research-corpus-or-evidence-historical",
        ),
        pytest.param(
            "consumed-holdout",
            "negative",
            "The consumed holdout is not a gate for publication.",
            False,
            id="consumed-holdout-negative",
        ),
        pytest.param(
            "consumed-holdout",
            "historical",
            (
                "The archived holdout policy required the consumed holdout "
                "before shipping."
            ),
            False,
            id="consumed-holdout-historical",
        ),
        pytest.param(
            "legacy-m5-or-93",
            "negative",
            "M5 and #93 are not release gatekeepers for publication.",
            False,
            id="legacy-m5-or-93-negative",
        ),
        pytest.param(
            "legacy-m5-or-93",
            "historical",
            "M5 and #93 formerly governed publication.",
            False,
            id="legacy-m5-or-93-historical",
        ),
        pytest.param(
            "issue-43-or-76",
            "negative",
            "The runtime release no longer depends on #43 or #76.",
            False,
            id="issue-43-or-76-negative",
        ),
        pytest.param(
            "issue-43-or-76",
            "historical",
            (
                "The retired dependency policy made #43 and #76 prerequisites "
                "for the runtime release."
            ),
            False,
            id="issue-43-or-76-historical",
        ),
    ),
)
def test_release_dependency_policy_allows_family_scoped_controls(
    prohibited_family: str,
    context_kind: str,
    document: str,
    expected_conflict: bool,
) -> None:
    conflict_detected = False
    try:
        assert_no_runtime_release_dependency_conflict(document)
    except AssertionError:
        conflict_detected = True

    assert conflict_detected is expected_conflict, (
        f"{prohibited_family}/{context_kind}: {document}"
    )


@pytest.mark.parametrize(
    ("document", "expected_units"),
    (
        pytest.param(
            (
                "Although optional research is archived, the current runtime "
                "release requires #76."
            ),
            (
                "optional research is archived",
                "the current runtime release requires #76.",
            ),
            id="although-comma",
        ),
        pytest.param(
            (
                "Research evidence remains available, yet publication depends "
                "on network access."
            ),
            (
                "Research evidence remains available",
                "publication depends on network access.",
            ),
            id="yet-comma",
        ),
        pytest.param(
            (
                "Even though model research is optional, publication is "
                "contingent on a model."
            ),
            (
                "model research is optional",
                "publication is contingent on a model.",
            ),
            id="even-though-comma",
        ),
        pytest.param(
            ("Despite the archived M5 plan, publication is controlled by #93."),
            (
                "the archived M5 plan",
                "publication is controlled by #93.",
            ),
            id="despite-comma",
        ),
    ),
)
def test_release_policy_units_split_contrast_scopes(
    document: str,
    expected_units: tuple[str, ...],
) -> None:
    units = _release_policy_units(document)

    for expected in expected_units:
        assert expected in units


@pytest.mark.parametrize(
    ("document", "current_unit"),
    (
        pytest.param(
            (
                "The archived M5 policy governed publication. The current runtime "
                "release requires #76."
            ),
            "The current runtime release requires #76.",
            id="sentence-punctuation",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication; the current runtime "
                "release requires #76."
            ),
            "the current runtime release requires #76.",
            id="semicolon",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication: the current runtime "
                "release requires #76."
            ),
            "the current runtime release requires #76.",
            id="colon",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication—the current runtime "
                "release requires #76."
            ),
            "the current runtime release requires #76.",
            id="em-dash",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, but the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="but",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, while the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="while",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, yet the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="yet",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication; however, the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="however",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, nevertheless the "
                "current runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="nevertheless",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, nonetheless the "
                "current runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="nonetheless",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, whereas the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="whereas",
        ),
        pytest.param(
            (
                "Although the archived M5 policy governed publication, the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="although",
        ),
        pytest.param(
            (
                "Even though the archived M5 policy governed publication, the "
                "current runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="even-though",
        ),
        pytest.param(
            (
                "Though the archived M5 policy governed publication, the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="though",
        ),
        pytest.param(
            (
                "Despite the archived M5 policy, the current runtime release "
                "requires #76."
            ),
            "the current runtime release requires #76.",
            id="despite",
        ),
        pytest.param(
            (
                "Granted that the archived M5 policy governed publication, the "
                "current runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="granted-that",
        ),
        pytest.param(
            (
                "The archived M5 policy governed publication, and the current "
                "runtime release requires #76."
            ),
            "the current runtime release requires #76.",
            id="and-current-clause",
        ),
    ),
)
def test_release_policy_splits_historical_prefix_from_current_contradiction(
    document: str,
    current_unit: str,
) -> None:
    assert current_unit in _release_policy_units(document)

    with pytest.raises(AssertionError, match="release dependency policy violation"):
        assert_no_runtime_release_dependency_conflict(document)


@pytest.mark.parametrize(
    "document",
    (
        pytest.param(
            (
                "Publication does not require a model—however, runtime shipping "
                "requires #76."
            ),
            id="negative-before-em-dash-however",
        ),
        pytest.param(
            (
                "Research evidence does not block publication, nonetheless the "
                "runtime release requires #43."
            ),
            id="negative-before-nonetheless",
        ),
        pytest.param(
            (
                "A local model is no prerequisite for publication; the runtime "
                "release requires #76."
            ),
            id="negative-before-semicolon",
        ),
        pytest.param(
            (
                "Publication does not require a model, and the current runtime "
                "release requires #76."
            ),
            id="negative-before-and-current-clause",
        ),
    ),
)
def test_release_policy_does_not_share_negation_between_clauses(
    document: str,
) -> None:
    with pytest.raises(AssertionError, match="release dependency policy violation"):
        assert_no_runtime_release_dependency_conflict(document)


@pytest.mark.parametrize("path", GOVERNED_RELEASE_DOCUMENTS)
def test_each_release_doc_independently_rejects_research_release_dependencies(
    path: Path,
) -> None:
    document = " ".join(path.read_text(encoding="utf-8").split())
    if path.name == "prerelease-candidate.md":
        required_phrases = (
            "opcjonalne badania nad modelem nigdy nie blokują wydania runtime'u",
            "Ścieżka wydania runtime'u nie wymaga modelu, procesu Java, usługi "
            "sieciowej, korpusu badawczego ani zużytego holdoutu",
        )
    else:
        required_phrases = (
            "optional model research never blocks a runtime release",
            "does not require a model, Java process, network service, research "
            "corpus, or consumed holdout",
        )

    for phrase in required_phrases:
        assert phrase in document

    assert_no_runtime_release_dependency_conflict(document)


def test_portfolio_manifest_covers_every_affected_open_issue_exactly_once() -> None:
    portfolio = PORTFOLIO.read_text(encoding="utf-8")
    product = {84, 95, 120}
    research = {76, 85, 86, 87, 88, 89, 90, 119}
    superseded = {43, 64, 66, 92, 93}
    future = {96, 97, 98, 99, 100}

    groups = (product, research, superseded, future)
    assert all(
        left.isdisjoint(right)
        for index, left in enumerate(groups)
        for right in groups[index + 1 :]
    )
    for issue in set().union(*groups):
        assert portfolio.count(f"| #{issue} |") == 1

    for phrase in (
        "Runtime 0.x Hardening",
        "Research — Optional Local Model Qualification",
        "status:superseded",
        "not planned",
        "acceptance criteria were not completed",
        "docs/superpowers/specs/2026-08-01-runtime-first-product-charter-design.md",
    ):
        assert phrase in portfolio


def test_portfolio_manifest_records_p0_p1_milestone_semantics() -> None:
    portfolio = " ".join(PORTFOLIO.read_text(encoding="utf-8").split())

    for phrase in (
        "`Runtime 0.x Hardening`: active product safety and invariant work; "
        "#84 is P0 product-safety work; #95 is P1 hardening; shared milestone "
        "membership does not make #95 a current runtime-release blocker.",
        "`#95` appends a product-hardening section stating that it is P1 "
        "hardening after `#84`, that it follows the P0 product-safety gate, "
        "and that neither the shared milestone nor roadmap arrow makes it a "
        "current runtime-release blocker.",
        "`#120` updates its checklist/body to reference PR #121 as Phase 1, "
        "carry the #84 P0 / #95 P1 distinction, and state that the issue "
        "closes only after every live-state assertion in this manifest passes.",
    ):
        assert phrase in portfolio


def test_portfolio_manifest_replaces_legacy_issue_body_and_native_edges() -> None:
    portfolio = " ".join(PORTFOLIO.read_text(encoding="utf-8").split())

    for phrase in (
        "`#84`: replace the complete legacy dependency section, not only one "
        "sentence; remove body claims that it depends on `#76`, blocks `#64`, "
        "or blocks final release authorization; remove native `blockedBy` "
        "edge `#76 -> #84`; remove native `blocking` edge `#84 -> #64`.",
        "`#95`: replace legacy M5 publication wording, including any claim "
        "that it does not block publication of M5; record it as P1 runtime "
        "hardening that follows #84 without blocking the current runtime "
        "release by milestone membership alone.",
        "`#90`: replace the complete dependency section so it keeps only "
        "internal optional-research dependencies `#76`, `#85`, `#86`, `#88`, "
        "and `#89`; remove body and native edges involving superseded `#43`, "
        "product `#84`, and blocking `#64`.",
        "`#100`: replace legacy release-authority prose, including any claim "
        "that `#93` remains authoritative for the next release or that the "
        "current M5 publication controls runtime release sequencing.",
    ):
        assert phrase in portfolio


def test_portfolio_post_mutation_assertions_reject_legacy_release_language() -> None:
    portfolio = " ".join(PORTFOLIO.read_text(encoding="utf-8").split())

    for phrase in (
        "post-mutation inventory rejects `#93 remains authoritative for the "
        "next release`",
        "post-mutation inventory rejects `current M5 publication`",
        "post-mutation inventory rejects `blocks #64` on #84 or #90",
        "post-mutation inventory rejects native `blockedBy` edges from #76 to "
        "#84, from #43 to #90, and from #84 to #90",
        "post-mutation inventory rejects native `blocking` edges from #84 to "
        "#64 and from #90 to #64",
        "post-mutation inventory rejects any product-release dependency on "
        "#43, #76, #90, #93, model research, Java, network, research corpus, "
        "or consumed holdout",
    ):
        assert phrase in portfolio


def test_task_6_plan_requires_executable_body_and_native_edge_contract() -> None:
    plan = " ".join(PLAN.read_text(encoding="utf-8").split())

    for phrase in (
        "Complete body edits must preserve unrelated body content while "
        "replacing only the heading-delimited sections named below.",
        "#84: replace the complete heading-delimited dependency section with "
        "the exact `## Runtime-first product-safety dependency` template",
        "#90: replace the complete heading-delimited dependency section with "
        "the exact `## Runtime-first optional-research dependency` template",
        "#95: replace the complete heading-delimited M5 publication section "
        "with the exact `## Runtime-first product-hardening disposition` "
        "template",
        "#100: replace the complete heading-delimited release-authority section "
        "with the exact `## Runtime-first M6 architecture disposition` template",
        "remove or reconcile every prohibited native `blockedBy` and `blocking` edge",
        "The mutation must abort if any old anchor is missing, appears more "
        "than once, or differs from the recorded live text.",
        "Do not append these templates as a fallback for #95 or #100.",
        "#95 old anchor appears exactly once",
        "#100 old anchors each appear exactly once",
        "This umbrella does not block #76, #90, #92, or publication of M5.",
        "Shared `Runtime 0.x Hardening` milestone membership and the "
        "`#120 -> #84 -> #95` roadmap sequence alone do not make #95 a "
        "blocker for the current runtime release.",
        "A future accepted issue may explicitly make #95 a release blocker.",
        "This umbrella remains independent from #76, #90, and #92.",
        "The current M5 tracker #93 remains authoritative for the next release.",
        "#83 + #84 + current M5 publication",
        "M6 is non-blocking for #93 and the current M5 publication.",
        "native `blocking` excludes #84 -> #43, #84 -> #64, and #90 -> #64",
    ):
        assert phrase in plan

    assert "append the exact heading and template" not in plan
    assert (
        "This umbrella does not block #76, #90, #92, or a runtime release." not in plan
    )


def test_task_6_plan_verifies_exact_live_postconditions() -> None:
    plan = " ".join(PLAN.read_text(encoding="utf-8").split())

    for phrase in (
        "#84 body contains `P0 product-safety work`",
        "#84 body contains no #64 blocking claim and no final-release "
        "authorization blocker claim",
        "#90 has only internal optional-research dependencies #76, #85, #86, "
        "#88, and #89 in body prose and native edges",
        "#90 has no body or native dependency edge involving #43, #84, or #64",
        "#95 body contains `P1 hardening after #84`",
        "#95 body contains no legacy M5 non-publication wording",
        "#95 body states that shared milestone membership and roadmap sequencing "
        "alone do not make #95 a blocker for the current runtime release and "
        "that a future accepted issue may explicitly make #95 a release blocker",
        "#95 body contains no generic claim that #95 does not block a runtime release",
        "#100 body contains no #93/current-M5 release-authority wording",
        "#100 body contains no `current M5 publication` wording in any section",
        "#120 body carries the #84 P0 / #95 P1 distinction and says #95 is not "
        "a current runtime-release blocker by shared milestone or roadmap "
        "sequencing alone",
        "native `blockedBy` excludes #76 -> #84, #84 -> #43, #43 -> #90, and "
        "#84 -> #90",
        "native `blocking` excludes #84 -> #43, #84 -> #64, and #90 -> #64",
    ):
        assert phrase in plan


def test_portfolio_manifest_records_exact_label_transitions() -> None:
    portfolio = PORTFOLIO.read_text(encoding="utf-8")
    normalized = " ".join(portfolio.split())

    for forbidden in (
        "preserve current labels",
        "Preserve current labels",
        "preserve other current labels",
        "Preserve other current labels",
        "Retain `status:blocked` only while",
        "retain `status:blocked` only while",
        "keep unblocked",
    ):
        assert forbidden not in portfolio

    expected_transitions = (
        (
            43,
            "`status:superseded`",
            "`status:blocked`",
            "`type:feature`, `area:llm`, `priority:P0`, `status:superseded`",
        ),
        (
            64,
            "`status:superseded`",
            "`status:blocked`",
            "`type:test`, `area:evaluation`, `priority:P0`, `status:superseded`",
        ),
        (
            66,
            "`status:superseded`",
            "`status:blocked`",
            "`type:test`, `area:evaluation`, `priority:P0`, `status:superseded`",
        ),
        (
            76,
            "none",
            "none",
            "`type:research`, `area:evaluation`, `priority:P0`, `status:blocked`",
        ),
        (
            84,
            "none",
            "`status:blocked`",
            "`type:bug`, `area:correction`, `priority:P0`",
        ),
        (
            85,
            "none",
            "none",
            "`type:research`, `area:evaluation`, `priority:P0`, `status:blocked`",
        ),
        (
            86,
            "none",
            "none",
            "`type:research`, `area:evaluation`, `priority:P0`, `status:blocked`",
        ),
        (
            87,
            "none",
            "none",
            "`type:research`, `area:rules`, `priority:P0`, `status:blocked`",
        ),
        (
            88,
            "none",
            "none",
            "`type:research`, `area:rules`, `priority:P0`, `status:blocked`",
        ),
        (
            89,
            "none",
            "none",
            "`type:research`, `area:llm`, `priority:P0`, `status:blocked`",
        ),
        (
            90,
            "none",
            "none",
            "`type:research`, `area:evaluation`, `priority:P0`, `status:blocked`",
        ),
        (
            92,
            "`status:superseded`",
            "`status:blocked`",
            "`type:research`, `area:packaging`, `priority:P0`, `status:superseded`",
        ),
        (
            93,
            "`status:superseded`",
            "none",
            "`type:research`, `area:packaging`, `priority:P0`, `status:superseded`",
        ),
        (95, "none", "none", "`type:chore`, `area:evaluation`, `priority:P1`"),
        (96, "none", "none", "`type:chore`, `area:core`, `priority:P1`"),
        (97, "none", "none", "`type:chore`, `area:rules`, `priority:P2`"),
        (98, "none", "none", "`type:chore`, `area:rules`, `priority:P2`"),
        (99, "none", "none", "`type:chore`, `area:analysis`, `priority:P2`"),
        (100, "none", "none", "`type:chore`, `area:core`, `priority:P1`"),
        (
            119,
            "none",
            "none",
            "`type:research`, `area:evaluation`, `priority:P0`",
        ),
        (
            120,
            "`type:decision`, `area:core`",
            "`type:chore`, `area:packaging`",
            "`type:decision`, `area:core`, `priority:P0`",
        ),
    )

    for issue, add_labels, remove_labels, final_labels in expected_transitions:
        phrase = (
            f"`#{issue}`: add {add_labels}; remove {remove_labels}; "
            f"final labels {final_labels}."
        )
        assert phrase in normalized
