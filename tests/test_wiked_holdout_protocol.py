from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tarfile
from collections.abc import Callable
from pathlib import Path

import pytest
import scripts.wiked_holdout as protocol
from scripts.wiked_holdout import (
    ExtractionParameters,
    WikEdProtocolError,
    extract_archive,
    extract_records,
    load_manifest,
)


def _synthetic_archive(path: Path) -> str:
    payload = b"synthetic old\tsynthetic new\n"
    with tarfile.open(path, "w:gz") as bundle:
        info = tarfile.TarInfo("pairs.tsv")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pending_manifest_records_the_external_authority_limitation() -> None:
    manifest = load_manifest(Path("docs/project/wiked-pl-holdout-manifest.json"))

    assert manifest["status"] == "blocked_external_authority"
    source = manifest["source"]
    assert isinstance(source, dict)
    assert source["license"] == "CC-BY-SA-3.0"
    assert source["license_status"] == "pending_artifact_authority_confirmation"
    extractor = manifest["extractor"]
    assert isinstance(extractor, dict)
    assert extractor["wikiedits_version"] == "2.0"
    assert extractor["parameters"] == ExtractionParameters().as_dict()
    assert manifest["privacy"]["plaintext_in_repository"] is False
    assert manifest["privacy"]["plaintext_in_logs"] is False


def test_archive_digest_is_required_before_archive_open(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.tgz"
    archive.write_bytes(b"not opened")
    output = tmp_path / "output"

    with pytest.raises(WikEdProtocolError, match="archive SHA-256 is required"):
        extract_archive(
            archive,
            output,
            expected_archive_sha256=None,
            member_name="pairs.tsv",
            classifications={},
            repository_root=tmp_path / "repository",
        )


def test_extract_records_writes_only_reviewed_target_classes_and_counts_rejections(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    result = extract_records(
        [
            "synthetic old\tsynthetic new\n",
            "ignored old\tignored new\n",
            "unreviewed old\tunreviewed new\n",
        ],
        {
            1: ("agreement", "development", True),
            2: ("style", "development", True),
            3: ("punctuation", "holdout", False),
        },
        output,
        repository_root=tmp_path / "repository",
    )

    assert result.counts == {
        "development": {"agreement": 1},
        "holdout": {},
    }
    assert result.rejected == {
        "out_of_scope": 1,
        "unreviewed": 1,
    }
    assert (output / "development.jsonl").read_text() == (
        '{"category":"agreement","line":1,"new":"synthetic new",'
        '"old":"synthetic old"}\n'
    )
    assert (output / "holdout.jsonl").read_text() == ""


def test_extraction_result_cannot_claim_leakage_or_holdout_authorization(
    tmp_path: Path,
) -> None:
    result = extract_records(
        ["synthetic old\tsynthetic new\n"],
        {1: ("agreement", "development", True)},
        tmp_path / "output",
        repository_root=tmp_path / "repository",
    )

    manifest = json.loads((tmp_path / "output" / "manifest.json").read_text())
    assert result.status == "blocked_external_authority"
    assert manifest["status"] == "blocked_external_authority"
    assert manifest["leakage"] == {
        "status": "not_run",
        "validated": False,
        "reason": "external_authority_and_existing_corpora_unavailable",
    }
    assert manifest["authorization"] == {
        "reservation_contract": "polis.evaluation.holdout_reservation",
        "status": "not_authorized",
        "reservation_established": False,
    }


@pytest.mark.parametrize(
    ("parameters", "line"),
    [
        (ExtractionParameters(min_chars=20), "short text\tshort edit\n"),
        (ExtractionParameters(min_words=3), "two words\ttwo words\n"),
        (ExtractionParameters(max_words=2), "one two three\tone two three\n"),
        (
            ExtractionParameters(length_diff=1),
            "synthetic words old\tsynthetic words\n",
        ),
        (
            ExtractionParameters(edit_ratio=0.1),
            "abcdefghij words\tzyxwvutsrq words\n",
        ),
    ],
)
def test_extraction_applies_each_declared_filter_parameter(
    parameters: ExtractionParameters, line: str, tmp_path: Path
) -> None:
    result = extract_records(
        [line],
        {1: ("agreement", "development", True)},
        tmp_path / "output",
        repository_root=tmp_path / "repository",
        parameters=parameters,
    )

    assert result.counts == {"development": {}, "holdout": {}}
    assert result.rejected == {"parameters": 1}


def test_holdout_extraction_rejects_absent_injected_authority(tmp_path: Path) -> None:
    with pytest.raises(WikEdProtocolError, match="holdout authority is required"):
        extract_records(
            ["synthetic old\tsynthetic new\n"],
            {1: ("agreement", "holdout", True)},
            tmp_path / "output",
            repository_root=tmp_path / "repository",
        )

    assert not (tmp_path / "output").exists()


def test_archive_extraction_rejects_absent_authority_before_archive_open(
    tmp_path: Path,
) -> None:
    with pytest.raises(WikEdProtocolError, match="holdout authority is required"):
        extract_archive(
            tmp_path / "unopened.tgz",
            tmp_path / "output",
            expected_archive_sha256="0" * 64,
            member_name="pairs.tsv",
            classifications={1: ("agreement", "holdout", True)},
            repository_root=tmp_path / "repository",
        )

    assert not (tmp_path / "output").exists()


class _SyntheticAuthority:
    def __init__(self) -> None:
        self.reservations: list[protocol.HoldoutReservationRequest] = []
        self.leakage_checks: list[protocol.LeakageCheckRequest] = []

    def reserve_holdout(self, request: protocol.HoldoutReservationRequest) -> None:
        self.reservations.append(request)

    def check_leakage(self, request: protocol.LeakageCheckRequest) -> None:
        self.leakage_checks.append(request)


def test_holdout_extraction_uses_injected_synthetic_authority(
    tmp_path: Path,
) -> None:
    authority = _SyntheticAuthority()
    output = tmp_path / "output"

    result = extract_records(
        ["synthetic old\tsynthetic new\n"],
        {1: ("agreement", "holdout", True)},
        output,
        repository_root=tmp_path / "repository",
        authority=authority,
    )

    manifest = json.loads((output / "manifest.json").read_text())
    assert len(authority.reservations) == 1
    assert authority.reservations[0].member_name == "synthetic-test-input"
    assert len(authority.leakage_checks) == 1
    assert authority.leakage_checks[0].holdout_path == output / "holdout.jsonl"
    assert result.status == "blocked_external_authority"
    assert manifest["leakage"] == {
        "status": "not_run",
        "validated": False,
        "reason": "external_authority_and_existing_corpora_unavailable",
    }
    assert manifest["authorization"] == {
        "reservation_contract": "polis.evaluation.holdout_reservation",
        "status": "not_authorized",
        "reservation_established": False,
    }


def test_output_plaintext_files_are_private_from_creation(tmp_path: Path) -> None:
    output = tmp_path / "output"
    extract_records(
        ["synthetic old\tsynthetic new\n"],
        {1: ("agreement", "development", True)},
        output,
        repository_root=tmp_path / "repository",
    )

    for path in (
        output / "development.jsonl",
        output / "holdout.jsonl",
        output / "manifest.json",
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_duplicate_pair_is_rejected_across_splits(tmp_path: Path) -> None:
    output = tmp_path / "output"
    with pytest.raises(WikEdProtocolError, match="cross-split duplicate"):
        extract_records(
            ["same old\tsame new\n", "same old\tsame new\n"],
            {
                1: ("agreement", "development", True),
                2: ("agreement", "holdout", True),
            },
            output,
            repository_root=tmp_path / "repository",
            parameters=ExtractionParameters(min_chars=1, min_words=1, edit_ratio=1.0),
            authority=_SyntheticAuthority(),
        )


def test_archive_manifest_is_reproducible_for_a_synthetic_external_fixture(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "synthetic.tgz"
    payload = b"synthetic old\tsynthetic new\n"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("pairs.tsv")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = extract_archive(
        archive,
        tmp_path / "output",
        expected_archive_sha256=digest,
        member_name="pairs.tsv",
        classifications={1: ("agreement", "development", True)},
        repository_root=tmp_path / "repository",
    )

    assert result.archive_sha256 == digest
    manifest = json.loads((tmp_path / "output" / "manifest.json").read_text())
    assert manifest["outputs"]["development"]["count"] == 1
    assert manifest["outputs"]["holdout"]["count"] == 0
    development = (tmp_path / "output" / "development.jsonl").read_bytes()
    assert manifest["outputs"]["development"]["count"] == development.count(b"\n")
    assert manifest["outputs"]["development"]["size_bytes"] == len(development)
    assert (
        manifest["outputs"]["development"]["sha256"]
        == hashlib.sha256(development).hexdigest()
    )


def test_archive_digest_and_read_use_one_open_file_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "synthetic.tgz"
    digest = _synthetic_archive(archive)
    original_open: Callable[..., int] = protocol._open_regular_descriptor

    def open_then_replace(path: Path, **kwargs: int | None) -> int:
        descriptor = original_open(path, **kwargs)
        if path == archive:
            replacement = path.with_name("archive-replacement")
            replacement.write_bytes(b"archive replaced after digest")
            os.replace(replacement, path)
        return descriptor

    monkeypatch.setattr(protocol, "_open_regular_descriptor", open_then_replace)
    result = extract_archive(
        archive,
        tmp_path / "output",
        expected_archive_sha256=digest,
        member_name="pairs.tsv",
        classifications={1: ("agreement", "development", True)},
        repository_root=tmp_path / "repository",
    )

    assert result.archive_sha256 == digest


def test_archive_parent_race_requires_descriptor_relative_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    sealed = repository / ".omo" / "sealed"
    sealed.mkdir(parents=True)
    real_parent = tmp_path / "external"
    real_parent.mkdir()
    safe_archive = real_parent / "synthetic.tgz"
    digest = _synthetic_archive(safe_archive)
    (sealed / safe_archive.name).write_bytes(safe_archive.read_bytes())
    archive = safe_archive
    moved_parent = tmp_path / "external-moved"
    original_open: Callable[..., int] = protocol.os.open
    pathname_race_triggered = False

    def race_open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal pathname_race_triggered
        if dir_fd is None and Path(path) == archive:
            pathname_race_triggered = True
            real_parent.rename(moved_parent)
            real_parent.symlink_to(sealed, target_is_directory=True)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(protocol.os, "open", race_open)
    result = extract_archive(
        archive,
        tmp_path / "output",
        expected_archive_sha256=digest,
        member_name="pairs.tsv",
        classifications={1: ("agreement", "development", True)},
        repository_root=repository,
    )

    assert result.archive_sha256 == digest
    assert not pathname_race_triggered


def test_archive_parent_replacement_is_rejected_before_pathname_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    sealed = repository / ".omo" / "sealed"
    sealed.mkdir(parents=True)
    real_parent = tmp_path / "external"
    real_parent.mkdir()
    alias = tmp_path / "external-alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    safe_archive = tmp_path / "safe.tgz"
    digest = _synthetic_archive(safe_archive)
    (sealed / "synthetic.tgz").write_bytes(safe_archive.read_bytes())
    archive = alias / "synthetic.tgz"

    original_require = protocol._require_external_path
    swapped = False

    def require_then_swap(path: Path, root: Path, label: str) -> None:
        nonlocal swapped
        original_require(path, root, label)
        if label == "archive" and not swapped:
            alias.unlink()
            alias.symlink_to(sealed, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(protocol, "_require_external_path", require_then_swap)
    with pytest.raises(WikEdProtocolError, match="path cannot contain symlinks"):
        extract_archive(
            archive,
            tmp_path / "output",
            expected_archive_sha256=digest,
            member_name="pairs.tsv",
            classifications={1: ("agreement", "development", True)},
            repository_root=repository,
        )


def test_output_parent_replacement_is_rejected_before_staging_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    sealed = repository / ".omo" / "sealed"
    sealed.mkdir(parents=True)
    real_parent = tmp_path / "external"
    real_parent.mkdir()
    alias = tmp_path / "external-alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    output = alias / "staging"

    original_require = protocol._require_external_path
    swapped = False

    def require_then_swap(path: Path, root: Path, label: str) -> None:
        nonlocal swapped
        original_require(path, root, label)
        if label == "output" and not swapped:
            alias.unlink()
            alias.symlink_to(sealed, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(protocol, "_require_external_path", require_then_swap)
    with pytest.raises(WikEdProtocolError, match="path cannot contain symlinks"):
        extract_records(
            ["synthetic old\tsynthetic new\n"],
            {1: ("agreement", "development", True)},
            output,
            repository_root=repository,
        )

    assert not (sealed / "staging").exists()


def test_classification_parent_replacement_is_rejected_before_pathname_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repository"
    sealed = repository / ".omo" / "sealed"
    sealed.mkdir(parents=True)
    real_parent = tmp_path / "external"
    real_parent.mkdir()
    alias = tmp_path / "external-alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    classification = alias / "classification.jsonl"
    safe_classification = (
        '{"line":1,"category":"agreement","split":"development","reviewed":true}\n'
    )
    (sealed / "classification.jsonl").write_text(safe_classification, encoding="utf-8")
    archive = tmp_path / "synthetic.tgz"
    digest = _synthetic_archive(archive)

    original_require = protocol._require_external_path
    swapped = False

    def require_then_swap(path: Path, root: Path, label: str) -> None:
        nonlocal swapped
        original_require(path, root, label)
        if label == "classification" and not swapped:
            alias.unlink()
            alias.symlink_to(sealed, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(protocol, "_require_external_path", require_then_swap)
    result = protocol.main(
        [
            "--archive",
            str(archive),
            "--archive-sha256",
            digest,
            "--member",
            "pairs.tsv",
            "--classification-map",
            str(classification),
            "--output",
            str(tmp_path / "output"),
            "--repository-root",
            str(repository),
        ]
    )
    capsys.readouterr()

    assert result == 2


def test_external_paths_reject_existing_symlink_parents_before_resolution(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    archive = real / "synthetic.tgz"
    archive.write_bytes(b"synthetic archive")
    external_alias = tmp_path / "external-alias"
    external_alias.symlink_to(real, target_is_directory=True)

    with pytest.raises(WikEdProtocolError, match="path cannot contain symlinks"):
        extract_archive(
            external_alias / "synthetic.tgz",
            tmp_path / "output",
            expected_archive_sha256="0" * 64,
            member_name="pairs.tsv",
            classifications={},
            repository_root=tmp_path / "repository",
        )


def test_archive_and_output_must_not_be_inside_repository_or_sealed_tree(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    archive = repository / "archive.tgz"
    output = tmp_path / "output"

    with pytest.raises(WikEdProtocolError, match="outside repository"):
        extract_archive(
            archive,
            output,
            expected_archive_sha256="0" * 64,
            member_name="pairs.tsv",
            classifications={},
            repository_root=repository,
        )
