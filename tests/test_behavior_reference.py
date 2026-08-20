from __future__ import annotations

import re
from pathlib import Path

from polis import Analyzer, AnalyzerConfig

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "behavior-reference.md"
SOURCE_ROW = re.compile(r"^\| `(rule:[^`]+)`(?: †)? \|", re.MULTILINE)


def test_behavior_reference_covers_current_runtime_sources_in_order() -> None:
    documented = tuple(SOURCE_ROW.findall(REFERENCE.read_text(encoding="utf-8")))
    runtime = tuple(
        str(identity.source)
        for identity in Analyzer(AnalyzerConfig()).source_identity_snapshot
    )

    assert documented == runtime
    assert len(documented) == len(set(documented))
