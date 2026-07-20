from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/architecture/decisions/0001-python-platform-licensing-policy.md"
INDEX = ROOT / "docs/architecture/README.md"


class ArchitecturePolicyTests(unittest.TestCase):
    def test_architecture_index_links_accepted_adr(self) -> None:
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn(
            "| [ADR-0001](decisions/0001-python-platform-licensing-policy.md) | "
            "Accepted | Python, platform, licensing, and asset policy |",
            index,
        )

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
        plan = (
            ROOT / "docs/superpowers/plans/2026-07-20-issue-1-policy.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("superpowers:", plan)


if __name__ == "__main__":
    unittest.main()
