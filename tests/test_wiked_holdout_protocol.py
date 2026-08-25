from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest
from scripts.wiked_holdout import (
    ExtractionParameters,
    WikEdProtocolError,
    extract_archive,
    extract_records,
    load_manifest,
)


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
