from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "third_party" / "languagetool-pl"


def test_vendor_manifest_has_provenance_and_required_licenses() -> None:
    manifest = json.loads((MODULE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert (
        manifest["upstream"]["repository"]
        == "https://github.com/languagetool-org/languagetool.git"
    )
    assert manifest["upstream"]["commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert manifest["upstream"]["tag"] == "v6.8"
    assert manifest["upstream"]["version"] == "6.8"
    assert manifest["language"] == "pl-PL"
    assert manifest["license"] == "LGPL-2.1-or-later"
    assert (
        manifest["resource_license_notices"]["org/languagetool/resource/pl/README.txt"]
        == "BSD-2-Clause"
    )
    assert (
        "LGPL"
        in manifest["resource_license_notices"][
            "org/languagetool/resource/pl/hunspell/README_en.txt"
        ]
    )
    assert (
        "languagetool-language-modules/pl/src/main"
        in manifest["included_upstream_paths"]
    )

    assert (MODULE_ROOT / "LICENSE-LGPL-2.1.txt").exists()
    assert (MODULE_ROOT / "NOTICE").exists()
    assert (MODULE_ROOT / "UPSTREAM.md").exists()


def test_vendor_module_contains_stable_runtime_support_files() -> None:
    assert (MODULE_ROOT / "README.md").exists()
    assert (MODULE_ROOT / "manifest.json").exists()
    assert (MODULE_ROOT / "scripts" / "benchmark.sh").is_file()
    assert os.access(MODULE_ROOT / "scripts" / "benchmark.sh", os.X_OK)
    assert (MODULE_ROOT / "scripts" / "benchmark.py").is_file()
    assert (MODULE_ROOT / "scripts" / "run_stdio.sh").is_file()


def test_vendor_contains_corresponding_core_and_polish_sources() -> None:
    required_sources = (
        "sources/languagetool-core/src/main/java/org/languagetool/JLanguageTool.java",
        "sources/languagetool-language-modules/pl/src/main/java/"
        "org/languagetool/language/Polish.java",
        "sources/languagetool-language-modules/pl/src/main/resources/"
        "org/languagetool/rules/pl/grammar.xml",
    )

    for relative_path in required_sources:
        assert (MODULE_ROOT / relative_path).is_file(), relative_path


def test_upstream_build_metadata_patch_is_declared_and_deterministic() -> None:
    manifest = json.loads((MODULE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    modified_paths = {item["path"] for item in manifest["modified_upstream_files"]}

    assert modified_paths == {
        "languagetool-core/pom.xml",
        "languagetool-core/src/main/resources/git.properties",
    }
    patch = MODULE_ROOT / "patches" / "0001-reproducible-build-metadata.patch"
    assert patch.is_file()

    build_info = (
        MODULE_ROOT / "sources/languagetool-core/src/main/resources/git.properties"
    ).read_text(encoding="utf-8")
    assert "git.commit.id.abbrev=e807fcd" in build_info
    assert "git.build.version=6.8" in build_info
    assert "git.build.user" not in build_info
    assert "git.branch" not in build_info


def test_stdio_bridge_invokes_language_tool_instead_of_corpus_lookup() -> None:
    source = (
        MODULE_ROOT / "src/main/java/org/polis/languagetool/PolisStdioServer.java"
    ).read_text(encoding="utf-8")

    assert "org.languagetool.JLanguageTool" in source
    assert "org.languagetool.language.Polish" in source
    assert "BRAK_PRZECINKA_ZE" in source
    assert "BRAK_PRZECINKA_ZEBY" in source
    assert "ALLOWLIST = Map.ofEntries" not in source
    assert "Wiem że Ania już wróciła." not in source
