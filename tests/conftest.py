from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import pytest

RESEARCH_IMPORT_PREFIX = "experiments"
EVALUATION_FIXTURE_PARTS = ("tests", "fixtures", "evaluation")
PATH_FACTORY_NAMES = {"Path", "PurePath", "PurePosixPath", "PureWindowsPath"}
PATH_PRESERVING_METHODS = {"absolute", "expanduser", "resolve"}
PATH_READ_METHODS = {"open", "read_bytes", "read_text"}
PATH_LOADING_FUNCTIONS = {"open"}
PATH_LOADING_NAME_PREFIXES = ("load", "parse", "read")


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
    bindings = _constant_assignments(tree)
    reasons: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_research_import(alias.name):
                    reasons.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if _is_research_import(node.module):
                reasons.append(node.module)
        elif isinstance(node, ast.Call):
            fixture = _evaluation_fixture_load(node, bindings)
            if fixture is not None:
                reasons.append(fixture)

    return ", ".join(sorted(set(reasons)))


def _is_research_import(module: str) -> bool:
    return module == RESEARCH_IMPORT_PREFIX or module.startswith(
        f"{RESEARCH_IMPORT_PREFIX}."
    )


def _constant_assignments(tree: ast.AST) -> dict[str, ast.AST]:
    bindings: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                bindings[node.target.id] = node.value
    return bindings


def _evaluation_fixture_load(
    node: ast.Call, bindings: Mapping[str, ast.AST]
) -> str | None:
    if isinstance(node.func, ast.Attribute):
        receiver_fixture = _evaluation_fixture_path(node.func.value, bindings)
        if receiver_fixture is not None and node.func.attr in PATH_READ_METHODS:
            return receiver_fixture

    if not _looks_like_path_loading_call(node.func):
        return None

    for candidate in (*node.args, *(keyword.value for keyword in node.keywords)):
        fixture = _evaluation_fixture_path(candidate, bindings)
        if fixture is not None:
            return fixture
    return None


def _looks_like_path_loading_call(func: ast.expr) -> bool:
    name = _call_leaf_name(func)
    if name in PATH_LOADING_FUNCTIONS:
        return True
    return name.startswith(PATH_LOADING_NAME_PREFIXES)


def _call_leaf_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _evaluation_fixture_path(
    node: ast.AST, bindings: Mapping[str, ast.AST]
) -> str | None:
    parts = _path_parts(node, bindings, seen=frozenset())
    for index in range(len(parts) - len(EVALUATION_FIXTURE_PARTS) + 1):
        candidate = parts[index : index + len(EVALUATION_FIXTURE_PARTS)]
        if candidate == EVALUATION_FIXTURE_PARTS:
            return "/".join(parts[index:])
    return None


def _path_parts(
    node: ast.AST, bindings: Mapping[str, ast.AST], *, seen: frozenset[str]
) -> tuple[str, ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _split_path(node.value)
    if isinstance(node, ast.JoinedStr):
        return tuple(
            part
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
            for part in _split_path(value.value)
        )
    if isinstance(node, ast.Name):
        if node.id in bindings and node.id not in seen:
            return _path_parts(bindings[node.id], bindings, seen=seen | {node.id})
        return ()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _path_parts(node.left, bindings, seen=seen) + _path_parts(
            node.right, bindings, seen=seen
        )
    if isinstance(node, ast.Call):
        name = _call_leaf_name(node.func)
        if name in PATH_FACTORY_NAMES:
            return tuple(
                part
                for argument in node.args
                for part in _path_parts(argument, bindings, seen=seen)
            )
        if isinstance(node.func, ast.Attribute) and name in PATH_PRESERVING_METHODS:
            return _path_parts(node.func.value, bindings, seen=seen)
    if isinstance(node, ast.Attribute):
        return _path_parts(node.value, bindings, seen=seen)
    if isinstance(node, ast.Subscript):
        return _path_parts(node.value, bindings, seen=seen)
    return ()


def _split_path(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.replace("\\", "/").split("/") if part)
