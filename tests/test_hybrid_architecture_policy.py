from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "architecture" / "decisions" / "0008-hybrid-correction-policy.md"
ARCHITECTURE_INDEX = ROOT / "docs" / "architecture" / "README.md"
ROADMAP = ROOT / "docs" / "project" / "ROADMAP.md"
RISKS = ROOT / "docs" / "project" / "RISKS.md"
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


def test_m5_roadmap_keeps_completed_historical_record() -> None:
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
    )

    assert "## Archiwalny rejestr dostarczania M0–M5" in roadmap
    assert all(issue in roadmap for issue in issue_refs)
    assert roadmap.index("#65") < roadmap.index("#55") < roadmap.index("#56")
    assert roadmap.index("#60") < roadmap.index("#61")


def test_v1_risk_register_covers_conservative_runtime_risks() -> None:
    risks = RISKS.read_text(encoding="utf-8").lower()

    for risk in (
        "lokalnego uzasadnienia",
        "znaczenie tekstu",
        "przesunięcie",
        "automatyczne uprawnienie",
        "offline",
        "archiwum v2",
    ):
        assert risk in risks


def test_v1_risk_register_points_to_the_current_product_decision() -> None:
    risks = RISKS.read_text(encoding="utf-8")

    assert "ADR-0022" in risks
    assert "danych wzorcowych" not in risks
    assert "dostrajania" not in risks


def test_removed_hybrid_quality_gates_are_not_a_maintained_v1_surface() -> None:
    assert not (ROOT / "docs" / "llm-quality-gates.md").exists()


def test_hybrid_policy_remains_historical_without_extending_v1() -> None:
    architecture_index = ARCHITECTURE_INDEX.read_text(encoding="utf-8")
    limitations = LIMITATIONS.read_text(encoding="utf-8")

    assert "0008-hybrid-correction-policy.md" in architecture_index
    assert "nie jest pełnym korektorem języka polskiego" in limitations
    assert "nie wymaga sieci, modelu, procesu Java" in limitations
