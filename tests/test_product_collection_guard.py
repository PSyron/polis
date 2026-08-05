from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

_research_only_references = cast(
    Callable[[Path], str],
    sys.modules["conftest"].__dict__["_research_only_references"],
)


def _references_for(tmp_path: Path, source: str) -> str:
    path = tmp_path / f"test_guard_probe_{abs(hash(source))}.py"
    path.write_text(source, encoding="utf-8")
    return _research_only_references(path)


def test_guard_rejects_plain_experiment_import(tmp_path: Path) -> None:
    reasons = _references_for(
        tmp_path,
        "import experiments.contextual_inflection_routing.experiment\n",
    )

    assert reasons == "experiments.contextual_inflection_routing.experiment"


def test_guard_rejects_direct_evaluation_fixture_reads(tmp_path: Path) -> None:
    reasons = _references_for(
        tmp_path,
        """
import json
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "evaluation" / "corpus.json"


def test_reads_research_fixtures():
    Path("tests/fixtures/evaluation/corpus.json").read_text(encoding="utf-8")
    open(ROOT / "tests" / "fixtures" / "evaluation" / "corpus.xml")
    json.load(open(CORPUS))
    ElementTree.parse(Path("tests") / "fixtures" / "evaluation" / "corpus.xml")
""",
    )

    assert reasons == (
        "tests/fixtures/evaluation/corpus.json, tests/fixtures/evaluation/corpus.xml"
    )


def test_guard_accepts_policy_mentions_without_fixture_reads(tmp_path: Path) -> None:
    reasons = _references_for(
        tmp_path,
        """
import subprocess

BYTE_STABLE_TEXT_PATHS = (
    "tests/fixtures/evaluation/polish_correction_corpus_v3.json",
)


def test_policy_mentions_research_fixture_path():
    result = subprocess.run(
        ["git", "check-attr", "text", "--", *BYTE_STABLE_TEXT_PATHS],
        check=False,
    )
    assert result.returncode in {0, 1}
""",
    )

    assert reasons == ""


def test_product_rules_exclude_orphaned_languagetool_runtime() -> None:
    for module_name in (
        "polis.rules.languagetool",
        "polis.rules.languagetool_stdio",
        "polis.rules.contextual_inflection",
    ):
        assert importlib.util.find_spec(module_name) is None, module_name

    assert not (Path(__file__).parent / "fixtures/fake_languagetool_stdio.py").exists()

    for module_name in (
        "polis.rules.agreement",
        "polis.rules.spelling",
        "polis.rules.syntax",
    ):
        assert importlib.import_module(module_name) is not None
