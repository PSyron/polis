#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MAIN_CLASS="${POLIS_LT_MAIN_CLASS:-org.polis.languagetool.PolisStdioServer}"
ARTIFACT="${POLIS_LT_ARTIFACT:-$ROOT_DIR/target/languagetool-pl-stdio-0.1.0-SNAPSHOT.jar}"
DEPENDENCIES="${POLIS_LT_DEPENDENCIES:-$ROOT_DIR/target/dependency/*}"
JAVA_BIN="${JAVA_BIN:-java}"

if [[ ! -f "$ARTIFACT" ]]; then
  echo "Missing artifact $ARTIFACT. Run build.sh first." >&2
  exit 1
fi

if ! compgen -G "$DEPENDENCIES" >/dev/null; then
  echo "Missing runtime dependencies. Run build.sh first." >&2
  exit 1
fi

exec "$JAVA_BIN" -cp "$ARTIFACT:$DEPENDENCIES" "$MAIN_CLASS"
