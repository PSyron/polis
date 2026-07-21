#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/sources"
LOCAL_REPOSITORY="$ROOT_DIR/.m2/repository"

if ! command -v mvn >/dev/null 2>&1; then
  echo "mvn is required for Java build" >&2
  exit 1
fi

JAVA_VERSION="$(java -version 2>&1 | sed -n '1s/.*version "\([^"]*\)".*/\1/p')"
MAVEN_VERSION="$(mvn -version | sed -n '1s/Apache Maven \([^ ]*\).*/\1/p')"
if [[ "$JAVA_VERSION" != "17.0.19" ]]; then
  echo "OpenJDK 17.0.19 is required, found $JAVA_VERSION" >&2
  exit 1
fi
if [[ "$MAVEN_VERSION" != "3.9.16" ]]; then
  echo "Maven 3.9.16 is required, found $MAVEN_VERSION" >&2
  exit 1
fi

if [[ ! -f "$SOURCE_DIR/pom.xml" ]]; then
  echo "Missing source build files; run bootstrap.sh first" >&2
  exit 1
fi

MAVEN_ARGS=(
  "-Dmaven.repo.local=$LOCAL_REPOSITORY"
  "-DskipTests"
  "-Dmaven-jar-plugin.version=3.4.2"
  "-Dproject.build.outputTimestamp=2026-05-05T15:03:23Z"
)
if [[ "${POLIS_LT_OFFLINE:-0}" == "1" ]]; then
  MAVEN_ARGS+=("--offline")
fi

# Install the pinned parent non-recursively, then build only the copied core and
# Polish modules. This intentionally avoids every excluded upstream module.
mvn -f "$SOURCE_DIR/pom.xml" -N "${MAVEN_ARGS[@]}" clean install
mvn -f "$SOURCE_DIR/languagetool-core/pom.xml" "${MAVEN_ARGS[@]}" clean install
mvn -f "$SOURCE_DIR/languagetool-language-modules/pl/pom.xml" \
  "${MAVEN_ARGS[@]}" clean install
mvn -f "$ROOT_DIR/pom.xml" "${MAVEN_ARGS[@]}" clean package

echo "Build finished; artifacts in $ROOT_DIR/target"
