from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tarfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

TARGET_CATEGORIES = frozenset({"inflection", "agreement", "rection", "punctuation"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SPLITS = frozenset({"development", "holdout"})

type Classification = tuple[str, str, bool]


class WikEdProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractionParameters:
    language: str = "polish"
    min_chars: int = 10
    min_words: int = 2
    max_words: int = 120
    length_diff: int = 4
    edit_ratio: float = 0.3

    def as_dict(self) -> dict[str, str | int | float]:
        return {
            "language": self.language,
            "min_chars": self.min_chars,
            "min_words": self.min_words,
            "max_words": self.max_words,
            "length_diff": self.length_diff,
            "edit_ratio": self.edit_ratio,
        }


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    archive_sha256: str
    archive_size_bytes: int
    counts: dict[str, dict[str, int]]
    rejected: dict[str, int]
    development_sha256: str
    holdout_sha256: str


def load_manifest(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WikEdProtocolError("WikEd manifest is unavailable or invalid") from error
    if not isinstance(raw, dict):
        raise WikEdProtocolError("WikEd manifest must be a JSON object")
    if raw.get("schema_id") != "polis.wiked-pl-holdout-manifest":
        raise WikEdProtocolError("WikEd manifest schema is invalid")
    if raw.get("schema_version") != 1:
        raise WikEdProtocolError("WikEd manifest schema version is invalid")
    if raw.get("status") != "blocked_external_authority":
        raise WikEdProtocolError("WikEd manifest must remain blocked pending authority")
    return raw


def load_classifications(path: Path) -> dict[int, Classification]:
    classifications: dict[int, Classification] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise WikEdProtocolError("classification map is unavailable") from error
    for row_number, line in enumerate(lines, start=1):
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise WikEdProtocolError(
                f"classification map line {row_number} is invalid"
            ) from error
        if not isinstance(raw, dict) or set(raw) != {
            "line",
            "category",
            "split",
            "reviewed",
        }:
            raise WikEdProtocolError("classification map fields are invalid")
        line_number = raw["line"]
        category = raw["category"]
        split = raw["split"]
        reviewed = raw["reviewed"]
        if (
            type(line_number) is not int
            or line_number <= 0
            or not isinstance(category, str)
            or not isinstance(split, str)
            or type(reviewed) is not bool
            or line_number in classifications
        ):
            raise WikEdProtocolError("classification map value is invalid")
        classifications[line_number] = (category, split, reviewed)
    return classifications


def extract_archive(
    archive_path: Path,
    output_root: Path,
    *,
    expected_archive_sha256: str | None,
    member_name: str,
    classifications: Mapping[int, Classification],
    repository_root: Path,
    parameters: ExtractionParameters | None = None,
) -> ExtractionResult:
    _require_external_path(archive_path, repository_root, "archive")
    _require_external_path(output_root, repository_root, "output")
    if expected_archive_sha256 is None:
        raise WikEdProtocolError("archive SHA-256 is required before archive open")
    if _SHA256.fullmatch(expected_archive_sha256) is None:
        raise WikEdProtocolError("archive SHA-256 is invalid")
    if (
        not member_name
        or member_name.startswith("/")
        or ".." in Path(member_name).parts
    ):
        raise WikEdProtocolError("archive member name is unsafe")
    try:
        archive_size, archive_sha256 = _file_digest(archive_path)
    except OSError as error:
        raise WikEdProtocolError("external WikEd archive is unavailable") from error
    if archive_sha256 != expected_archive_sha256:
        raise WikEdProtocolError("external WikEd archive SHA-256 mismatch")
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            try:
                member = archive.getmember(member_name)
            except KeyError as error:
                raise WikEdProtocolError(
                    "declared archive member is unavailable"
                ) from error
            if not member.isfile() or member.issym() or member.islnk():
                raise WikEdProtocolError(
                    "declared archive member is not a regular file"
                )
            extracted = archive.extractfile(member)
            if extracted is None:
                raise WikEdProtocolError("declared archive member cannot be read")
            with io.TextIOWrapper(extracted, encoding="utf-8") as source:
                return extract_records(
                    source,
                    classifications,
                    output_root,
                    repository_root=repository_root,
                    archive_sha256=archive_sha256,
                    archive_size_bytes=archive_size,
                    member_name=member_name,
                    parameters=parameters or ExtractionParameters(),
                )
    except UnicodeDecodeError as error:
        raise WikEdProtocolError("declared archive member is not UTF-8") from error
    except (OSError, tarfile.TarError) as error:
        raise WikEdProtocolError("external WikEd archive is invalid") from error


def extract_records(
    lines: Iterable[str],
    classifications: Mapping[int, Classification],
    output_root: Path,
    *,
    repository_root: Path,
    archive_sha256: str = "0" * 64,
    archive_size_bytes: int = 0,
    member_name: str = "synthetic-test-input",
    parameters: ExtractionParameters | None = None,
) -> ExtractionResult:
    _require_external_path(output_root, repository_root, "output")
    output_root.mkdir(parents=True, exist_ok=False)
    os.chmod(output_root, 0o700)
    output_files = {
        split: (output_root / f"{split}.jsonl").open("x", encoding="utf-8")
        for split in _SPLITS
    }
    counts: dict[str, dict[str, int]] = {"development": {}, "holdout": {}}
    rejected: dict[str, int] = {}
    seen_pairs: set[str] = set()
    try:
        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r\n")
            if not line:
                _increment(rejected, "blank")
                continue
            fields = line.split("\t")
            if len(fields) != 2 or not fields[0].strip() or not fields[1].strip():
                raise WikEdProtocolError(
                    f"parallel input line {line_number} is invalid"
                )
            decision = classifications.get(line_number)
            if decision is None or not decision[2]:
                _increment(rejected, "unreviewed")
                continue
            category, split, reviewed = decision
            if category not in TARGET_CATEGORIES:
                _increment(rejected, "out_of_scope")
                continue
            if split not in _SPLITS or not reviewed:
                raise WikEdProtocolError("classification map contains an invalid split")
            pair_digest = hashlib.sha256(
                (fields[0] + "\0" + fields[1]).encode("utf-8")
            ).hexdigest()
            if pair_digest in seen_pairs:
                raise WikEdProtocolError("cross-split duplicate pair")
            seen_pairs.add(pair_digest)
            record = {
                "category": category,
                "line": line_number,
                "old": fields[0],
                "new": fields[1],
            }
            output_files[split].write(
                json.dumps(
                    record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            )
            counts[split][category] = counts[split].get(category, 0) + 1
    finally:
        for output_file in output_files.values():
            output_file.close()
    output_hashes = {
        split: _file_digest(output_root / f"{split}.jsonl")[1] for split in _SPLITS
    }
    result = ExtractionResult(
        archive_sha256,
        archive_size_bytes,
        counts,
        rejected,
        output_hashes["development"],
        output_hashes["holdout"],
    )
    manifest = {
        "schema_id": "polis.wiked-pl-extraction-result",
        "schema_version": 1,
        "archive": {
            "sha256": archive_sha256,
            "size_bytes": archive_size_bytes,
            "member": member_name,
        },
        "extractor": {
            "tool": "snukky/wikiedits",
            "wikiedits_version": "2.0",
            "parameters": (parameters or ExtractionParameters()).as_dict(),
        },
        "outputs": {
            "development": {
                "count": sum(counts["development"].values()),
                "sha256": result.development_sha256,
                "class_counts": counts["development"],
            },
            "holdout": {
                "count": sum(counts["holdout"].values()),
                "sha256": result.holdout_sha256,
                "class_counts": counts["holdout"],
            },
        },
        "rejected": rejected,
        "privacy": {"plaintext_in_logs": False, "repository_plaintext": False},
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    os.chmod(output_root / "manifest.json", 0o600)
    return result


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _require_external_path(path: Path, repository_root: Path, label: str) -> None:
    resolved = path.resolve(strict=False)
    root = repository_root.resolve(strict=False)
    if resolved == root or root in resolved.parents:
        raise WikEdProtocolError(f"{label} must be outside repository")
    parts = resolved.parts
    if any(
        parts[index : index + 2]
        in ((".omo", "sealed"), ("experiments", "a-b-one-shot"))
        for index in range(len(parts) - 1)
    ):
        raise WikEdProtocolError(f"{label} must be outside sealed tree")
    current = resolved
    while current != current.parent:
        if current.is_symlink():
            raise WikEdProtocolError(f"{label} path cannot contain symlinks")
        current = current.parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare an external WikEd PL staging set"
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--member", required=True)
    parser.add_argument("--classification-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _require_external_path(
            args.classification_map, args.repository_root, "classification"
        )
        result = extract_archive(
            args.archive,
            args.output,
            expected_archive_sha256=args.archive_sha256,
            member_name=args.member,
            classifications=load_classifications(args.classification_map),
            repository_root=args.repository_root,
        )
    except WikEdProtocolError as error:
        print(f"wiked extraction blocked: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "archive_sha256": result.archive_sha256,
                "archive_size_bytes": result.archive_size_bytes,
                "counts": result.counts,
                "rejected": result.rejected,
                "development_sha256": result.development_sha256,
                "holdout_sha256": result.holdout_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
