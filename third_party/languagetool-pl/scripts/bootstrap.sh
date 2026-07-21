#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

UPSTREAM_URL="https://github.com/languagetool-org/languagetool.git"
UPSTREAM_TAG="v6.8"
UPSTREAM_COMMIT="e807fcde6a6506191e1470744d2345da28c26be6"
WORK_DIR="$ROOT_DIR/.upstream"
SOURCE_DIR="$ROOT_DIR/sources"
TEMP_DIR="$ROOT_DIR/.tmp"

if ! command -v git >/dev/null 2>&1 || ! command -v patch >/dev/null 2>&1; then
  echo "git and patch are required for bootstrap" >&2
  exit 1
fi

mkdir -p "$TEMP_DIR"
rm -rf "$SOURCE_DIR"
mkdir -p "$SOURCE_DIR"
if [[ ! -d "$WORK_DIR/.git" ]]; then
  rm -rf "$WORK_DIR"
  git clone --depth=1 "$UPSTREAM_URL" "$WORK_DIR"
fi

git -C "$WORK_DIR" fetch --depth=1 origin "refs/tags/$UPSTREAM_TAG"
git -C "$WORK_DIR" checkout --quiet "$UPSTREAM_COMMIT"

ACTUAL_COMMIT="$(git -C "$WORK_DIR" rev-parse HEAD)"
if [[ "$ACTUAL_COMMIT" != "$UPSTREAM_COMMIT" ]]; then
  echo "Expected $UPSTREAM_COMMIT for $UPSTREAM_TAG, got $ACTUAL_COMMIT" >&2
  exit 1
fi

git -C "$WORK_DIR" archive --format=tar -- "$UPSTREAM_COMMIT" \
  pom.xml \
  languagetool-core/pom.xml \
  languagetool-core/src/main \
  languagetool-language-modules/pl/pom.xml \
  languagetool-language-modules/pl/src/main > "$TEMP_DIR/languagetool-pl.tar"

tar -xpf "$TEMP_DIR/languagetool-pl.tar" -C "$SOURCE_DIR"
patch --directory="$SOURCE_DIR" --strip=1 \
  < "$ROOT_DIR/patches/0001-reproducible-build-metadata.patch"
rm -f "$TEMP_DIR/languagetool-pl.tar"
rmdir "$TEMP_DIR" 2>/dev/null || true

echo "Prepared upstream modules under $SOURCE_DIR"
