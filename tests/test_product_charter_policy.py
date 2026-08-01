from __future__ import annotations

from pathlib import Path

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
    ):
        assert phrase in portfolio


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
