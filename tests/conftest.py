from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import pytest

RESEARCH_IMPORT_PREFIXES = (
    "experiments.",
    "experiments",
)
RESEARCH_CORPUS_MARKERS = (
    "tests/fixtures/evaluation/",
    "tests/fixtures/evaluation",
)


def pytest_collection_finish(session: pytest.Session) -> None:
    marker_expression = session.config.option.markexpr or ""
    if "not research" not in marker_expression:
        return

    violations: list[str] = []
    for item in session.items:
        path = Path(str(item.path))
        if path.suffix != ".py":
            continue
        reasons = _research_only_references(path)
        if reasons:
            violations.append(f"{path.relative_to(session.config.rootpath)}: {reasons}")

    if violations:
        raise pytest.UsageError(
            "product-selected tests must not import research-only assets:\n"
            + "\n".join(sorted(set(violations)))
        )


@lru_cache
def _research_only_references(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    reasons: list[str] = []
    imports_research_loader = any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("experiments.sentence_safety_gate.")
        and bool(
            {alias.name for alias in node.names}
            & {"load_development_sentences", "load_reserved_holdout_sentences"}
        )
        for node in ast.walk(tree)
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in RESEARCH_IMPORT_PREFIXES:
                    reasons.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "experiments" or node.module.startswith("experiments."):
                reasons.append(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if imports_research_loader and any(
                marker in node.value for marker in RESEARCH_CORPUS_MARKERS
            ):
                reasons.append(node.value)

    return ", ".join(sorted(set(reasons)))
