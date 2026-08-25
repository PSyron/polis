from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
import tarfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final, Literal, Protocol

TARGET_CATEGORIES = frozenset({"inflection", "agreement", "rection", "punctuation"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SPLITS = frozenset({"development", "holdout"})
_EXPECTED_SOURCE: Final = {
    "name": "WikEd Error Corpus",
    "archive": "wiked-v1.0.pl.tgz",
    "url": "http://data.statmt.org/romang/wiked/wiked-v1.0.pl.tgz",
    "language": "pl",
    "license": "CC-BY-SA-3.0",
    "license_status": "pending_artifact_authority_confirmation",
    "license_basis": "WikEd inherits the license of the source Wikipedia revisions.",
}
_EXPECTED_SELECTION: Final = {
    "target_categories": ["inflection", "agreement", "rection", "punctuation"],
    "classification_source": "external-human-reviewed-line-map",
    "review_required": True,
    "unclassified_action": "reject",
}

type Classification = tuple[str, str, bool]
type ExtractionStatus = Literal["blocked_external_authority"]


class WikEdProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HoldoutReservationRequest:
    archive_sha256: str
    member_name: str


@dataclass(frozen=True, slots=True)
class LeakageCheckRequest:
    development_path: Path
    holdout_path: Path


class HoldoutAuthority(Protocol):
    def reserve_holdout(self, request: HoldoutReservationRequest) -> None: ...

    def check_leakage(self, request: LeakageCheckRequest) -> None: ...


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
    status: ExtractionStatus
    archive_sha256: str
    archive_size_bytes: int
    counts: dict[str, dict[str, int]]
    rejected: dict[str, int]
    development_sha256: str
    holdout_sha256: str
    development_size_bytes: int
    holdout_size_bytes: int


def load_manifest(path: Path) -> dict[str, object]:
    descriptor = -1
    try:
        descriptor = _open_regular_descriptor(path)
        raw = json.loads(_read_descriptor(descriptor).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WikEdProtocolError("WikEd manifest is unavailable or invalid") from error
    finally:
        if descriptor != -1:
            os.close(descriptor)
    if not isinstance(raw, dict):
        raise WikEdProtocolError("WikEd manifest must be a JSON object")
    if raw.get("schema_id") != "polis.wiked-pl-holdout-manifest":
        raise WikEdProtocolError("WikEd manifest schema is invalid")
    if raw.get("schema_version") != 1:
        raise WikEdProtocolError("WikEd manifest schema version is invalid")
    if raw.get("status") != "blocked_external_authority":
        raise WikEdProtocolError("WikEd manifest must remain blocked pending authority")
    _validate_manifest_source(raw)
    _validate_manifest_selection(raw)
    return raw


def _validate_manifest_source(manifest: Mapping[str, object]) -> None:
    if manifest.get("source") != _EXPECTED_SOURCE:
        raise WikEdProtocolError("WikEd manifest source contract is invalid")


def _validate_manifest_selection(manifest: Mapping[str, object]) -> None:
    if manifest.get("selection") != _EXPECTED_SELECTION:
        raise WikEdProtocolError("WikEd manifest selection contract is invalid")


def _validate_manifest_extractor(
    manifest: Mapping[str, object], parameters: ExtractionParameters
) -> None:
    extractor = manifest.get("extractor")
    if not isinstance(extractor, dict):
        raise WikEdProtocolError("WikEd manifest extractor is invalid")
    expected = {
        "tool": "snukky/wikiedits",
        "wikiedits_version": "2.0",
        "revision": None,
        "parameters": parameters.as_dict(),
        "input_format": "UTF-8 tab-separated old/new pairs in a named archive member",
    }
    if extractor != expected:
        raise WikEdProtocolError("WikEd manifest extractor contract is invalid")


def load_classifications(
    path: Path, *, repository_root: Path | None = None
) -> dict[int, Classification]:
    classifications: dict[int, Classification] = {}
    if repository_root is not None:
        _require_external_path(path, repository_root, "classification")
    descriptor = -1
    try:
        descriptor = _open_regular_descriptor(path)
        content = _read_descriptor(descriptor)
        lines = content.decode("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise WikEdProtocolError("classification map is unavailable") from error
    finally:
        if descriptor != -1:
            os.close(descriptor)
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
    authority: HoldoutAuthority | None = None,
) -> ExtractionResult:
    if _has_reviewed_holdout(classifications) and authority is None:
        raise WikEdProtocolError("holdout authority is required")
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
    effective_parameters = parameters or ExtractionParameters()
    manifest = load_manifest(
        repository_root / "docs/project/wiked-pl-holdout-manifest.json"
    )
    _validate_manifest_extractor(manifest, effective_parameters)
    archive_descriptor = -1
    try:
        try:
            archive_descriptor = _open_regular_descriptor(archive_path)
            archive_snapshot = _read_descriptor(archive_descriptor)
            archive_size = len(archive_snapshot)
            archive_sha256 = hashlib.sha256(archive_snapshot).hexdigest()
        except OSError as error:
            raise WikEdProtocolError("external WikEd archive is unavailable") from error
        if archive_sha256 != expected_archive_sha256:
            raise WikEdProtocolError("external WikEd archive SHA-256 mismatch")
        with tarfile.open(fileobj=io.BytesIO(archive_snapshot), mode="r:gz") as archive:
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
                    parameters=effective_parameters,
                    authority=authority,
                )
    except UnicodeDecodeError as error:
        raise WikEdProtocolError("declared archive member is not UTF-8") from error
    except (OSError, tarfile.TarError) as error:
        raise WikEdProtocolError("external WikEd archive is invalid") from error
    finally:
        if archive_descriptor != -1:
            os.close(archive_descriptor)


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
    authority: HoldoutAuthority | None = None,
) -> ExtractionResult:
    _require_external_path(output_root, repository_root, "output")
    effective_parameters = parameters or ExtractionParameters()
    requires_holdout_authority = _has_reviewed_holdout(classifications)
    if requires_holdout_authority and authority is None:
        raise WikEdProtocolError("holdout authority is required")
    if requires_holdout_authority and authority is not None:
        authority.reserve_holdout(
            HoldoutReservationRequest(archive_sha256, member_name)
        )
    output_descriptor = _open_output_directory(output_root)
    try:
        output_files = {
            split: _open_private_text(Path(f"{split}.jsonl"), dir_fd=output_descriptor)
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
                if not _passes_parameters(fields[0], fields[1], effective_parameters):
                    _increment(rejected, "parameters")
                    continue
                decision = classifications.get(line_number)
                if decision is None or not decision[2]:
                    _increment(rejected, "unreviewed")
                    continue
                category, split, reviewed = decision
                if category not in TARGET_CATEGORIES:
                    _increment(rejected, "out_of_scope")
                    continue
                if split not in _SPLITS or not reviewed:
                    raise WikEdProtocolError(
                        "classification map contains an invalid split"
                    )
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
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                counts[split][category] = counts[split].get(category, 0) + 1
        finally:
            for output_file in output_files.values():
                output_file.close()
        output_metadata = {
            split: _file_digest(Path(f"{split}.jsonl"), dir_fd=output_descriptor)
            for split in _SPLITS
        }
        if requires_holdout_authority and authority is not None:
            authority.check_leakage(
                LeakageCheckRequest(
                    output_root / "development.jsonl", output_root / "holdout.jsonl"
                )
            )
        result = ExtractionResult(
            "blocked_external_authority",
            archive_sha256,
            archive_size_bytes,
            counts,
            rejected,
            output_metadata["development"][1],
            output_metadata["holdout"][1],
            output_metadata["development"][0],
            output_metadata["holdout"][0],
        )
        manifest = {
            "schema_id": "polis.wiked-pl-extraction-result",
            "schema_version": 1,
            "status": result.status,
            "archive": {
                "sha256": archive_sha256,
                "size_bytes": archive_size_bytes,
                "member": member_name,
            },
            "extractor": {
                "tool": "snukky/wikiedits",
                "wikiedits_version": "2.0",
                "parameters": effective_parameters.as_dict(),
            },
            "outputs": {
                "development": {
                    "count": sum(counts["development"].values()),
                    "size_bytes": result.development_size_bytes,
                    "sha256": result.development_sha256,
                    "class_counts": counts["development"],
                },
                "holdout": {
                    "count": sum(counts["holdout"].values()),
                    "size_bytes": result.holdout_size_bytes,
                    "sha256": result.holdout_sha256,
                    "class_counts": counts["holdout"],
                },
            },
            "rejected": rejected,
            "leakage": {
                "status": "not_run",
                "validated": False,
                "reason": "external_authority_and_existing_corpora_unavailable",
            },
            "authorization": {
                "reservation_contract": "polis.evaluation.holdout_reservation",
                "status": "not_authorized",
                "reservation_established": False,
            },
            "privacy": {"plaintext_in_logs": False, "repository_plaintext": False},
        }
        _write_private_bytes(
            Path("manifest.json"),
            (
                json.dumps(
                    manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            ).encode("utf-8"),
            dir_fd=output_descriptor,
        )
        return result
    finally:
        os.close(output_descriptor)


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _has_reviewed_holdout(classifications: Mapping[int, Classification]) -> bool:
    return any(
        category in TARGET_CATEGORIES and split == "holdout" and reviewed
        for category, split, reviewed in classifications.values()
    )


def _passes_parameters(old: str, new: str, parameters: ExtractionParameters) -> bool:
    old_words = len(old.split())
    new_words = len(new.split())
    return (
        len(old) >= parameters.min_chars
        and len(new) >= parameters.min_chars
        and old_words >= parameters.min_words
        and new_words >= parameters.min_words
        and old_words <= parameters.max_words
        and new_words <= parameters.max_words
        and abs(len(old) - len(new)) <= parameters.length_diff
        and _edit_ratio(old, new) <= parameters.edit_ratio
    )


def _edit_ratio(old: str, new: str) -> float:
    changed = sum(
        max(old_end - old_start, new_end - new_start)
        for tag, old_start, old_end, new_start, new_end in SequenceMatcher(
            None, old, new, autojunk=False
        ).get_opcodes()
        if tag != "equal"
    )
    return changed / max(len(old), len(new), 1)


def _file_digest(path: Path, *, dir_fd: int) -> tuple[int, str]:
    descriptor = _open_regular_descriptor(path, dir_fd=dir_fd)
    try:
        return _descriptor_digest(descriptor)
    finally:
        os.close(descriptor)


def _descriptor_digest(descriptor: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    os.lseek(descriptor, 0, os.SEEK_SET)
    while chunk := os.read(descriptor, 1024 * 1024):
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def _secure_directory_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise OSError("required O_NOFOLLOW and O_DIRECTORY support is unavailable")
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY


def _open_directory_path(path: Path, *, create_missing: bool) -> int:
    absolute = Path(os.path.abspath(path))
    descriptor = os.open(absolute.anchor, _secure_directory_flags())
    completed = False
    try:
        for component in absolute.parts[1:]:
            try:
                next_descriptor = os.open(
                    component,
                    _secure_directory_flags(),
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create_missing:
                    raise
                os.mkdir(component, 0o700, dir_fd=descriptor)
                next_descriptor = os.open(
                    component,
                    _secure_directory_flags(),
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = next_descriptor
        completed = True
    finally:
        if not completed:
            os.close(descriptor)
    return descriptor


def _open_output_directory(path: Path) -> int:
    parent = _open_directory_path(path.parent, create_missing=True)
    try:
        if not path.name or path.name in {".", ".."}:
            raise WikEdProtocolError("output directory name is invalid")
        os.mkdir(path.name, 0o700, dir_fd=parent)
        descriptor = os.open(
            path.name,
            _secure_directory_flags(),
            dir_fd=parent,
        )
        os.fchmod(descriptor, 0o700)
        return descriptor
    except FileExistsError as error:
        raise WikEdProtocolError("output directory already exists") from error
    except OSError as error:
        raise WikEdProtocolError("output directory is unavailable") from error
    finally:
        os.close(parent)


def _open_regular_descriptor(path: Path, *, dir_fd: int | None = None) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError("required O_NOFOLLOW support is unavailable")
    parent_descriptor = -1
    if dir_fd is None:
        parent_descriptor = _open_directory_path(path.parent, create_missing=False)
        open_path: str | Path = path.name
        open_dir_fd: int | None = parent_descriptor
    else:
        open_path = path
        open_dir_fd = dir_fd
    descriptor = -1
    try:
        descriptor = os.open(
            open_path,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=open_dir_fd,
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("path is not a regular file")
    except OSError:
        if descriptor != -1:
            os.close(descriptor)
        raise
    finally:
        if parent_descriptor != -1:
            os.close(parent_descriptor)
    return descriptor


def _open_private_text(path: Path, *, dir_fd: int) -> io.TextIOWrapper:
    if not hasattr(os, "O_NOFOLLOW"):
        raise WikEdProtocolError("required O_NOFOLLOW support is unavailable")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=dir_fd,
    )
    try:
        return os.fdopen(descriptor, "w", encoding="utf-8")
    except OSError:
        os.close(descriptor)
        raise


def _write_private_bytes(path: Path, content: bytes, *, dir_fd: int) -> None:
    if not hasattr(os, "O_NOFOLLOW"):
        raise WikEdProtocolError("required O_NOFOLLOW support is unavailable")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=dir_fd,
    )
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
    finally:
        os.close(descriptor)


def _require_external_path(path: Path, repository_root: Path, label: str) -> None:
    candidate = path if path.is_absolute() else Path.cwd() / path
    current = Path(candidate.anchor)
    for component in candidate.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise WikEdProtocolError(f"{label} path cannot be inspected") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise WikEdProtocolError(f"{label} path cannot contain symlinks")
    resolved = candidate.resolve(strict=False)
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


def _require_cli_repository_root(repository_root: Path) -> Path:
    actual_root = Path(__file__).resolve().parents[1]
    try:
        supplied_root = repository_root.resolve(strict=True)
    except OSError as error:
        raise WikEdProtocolError("repository root cannot be verified") from error
    if supplied_root != actual_root:
        raise WikEdProtocolError("repository root does not match script repository")
    return actual_root


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repository_root = _require_cli_repository_root(args.repository_root)
        result = extract_archive(
            args.archive,
            args.output,
            expected_archive_sha256=args.archive_sha256,
            member_name=args.member,
            classifications=load_classifications(
                args.classification_map, repository_root=repository_root
            ),
            repository_root=repository_root,
        )
    except WikEdProtocolError as error:
        print(f"wiked extraction blocked: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result.status,
                "archive_sha256": result.archive_sha256,
                "archive_size_bytes": result.archive_size_bytes,
                "counts": result.counts,
                "rejected": result.rejected,
                "development_sha256": result.development_sha256,
                "holdout_sha256": result.holdout_sha256,
                "development_size_bytes": result.development_size_bytes,
                "holdout_size_bytes": result.holdout_size_bytes,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
