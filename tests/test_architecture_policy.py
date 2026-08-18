import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/architecture/decisions/0001-python-platform-licensing-policy.md"
CONSERVATIVE_V1_ADR = (
    ROOT / "docs/architecture/decisions/0022-conservative-v1-product-scope.md"
)
INDEX = ROOT / "docs/architecture/README.md"
PROMPT = ROOT / "PROMPT.md"
RULE_CATALOG_ADR = "decisions/0021-rule-catalog-ownership.md"


class ArchitecturePolicyTests(unittest.TestCase):
    def test_architecture_index_links_accepted_adr(self) -> None:
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn(
            "| [ADR-0001](decisions/0001-python-platform-licensing-policy.md) | "
            "Zaakceptowany | Polityka wersji Pythona, platform, licencji i zasobów |",
            index,
        )

    def test_architecture_index_covers_every_accepted_adr_exactly_once(self) -> None:
        index = INDEX.read_text(encoding="utf-8")
        accepted = {
            path.name
            for path in (INDEX.parent / "decisions").glob("*.md")
            if "Status: Accepted" in path.read_text(encoding="utf-8")
        }
        linked = re.findall(r"\(decisions/([^)]+\.md)\)", index)

        self.assertEqual(len(accepted), 30)
        self.assertEqual(set(linked), accepted)
        self.assertEqual(len(linked), len(set(linked)))
        self.assertNotIn("<!--", index)

    def test_architecture_index_links_rule_catalog_decision(self) -> None:
        index = INDEX.read_text(encoding="utf-8")

        self.assertIn(f"({RULE_CATALOG_ADR})", index)

    def test_conservative_v1_decision_is_indexed_and_traceable(self) -> None:
        adr = CONSERVATIVE_V1_ADR.read_text(encoding="utf-8")
        index = INDEX.read_text(encoding="utf-8")

        self.assertIn("Status: Accepted", adr)
        self.assertIn("#185", adr)
        self.assertIn("../../project/v2-research-archive-manifest.md", adr)
        self.assertIn(
            "decisions/0022-conservative-v1-product-scope.md",
            index,
        )

    def test_conservative_v1_decides_every_legacy_configuration_surface(self) -> None:
        adr = CONSERVATIVE_V1_ADR.read_text(encoding="utf-8")

        for surface in (
            "use_local_heuristic_backend",
            "language_tool_url",
            "language_tool_timeout_seconds",
            "contextual_inflection_stdio_path",
            "contextual_inflection_timeout_seconds",
            "vendored_language_tool_stdio_path",
            "vendored_language_tool_timeout_seconds",
            "AnalyzerConfig.from_toml",
            "AnalyzerConfig.from_config",
            "[backend]",
            "use_mock",
            "[language_tool]",
            "base_url",
            "[contextual_inflection]",
            "[vendored_language_tool]",
            "stdio_path",
            "timeout_seconds",
        ):
            with self.subTest(surface=surface):
                self.assertIn(f"`{surface}`", adr)

        for contract in (
            "is not supported in Polis v1",
            "retryable=False",
            "LocalGenerationBackend",
            "LocalFindingBackend",
            "MonotonicClock",
            "SourceKind.LLM",
            "SuggestionOutcome",
            "polis.evaluation",
            "ADR-0019",
            "ADR-0021",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, adr)

    def test_prompt_excludes_semantic_and_tense_aspect_corrections(self) -> None:
        prompt = " ".join(PROMPT.read_text(encoding="utf-8").split()).casefold()

        self.assertIn("nie zmienia znaczenia", prompt)
        self.assertIn("zgodność czasów i aspektu", prompt)
        self.assertIn("w razie wątpliwości nie sugeruje zmiany", prompt)

    def test_protocol_documentation_records_v1_source_policy_boundary(self) -> None:
        content = (INDEX.parent / "protocols.md").read_text(encoding="utf-8")

        self.assertIn("source-policy", content)
        self.assertIn("ADR-0022", content)
        self.assertNotIn("LocalGenerationBackend", content)

    def test_task_13_architecture_guides_are_removed(self) -> None:
        for relative_path in (
            "contextual-inflection-routing-design.md",
            "finetuning-dataset.md",
            "languagetool-rule-inventory-design.md",
            "sentence-category-routing-design.md",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertFalse((INDEX.parent / relative_path).exists())

    def test_adr_records_python_and_platform_contract(self) -> None:
        adr = ADR.read_text(encoding="utf-8")
        required = (
            "Polis will provide an offline, pure-Python core and may gain optional "
            "native adapters.",
            "Installation metadata accepts CPython >=3.12 through "
            '`requires-python = ">=3.12"` and has no upper bound.',
            "The initially tested and supported minors are CPython 3.12, CPython "
            "3.13, and CPython 3.14.",
            "Newer untested minors are best-effort until they are promoted after "
            "the CI matrix passes.",
            "Per-change CI uses this initial representative matrix, not Cartesian "
            "all-platform coverage:",
            "| `ubuntu-24.04` | x86_64 | CPython 3.12, CPython 3.13, CPython 3.14 |",
            "| `macos-15` | arm64 | CPython 3.12, CPython 3.14 |",
            "| `windows-2025` | x86_64 | CPython 3.12, CPython 3.14 |",
            "These runner labels are pinned and reviewed when the provider retires "
            "an image.",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, adr)

    def test_adr_records_licensing_and_asset_contract(self) -> None:
        adr = ADR.read_text(encoding="utf-8")
        required = (
            'M0-03 must set `license = "MIT"` and `license-files = ["LICENSE"]`.',
            "Deprecated `License ::` classifiers are not used.",
            "Both the built wheel and sdist must verify `License-Expression: MIT` "
            "and `License-File: LICENSE`.",
            "The allowlist applies to direct and transitive runtime, optional, "
            "build, and development dependencies.",
            "Compound expressions and expressions outside this allowlist require a "
            "dedicated review before adoption.",
            "Every redistributed CC-BY-4.0 dataset or subset must ship attribution "
            "and provenance.",
            "Retain the creator, copyright notice if supplied, license link, source "
            "link where practicable, and modification indication.",
            "Before model support is claimed, review must confirm that publisher "
            "terms permit the intended local use.",
            "Document material restrictions, redistribution status, attribution, and "
            "the exact revision.",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, adr)

    def test_adr_uses_authoritative_references(self) -> None:
        adr = ADR.read_text(encoding="utf-8")
        required_hosts = (
            "devguide.python.org/versions",
            "packaging.python.org/en/latest/guides/dropping-older-python-versions",
            "opensource.org/license/mit",
            "spdx.org/licenses",
            "creativecommons.org/licenses/by/4.0",
        )
        for host in required_hosts:
            with self.subTest(host=host):
                self.assertIn(host, adr)

    def test_plan_avoids_agent_specific_tool_instructions(self) -> None:
        plan = (ROOT / "docs/superpowers/plans/2026-07-20-issue-1-policy.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("superpowers:", plan)


if __name__ == "__main__":
    unittest.main()
