#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT_PATH="$ROOT_DIR" python3 - <<'PY'
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


root = Path(os.environ["ROOT_PATH"])
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
if manifest["upstream"] != {
    "repository": "https://github.com/languagetool-org/languagetool.git",
    "tag": "v6.8",
    "version": "6.8",
    "commit": "e807fcde6a6506191e1470744d2345da28c26be6",
    "retrieved_utc": "2026-07-21T00:00:00Z",
}:
    raise SystemExit("manifest upstream identity is not the reviewed v6.8 release")
expected_modified_paths = {
    "languagetool-core/pom.xml",
    "languagetool-core/src/main/resources/git.properties",
}
if {entry["path"] for entry in manifest.get("modified_upstream_files", [])} != expected_modified_paths:
    raise SystemExit("manifest does not identify the reviewed reproducible-build patch")

required_files = [
    "LICENSE-LGPL-2.1.txt",
    "UPSTREAM.md",
    "NOTICE",
    "README.md",
    "BENCHMARK.md",
    "pom.xml",
    "sources/pom.xml",
    "sources/languagetool-core/pom.xml",
    "sources/languagetool-core/src/main/resources/git.properties",
    "sources/languagetool-core/src/main/java/org/languagetool/JLanguageTool.java",
    "sources/languagetool-language-modules/pl/pom.xml",
    "sources/languagetool-language-modules/pl/src/main/java/org/languagetool/language/Polish.java",
    "sources/languagetool-language-modules/pl/src/main/resources/org/languagetool/rules/pl/grammar.xml",
    "src/main/java/org/polis/languagetool/PolisStdioServer.java",
    "patches/0001-reproducible-build-metadata.patch",
]
required_files.extend(manifest["project_files"])
for relative_path in required_files:
    if not (root / relative_path).is_file():
        raise SystemExit(f"missing required module file: {relative_path}")

server_source = (root / "src/main/java/org/polis/languagetool/PolisStdioServer.java").read_text(
    encoding="utf-8"
)
for forbidden in ("ALLOWLIST = Map.ofEntries", "Wiem że Ania już wróciła."):
    if forbidden in server_source:
        raise SystemExit("stdio bridge contains a corpus-derived lookup")
for required in (
    "org.languagetool.JLanguageTool",
    "org.languagetool.language.Polish",
    "BRAK_PRZECINKA_ZE",
    "BRAK_PRZECINKA_ZEBY",
):
    if required not in server_source:
        raise SystemExit(f"stdio bridge is missing real-engine marker: {required}")

build_info = (
    root / "sources/languagetool-core/src/main/resources/git.properties"
).read_text(encoding="utf-8")
for required in (
    "git.build.time=2026-05-05T17:03:23+0200",
    "git.commit.id.abbrev=e807fcd",
    "git.build.version=6.8",
):
    if required not in build_info:
        raise SystemExit(f"deterministic build metadata is missing: {required}")
for forbidden in ("git.build.user", "git.branch"):
    if forbidden in build_info:
        raise SystemExit(f"local repository metadata leaked into build info: {forbidden}")

help_result = subprocess.run(
    [os.fspath(root / "scripts/benchmark.sh"), "--help"],
    capture_output=True,
    check=False,
    text=True,
    timeout=10,
)
if help_result.returncode != 0 or "usage" not in help_result.stdout.lower():
    raise SystemExit("benchmark helper entry point is not callable")

jar = root / "target/languagetool-pl-stdio-0.1.0-SNAPSHOT.jar"
dependencies = root / "target/dependency"
if jar.is_file() and dependencies.is_dir():
    runtime = subprocess.run(
        [os.fspath(root / "scripts/run_stdio.sh")],
        input=(
            '{"text":"Powiedział że jutro wróci.","language":"pl-PL"}\n'
            '{"text":"Powiedział, że jutro wróci.","language":"pl-PL"}\n'
        ),
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    responses = [json.loads(line) for line in runtime.stdout.splitlines()]
    if len(responses) != 2:
        raise SystemExit("stdio bridge did not return one response per request")
    rule_ids = {match["rule"]["id"] for match in responses[0]["matches"]}
    if "BRAK_PRZECINKA_ZE" not in rule_ids:
        raise SystemExit("real engine did not find the unseen comma case")
    if responses[1]["matches"] != []:
        raise SystemExit("real engine changed the unseen correct control")

print("vendored LanguageTool sources, provenance, and runtime boundary verified")
PY

if [[ -d "$ROOT_DIR/.upstream/.git" ]]; then
  VERIFY_TEMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$VERIFY_TEMP_DIR"' EXIT
  mkdir -p "$VERIFY_TEMP_DIR/languagetool-core"
  cp "$ROOT_DIR/sources/languagetool-core/pom.xml" \
    "$VERIFY_TEMP_DIR/languagetool-core/pom.xml"
  cp -R "$ROOT_DIR/sources/languagetool-core/src" \
    "$VERIFY_TEMP_DIR/languagetool-core/src"
  patch --quiet --reverse --directory="$VERIFY_TEMP_DIR" --strip=1 \
    < "$ROOT_DIR/patches/0001-reproducible-build-metadata.patch"
  diff -qr \
    "$VERIFY_TEMP_DIR/languagetool-core/pom.xml" \
    "$ROOT_DIR/.upstream/languagetool-core/pom.xml"
  diff -qr \
    "$VERIFY_TEMP_DIR/languagetool-core/src/main" \
    "$ROOT_DIR/.upstream/languagetool-core/src/main"
  diff -qr \
    "$ROOT_DIR/sources/languagetool-language-modules/pl/src/main" \
    "$ROOT_DIR/.upstream/languagetool-language-modules/pl/src/main"
fi
