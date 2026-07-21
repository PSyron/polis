#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

JAR="${POLIS_LT_JAR:-$SCRIPT_DIR/../target/languagetool-pl-stdio-0.1.0-SNAPSHOT.jar}"
DEPENDENCIES="${POLIS_LT_DEPENDENCIES:-$SCRIPT_DIR/../target/dependency}"
CORPUS="${POLIS_LT_CORPUS:-$ROOT_DIR/tests/fixtures/e2e/polish_correction_corpus.json}"

# Use JAVA_BIN env to override java executable path if needed (e.g. custom JDK install).
python3 "$SCRIPT_DIR/benchmark.py" \
  --jar "$JAR" \
  --dependencies "$DEPENDENCIES" \
  --corpus "$CORPUS" \
  "$@"
