"""Regression boundary for the retained LanguageTool provenance shell."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "third_party" / "languagetool-pl"
PROVENANCE_SHA256 = {
    "LICENSE-LGPL-2.1.txt": (
        "02eac5045df5a207f602b73e2a60b53a283a3bae052d911648b72eaa6b53c291"
    ),
    "NOTICE": "3f1048986a84de6a651edf22e1cdc8120f8d9901a8bca36e3adc510e623b7af0",
    "README.md": "e17d0d0039e697523e42ef05fe7b8228d8c1872baa8042b11e9360e6dd5dc211",
    "UPSTREAM.md": "c54e6504802564cbe4a264fe0006722bde00ba29725bef5c979843385d912fbb",
    "BENCHMARK.md": "97b755f128c5a11c7fa951497cc4b0d6a77f3b5dafdfd3d84e4d5e59902c4b87",
    "manifest.json": "d5871e8173addb96cc93e2f8ce6833737f08a20c4fc47e99596b4d82b8f3f6e8",
    "patches/0001-reproducible-build-metadata.patch": (
        "26c294a55c0c56b30363910b6f0caf1aab91cd7031c9d74552f633e4649eaac6"
    ),
}
EXECUTABLE_VENDOR_PATHS = (
    "sources",
    "src",
    "pom.xml",
    "scripts/benchmark.py",
    "scripts/benchmark.sh",
    "scripts/bootstrap.sh",
    "scripts/build.sh",
    "scripts/run_stdio.sh",
    "scripts/verify.sh",
)


def test_vendored_languagetool_is_a_provenance_shell() -> None:
    assert VENDOR_ROOT.is_dir()

    for relative_path, expected_sha256 in PROVENANCE_SHA256.items():
        path = VENDOR_ROOT / relative_path
        assert path.is_file(), relative_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256

    for relative_path in EXECUTABLE_VENDOR_PATHS:
        assert not (VENDOR_ROOT / relative_path).exists(), relative_path
