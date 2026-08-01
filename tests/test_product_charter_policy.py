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


def assert_no_runtime_release_dependency_conflict(document: str) -> None:
    for unit in _release_policy_units(document):
        if not _has_runtime_release_concept(unit):
            continue
        if not _has_dependency_or_authority_concept(unit):
            continue
        if not _has_forbidden_release_dependency_concept(unit):
            continue
        if _is_allowed_historical_or_negative_context(unit):
            continue
        msg = f"release dependency policy violation: {unit}"
        raise AssertionError(msg)


def _release_policy_units(document: str) -> tuple[str, ...]:
    units: list[str] = []
    for raw_line in document.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        for sentence in re.split(r"(?<=[.!?;])\s+", line):
            for clause in re.split(
                r"\s*(?:[,;]\s*)?\b(?:but|while|whereas|although|though|however)\b\s+",
                sentence,
                flags=re.IGNORECASE,
            ):
                normalized = clause.strip(" ,;")
                if normalized:
                    units.append(normalized)
    return tuple(dict.fromkeys(units))


def _has_runtime_release_concept(unit: str) -> bool:
    return bool(
        re.search(
            r"\b(?:runtime|product|polis|next|current)?[- ]?"
            r"(?:release|publication|publishing|publish|prerelease|candidate|"
            r"ship|shipping)\b",
            unit,
            flags=re.IGNORECASE,
        )
    )


def _has_dependency_or_authority_concept(unit: str) -> bool:
    return bool(
        re.search(
            r"\b(?:blocked?|blocking|requires?|required|depends? on|dependency|"
            r"prerequisite|precondition|until|only after|cannot proceed|"
            r"waits? for|governed by|authoritative|authority|release blocker|"
            r"release-blocking|contingent (?:upon|on)|gatekeepers?)\b",
            unit,
            flags=re.IGNORECASE,
        )
    )


def _has_forbidden_release_dependency_concept(unit: str) -> bool:
    return bool(
        re.search(
            r"(?:#43|#76|#93|\bM5\b|\bqualified local model\b|"
            r"\blocal model\b|\bmodel research\b|\bmodel qualification\b|"
            r"\bJava(?: process)?\b|\bnetwork(?: access| service)?\b|"
            r"\bresearch corp(?:us|ora)\b|\bconsumed holdouts?\b)",
            unit,
            flags=re.IGNORECASE,
        )
    )


def _is_allowed_historical_or_negative_context(unit: str) -> bool:
    return bool(
        re.search(
            r"(?:\bdoes not (?:require|depend on|execute or depend on|block)\b|"
            r"\bdo not block\b|\bnever blocks?\b|\bno current-release "
            r"dependency\b|\bnot .*current[- ]runtime[- ]release blocker\b|"
            r"\bnot .*product-release authority\b|\bnot .*release dependency\b|"
            r"\bnot .*release blocker\b|\bnot .*release gate\b|"
            r"\bno longer depends\b|\bwithout making\b|\bhistorical evidence\b|"
            r"\bsuperseded\b|\boptional research\b|\bresearch evidence\b)",
            unit,
            flags=re.IGNORECASE,
        )
    )


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
    ),
)
def test_release_dependency_policy_rejects_semantic_contradiction_probes(
    document: str,
    break_it_catches: str,
) -> None:
    assert break_it_catches

    with pytest.raises(AssertionError, match="release dependency policy violation"):
        assert_no_runtime_release_dependency_conflict(document)


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
    ),
)
def test_release_dependency_policy_allows_nearby_non_contradictory_probes(
    document: str,
) -> None:
    assert_no_runtime_release_dependency_conflict(document)


@pytest.mark.parametrize("path", GOVERNED_RELEASE_DOCUMENTS)
def test_each_release_doc_independently_rejects_research_release_dependencies(
    path: Path,
) -> None:
    document = " ".join(path.read_text(encoding="utf-8").split())

    for phrase in (
        "optional model research never blocks a runtime release",
        "does not require a model, Java process, network service, research "
        "corpus, or consumed holdout",
    ):
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
        "The current M5 tracker #93 remains authoritative for the next release.",
        "#83 + #84 + current M5 publication",
        "M6 is non-blocking for #93 and the current M5 publication.",
        "native `blocking` excludes #84 -> #43, #84 -> #64, and #90 -> #64",
    ):
        assert phrase in plan

    assert "append the exact heading and template" not in plan


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
        "do not make #95 a current runtime-release blocker",
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
