from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "architecture" / "decisions" / "0008-hybrid-correction-policy.md"
ARCHITECTURE_INDEX = ROOT / "docs" / "architecture" / "README.md"
ROADMAP = ROOT / "docs" / "project" / "ROADMAP.md"
RISKS = ROOT / "docs" / "project" / "RISKS.md"
QUALITY_GATES = ROOT / "docs" / "llm-quality-gates.md"
LIMITATIONS = ROOT / "docs" / "limitations.md"


def test_hybrid_adr_records_architecture_and_safety_boundaries() -> None:
    assert ADR.exists(), "ADR-0008 must record the M5 hybrid policy"
    decision = ADR.read_text(encoding="utf-8")

    for section in (
        "## Components and interfaces",
        "## Data flow and request budget",
        "## Correction eligibility",
        "## Failure and outcome boundaries",
        "## Privacy boundary",
        "## Quality gates",
    ):
        assert section in decision

    for policy in (
        "source-policy",
        "suggestion-only",
        "one model call",
        "two model calls",
        "finite candidate",
        "accept or reject",
        "model-independent",
        "loopback",
    ):
        assert policy in decision


def test_m5_roadmap_records_every_outcome_in_dependency_order() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    issue_refs = (
        "#65",
        "#55",
        "#56",
        "#57",
        "#58",
        "#59",
        "#60",
        "#61",
        "#62",
        "#63",
        "#43",
        "#64",
    )

    assert all(issue in roadmap for issue in issue_refs)
    assert roadmap.index("#65") < roadmap.index("#55") < roadmap.index("#56")
    assert roadmap.index("#60") < roadmap.index("#61") < roadmap.index("#43")
    assert roadmap.index("#43") < roadmap.index("#64")


def test_m5_risk_register_covers_hybrid_evidence_and_runtime_risks() -> None:
    risks = RISKS.read_text(encoding="utf-8").lower()

    for risk in (
        "evaluation leakage",
        "circular benchmark",
        "morphology ambiguity",
        "suggestion false positives",
        "runtime availability",
        "memory pressure",
        "fine-tuning overfit",
    ):
        assert risk in risks


def test_quality_gates_split_automatic_corrections_from_suggestions() -> None:
    gates = QUALITY_GATES.read_text(encoding="utf-8")

    assert "## Automatic-correction gates" in gates
    assert "exact edit precision: **1.00**" in gates
    assert "correction accuracy: **1.00**" in gates
    assert "## Suggestion gates" in gates
    assert "exact edit precision: at least **0.90**" in gates
    assert "valid structured outcomes: **100%**" in gates
    assert "protected hard negatives: **0** findings" in gates


def test_hybrid_policy_is_linked_without_claiming_qualification() -> None:
    architecture_index = ARCHITECTURE_INDEX.read_text(encoding="utf-8")
    limitations = LIMITATIONS.read_text(encoding="utf-8")

    assert "0008-hybrid-correction-policy.md" in architecture_index
    assert "ADR-0008" in limitations
    assert "No tested local model has qualified" in limitations
    assert (
        "five-rule LanguageTool subset is not a general Polish corrector" in limitations
    )
