from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/architecture/decisions/0003-public-api-and-exception-contract.md"
API_DOC = ROOT / "docs/public-api.md"
API_STUB = ROOT / "tests/typecheck/stubs/polis/__init__.pyi"
EXAMPLES = ROOT / "tests/typecheck/api_contract_examples.py"
TYPECHECK_RUNNER = ROOT / "scripts/typecheck_api_contract.py"
ARCHITECTURE_INDEX = ROOT / "docs/architecture/README.md"
PORTABLE_TYPECHECK_COMMAND = (
    "uv run --locked --extra dev python scripts/typecheck_api_contract.py"
)

PUBLIC_ERROR_EXAMPLES = {
    "ConfigurationError": ("classify_configuration_failure", "path"),
    "BackendUnavailableError": ("classify_backend_unavailability", "backend"),
    "AnalysisTimeoutError": ("classify_timeout", "backend"),
    "InvalidBackendResponseError": ("classify_invalid_response", "backend"),
    "UnknownFindingError": ("classify_unknown_finding", "finding_ids"),
    "UncorrectableFindingError": ("classify_uncorrectable_finding", "finding_ids"),
    "CorrectionConflictError": ("classify_correction_conflict", "finding_ids"),
}


def test_accepted_adr_freezes_the_public_entry_points_and_failures() -> None:
    adr = ADR.read_text(encoding="utf-8")

    required = (
        "- Status: Accepted",
        "class Analyzer:",
        "def from_config(cls, path: str | Path) -> Self:",
        "def analyze(",
        "async def analyze_async(",
        "def apply(self, issue_ids: Iterable[str]) -> str:",
        "No partial `AnalysisResult` is returned.",
        "ConfigurationError",
        "BackendUnavailableError",
        "AnalysisTimeoutError",
        "InvalidBackendResponseError",
        "CorrectionConflictError",
        "The operation is atomic",
    )

    for value in required:
        assert value in adr


def test_api_contract_documents_the_accepted_adr_and_public_error_examples() -> None:
    api_doc = API_DOC.read_text(encoding="utf-8")

    required = (
        "ADR-0003",
        "Analyzer.from_config",
        "BackendUnavailableError",
        "AnalysisTimeoutError",
        "InvalidBackendResponseError",
        "No partial `AnalysisResult` is returned.",
    )
    for value in required:
        assert value in api_doc
    for error in PUBLIC_ERROR_EXAMPLES:
        assert f"except {error} as error:" in api_doc


def test_architecture_index_lists_the_accepted_api_contract() -> None:
    index = ARCHITECTURE_INDEX.read_text(encoding="utf-8")

    assert (
        "| [ADR-0003](decisions/0003-public-api-and-exception-contract.md) | "
        "Accepted | Public API and exception contract |"
    ) in index


def test_typing_only_contract_is_not_a_runtime_module() -> None:
    assert API_STUB.is_file()
    assert not (API_STUB.parent / "__init__.py").exists()
    assert not (API_STUB.parent / "_api_contract.pyi").exists()


def test_public_result_has_one_declaration_and_direct_alias_reexports() -> None:
    stub_root = API_STUB.parents[1]
    declarations: list[Path] = []
    for stub in stub_root.rglob("*.pyi"):
        tree = ast.parse(stub.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "AnalysisResult"
            for node in tree.body
        ):
            declarations.append(stub.relative_to(stub_root))

    assert declarations == [Path("polis/core/models.pyi")]

    for stub in (API_STUB, API_STUB.parent / "core/__init__.pyi"):
        tree = ast.parse(stub.read_text(encoding="utf-8"))
        aliases = {
            (node.level, node.module, alias.name, alias.asname)
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        expected_module = "core.models" if stub == API_STUB else "models"
        assert (1, expected_module, "AnalysisResult", "AnalysisResult") in aliases


def test_exception_hierarchy_and_examples_cover_every_public_leaf() -> None:
    stub_tree = ast.parse(API_STUB.read_text(encoding="utf-8"))
    examples_tree = ast.parse(EXAMPLES.read_text(encoding="utf-8"))
    hierarchy = {
        node.name: node.bases[0].id
        for node in stub_tree.body
        if isinstance(node, ast.ClassDef)
        and node.bases
        and isinstance(node.bases[0], ast.Name)
    }
    expected_hierarchy = {
        "ConfigurationError": "PolisError",
        "BackendUnavailableError": "PolisError",
        "AnalysisTimeoutError": "PolisError",
        "InvalidBackendResponseError": "PolisError",
        "CorrectionSelectionError": "PolisError",
        "UnknownFindingError": "CorrectionSelectionError",
        "UncorrectableFindingError": "CorrectionSelectionError",
        "CorrectionConflictError": "CorrectionSelectionError",
    }
    assert {name: hierarchy[name] for name in expected_hierarchy} == expected_hierarchy

    caught_by_function = {
        node.name: {
            handler.type.id
            for handler in ast.walk(node)
            if isinstance(handler, ast.ExceptHandler)
            and isinstance(handler.type, ast.Name)
        }
        for node in examples_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    function_nodes = {
        node.name: node
        for node in examples_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for error, (function, context_key) in PUBLIC_ERROR_EXAMPLES.items():
        assert caught_by_function[function] == {error}
        function_source = ast.unparse(function_nodes[function])
        assert f"error.context['{context_key}']" in function_source


def test_analyzer_result_is_explicitly_compatible_with_public_result_type() -> None:
    examples = EXAMPLES.read_text(encoding="utf-8")

    assert "import polis" in examples
    assert "result: polis.AnalysisResult = analyzer.analyze(" in examples
    required_examples = (
        "def root_result_as_core(",
        "def core_result_as_root(",
        "def analyzer_result_as_core(",
        "def analyzer_result_as_root(",
    )
    for signature in required_examples:
        assert signature in examples


def test_adr_uses_the_portable_type_contract_command() -> None:
    adr = ADR.read_text(encoding="utf-8")

    assert PORTABLE_TYPECHECK_COMMAND in adr
    assert TYPECHECK_RUNNER.is_file()


def test_all_public_contract_examples_type_check_strictly() -> None:
    completed = subprocess.run(
        [sys.executable, str(TYPECHECK_RUNNER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
