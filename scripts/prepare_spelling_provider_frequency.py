from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
import tempfile
from pathlib import Path

EXPECTED_FIELDS = (
    "word",
    "wordLen",
    "urlcount",
    "totalcount",
    "adjFreq",
    "deleted",
    "whyDeleted",
    "Rank",
    "corrected",
    "english",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the pinned two-column Polish SymSpell frequency file."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    return parser


def _write_frequency_file(input_path: Path, output_path: Path) -> int:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("input and output must be different files")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with (
            input_path.open(encoding="utf-8", newline="") as source,
            os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target,
        ):
            reader = csv.DictReader(source)
            if tuple(reader.fieldnames or ()) != EXPECTED_FIELDS:
                raise ValueError("unexpected K7TRY CSV header")
            selected = 0
            for row in reader:
                word = row["word"].strip().lower()
                if row["deleted"] != "1" and word.isalpha() and len(word) >= 2:
                    target.write(f"{word} {max(int(row['totalcount']), 1)}\n")
                    selected += 1
        os.replace(temporary, output_path)
        return selected
    except (OSError, UnicodeError, ValueError, csv.Error):
        temporary.unlink(missing_ok=True)
        raise


def main(arguments: list[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    try:
        if len(options.expected_input_sha256) != 64:
            raise ValueError("expected input digest must be SHA-256")
        actual = _sha256(options.input)
        if actual != options.expected_input_sha256:
            raise ValueError("input digest mismatch")
        selected = _write_frequency_file(options.input, options.output)
        print(f"{selected} terms; output_sha256={_sha256(options.output)}")
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        print(f"frequency preparation failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
