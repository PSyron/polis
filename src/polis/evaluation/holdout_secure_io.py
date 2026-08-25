from __future__ import annotations

import hashlib
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Final, NoReturn

from polis.evaluation.holdout_admission import ExternalAdmission
from polis.evaluation.holdout_attestations import exact_fields, metadata_bytes
from polis.evaluation.holdout_contract import canonical_sha256, parse_holdout_config
from polis.evaluation.holdout_manifest import (
    parse_dataset_manifest,
    parse_manifest_dataset_identity,
)
from polis.evaluation.holdout_models import (
    AdmissionEvidence,
    DatasetIdentity,
    HoldoutAdmissionError,
    HoldoutContractError,
    JsonObject,
)
from polis.evaluation.holdout_reservation import (
    CANONICAL_MARKER,
    HoldoutAlreadyConsumedError,
    _CanonicalWorkspaceIdentity,
    _ConsumptionCapability,
    consume_consumption_capability,
    invalidate_consumption_capabilities,
    reserve_consumption_secure,
)
from polis.evaluation.holdout_sources import source_sha256

_OUTPUT_NAMES: Final = frozenset(
    {
        "holdout.started",
        "report.json",
        "normalized-report.json",
        "result.manifest.json",
    }
)
_PERMANENT_FAILURE_NAME: Final = "holdout.publication.failed"
_MAX_METADATA_BYTES: Final = 1 << 20
_PUBLICATION_LOCK: Final = Lock()


def _secure_flags(*, directory: bool) -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise HoldoutAdmissionError("required O_NOFOLLOW support is unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    return flags | os.O_DIRECTORY if directory else flags


def _open_directory(parent: int, name: str) -> int:
    try:
        descriptor = os.open(name, _secure_flags(directory=True), dir_fd=parent)
    except OSError as error:
        raise HoldoutAdmissionError(
            "secure holdout directory is unavailable"
        ) from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise HoldoutAdmissionError("secure holdout directory is invalid")
    return descriptor


def _fsync_directory(parent: int) -> None:
    try:
        os.fsync(parent)
    except OSError as error:
        raise HoldoutAdmissionError(
            "exclusive holdout output parent directory sync failed"
        ) from error


@dataclass(frozen=True, slots=True)
class SecureFile:
    content: bytes
    mode: str


@dataclass(frozen=True, slots=True)
class _PublishedOutput:
    content: bytes
    digest: str


def _file_state(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        *_file_identity(metadata),
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_uid,
        metadata.st_gid,
    )


def _file_publication_state(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_uid,
        metadata.st_gid,
    )


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_nlink, metadata.st_mode)


def _read_file(
    parent: int,
    name: str,
    *,
    max_size: int,
    expected_size: int | None = None,
) -> SecureFile:
    if max_size < 0 or (
        expected_size is not None and (expected_size < 0 or expected_size > max_size)
    ):
        raise HoldoutAdmissionError("secure holdout file size contract is invalid")
    try:
        descriptor = os.open(name, _secure_flags(directory=False), dir_fd=parent)
    except OSError as error:
        raise HoldoutAdmissionError("secure holdout file is unavailable") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise HoldoutAdmissionError("secure holdout file is invalid")
        if before.st_nlink != 1:
            raise HoldoutAdmissionError("secure holdout file has multiple links")
        if before.st_size > max_size:
            raise HoldoutAdmissionError("secure holdout file exceeds size bound")
        before_state = _file_state(before)
        chunks: list[bytes] = []
        size = 0
        while size <= max_size:
            chunk = os.read(descriptor, min(65536, max_size - size + 1))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_size:
                raise HoldoutAdmissionError("secure holdout file exceeds size bound")
        after = os.fstat(descriptor)
        if _file_state(after) != before_state:
            raise HoldoutAdmissionError("secure holdout file changed during read")
        if expected_size is not None and size != expected_size:
            raise HoldoutAdmissionError(
                "secure holdout file size does not match contract"
            )
        return SecureFile(b"".join(chunks), f"{stat.S_IMODE(before.st_mode):04o}")
    except OSError as error:
        raise HoldoutAdmissionError("secure holdout file read failed") from error
    finally:
        os.close(descriptor)


def _verify_published_destination(
    parent: int,
    name: str,
    source_descriptor: int,
    expected_content: bytes,
    expected_links: int,
    expected_state: tuple[int, ...],
) -> None:
    try:
        destination = os.open(name, _secure_flags(directory=False), dir_fd=parent)
    except FileNotFoundError as error:
        raise HoldoutAdmissionError(
            "published holdout output destination is missing"
        ) from error
    except OSError as error:
        raise HoldoutAdmissionError(
            "published holdout output destination is invalid"
        ) from error
    try:
        source_metadata = os.fstat(source_descriptor)
        destination_metadata = os.fstat(destination)
        if (source_metadata.st_dev, source_metadata.st_ino) != (
            destination_metadata.st_dev,
            destination_metadata.st_ino,
        ):
            raise HoldoutAdmissionError("published holdout output destination changed")
        _verify_output(destination, expected_content, expected_links, expected_state)
    finally:
        os.close(destination)


def _ensure_no_publication_failure(parent: int) -> None:
    try:
        descriptor = os.open(
            _PERMANENT_FAILURE_NAME,
            _secure_flags(directory=False),
            dir_fd=parent,
        )
    except FileNotFoundError:
        return
    except OSError as error:
        raise HoldoutAdmissionError(
            "holdout publication failure state is invalid"
        ) from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise HoldoutAdmissionError("holdout publication failure state is invalid")
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            raise HoldoutAdmissionError(
                "holdout publication failure state could not be closed"
            ) from error
    raise HoldoutAdmissionError("holdout publication has permanently failed")


def _write_publication_failure(parent: int, name: str) -> None:
    content = f"publication failed for {name}\n".encode()
    try:
        descriptor = os.open(
            _PERMANENT_FAILURE_NAME,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | (_secure_flags(directory=False) & os.O_NOFOLLOW),
            0o600,
            dir_fd=parent,
        )
    except FileExistsError as error:
        raise HoldoutAdmissionError(
            "holdout publication has permanently failed"
        ) from error
    except OSError as error:
        raise HoldoutAdmissionError(
            "holdout publication failure marker is unavailable"
        ) from error
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(parent)


def _unlink_owned_temporary(
    parent: int,
    temporary_name: str,
    source_descriptor: int,
    expected_links_before: int,
    expected_links_after: int,
) -> None:
    try:
        temporary = os.open(
            temporary_name,
            _secure_flags(directory=False),
            dir_fd=parent,
        )
    except OSError as error:
        raise HoldoutAdmissionError(
            "temporary holdout output ownership is unavailable"
        ) from error
    try:
        source_metadata = os.fstat(source_descriptor)
        temporary_metadata = os.fstat(temporary)
        if (
            (source_metadata.st_dev, source_metadata.st_ino)
            != (temporary_metadata.st_dev, temporary_metadata.st_ino)
            or source_metadata.st_nlink != expected_links_before
            or temporary_metadata.st_nlink != expected_links_before
        ):
            raise HoldoutAdmissionError("temporary holdout output ownership changed")
        try:
            os.unlink(temporary_name, dir_fd=parent)
        except OSError as error:
            raise HoldoutAdmissionError(
                "temporary holdout output cleanup failed"
            ) from error
        source_after = os.fstat(source_descriptor)
        if source_after.st_nlink != expected_links_after:
            raise HoldoutAdmissionError("temporary holdout output ownership changed")
        _fsync_directory(parent)
    finally:
        os.close(temporary)


def _fail_closed_after_publication(
    parent: int,
    name: str,
    temporary_name: str,
    source_descriptor: int,
    original_error: HoldoutAdmissionError,
) -> NoReturn:
    cleanup_error: HoldoutAdmissionError | None = None
    try:
        if temporary_name:
            _unlink_owned_temporary(parent, temporary_name, source_descriptor, 2, 1)
    except HoldoutAdmissionError as error:
        cleanup_error = error
    try:
        _write_publication_failure(parent, name)
    except HoldoutAdmissionError as marker_error:
        raise HoldoutAdmissionError(str(original_error)) from marker_error
    if cleanup_error is not None:
        raise HoldoutAdmissionError(str(original_error)) from cleanup_error
    raise original_error


def _fail_closed_before_publication(
    parent: int,
    temporary_name: str,
    source_descriptor: int,
    original_error: HoldoutAdmissionError,
) -> NoReturn:
    try:
        _unlink_owned_temporary(parent, temporary_name, source_descriptor, 1, 0)
    except HoldoutAdmissionError as failure_error:
        raise HoldoutAdmissionError(str(original_error)) from failure_error
    raise original_error


def _require_output_name(name: str) -> None:
    if name not in _OUTPUT_NAMES:
        raise HoldoutAdmissionError("unregistered holdout output")


def _verify_output(
    descriptor: int,
    expected_content: bytes,
    expected_links: int,
    expected_state: tuple[int, ...],
) -> None:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != expected_links:
        raise HoldoutAdmissionError("exclusive holdout output changed")
    if _file_publication_state(before) != expected_state:
        raise HoldoutAdmissionError("exclusive holdout output changed")
    chunks: list[bytes] = []
    offset = 0
    while offset < len(expected_content):
        chunk = os.pread(descriptor, min(65536, len(expected_content) - offset), offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    if b"".join(chunks) != expected_content:
        raise HoldoutAdmissionError("exclusive holdout output changed")
    after = os.fstat(descriptor)
    if _file_publication_state(after) != expected_state:
        raise HoldoutAdmissionError("exclusive holdout output changed")


class SecureHoldoutWorkspace:
    __slots__ = (
        "_config",
        "_experiment",
        "_reservation_workspace",
        "_root",
        "_sealed",
        "_approved_config",
        "_approved_dataset_identity",
        "_published_outputs",
        "_closed",
        "_lifecycle_lock",
    )

    def __init__(
        self, root: int, experiment: int, sealed: int, config: SecureFile
    ) -> None:
        self._root = root
        self._experiment = experiment
        self._sealed = sealed
        self._config = config
        self._reservation_workspace = _CanonicalWorkspaceIdentity()
        self._approved_config = None
        self._approved_dataset_identity: DatasetIdentity | None = None
        self._published_outputs: dict[str, _PublishedOutput] = {}
        self._closed = False
        self._lifecycle_lock = Lock()

    @classmethod
    def open(cls, repository_root: Path) -> SecureHoldoutWorkspace:
        flags = _secure_flags(directory=True)
        try:
            root = os.open(repository_root, flags)
        except OSError as error:
            raise HoldoutAdmissionError("repository root is unavailable") from error
        opened = [root]
        try:
            root_identity = os.fstat(root)
            cwd_identity = os.stat(".", follow_symlinks=False)
            if (root_identity.st_dev, root_identity.st_ino) != (
                cwd_identity.st_dev,
                cwd_identity.st_ino,
            ):
                raise HoldoutAdmissionError(
                    "repository descriptor does not match current directory"
                )
            experiments = _open_directory(root, "experiments")
            opened.append(experiments)
            experiment = _open_directory(experiments, "a-b-one-shot")
            opened.append(experiment)
            omo = _open_directory(root, ".omo")
            opened.append(omo)
            sealed_root = _open_directory(omo, "sealed")
            opened.append(sealed_root)
            sealed = _open_directory(sealed_root, "a-b-one-shot-v1")
            opened.append(sealed)
            config = _read_file(experiment, "config.json", max_size=_MAX_METADATA_BYTES)
        except (HoldoutAdmissionError, OSError):
            for descriptor in reversed(opened):
                os.close(descriptor)
            raise
        os.close(experiments)
        os.close(omo)
        os.close(sealed_root)
        return cls(root, experiment, sealed, config)

    def read_config(self) -> bytes:
        with self._lifecycle_lock:
            self._require_open()
            return self._config.content

    def read_manifest(self) -> bytes:
        with self._lifecycle_lock:
            self._require_open()
            return _read_file(
                self._experiment,
                "dataset.manifest.json",
                max_size=_MAX_METADATA_BYTES,
            ).content

    def bind_approved_dataset_identity(self) -> None:
        with self._lifecycle_lock:
            self._require_open()
            try:
                config = parse_holdout_config(
                    metadata_bytes(self._config.content, "config.json")
                )
                manifest = metadata_bytes(
                    _read_file(
                        self._experiment,
                        "dataset.manifest.json",
                        max_size=_MAX_METADATA_BYTES,
                    ).content,
                    "dataset.manifest.json",
                )
                parse_dataset_manifest(manifest, config)
                identity = parse_manifest_dataset_identity(manifest)
            except (HoldoutContractError, HoldoutAdmissionError) as error:
                raise HoldoutAdmissionError(
                    "approved dataset manifest is invalid"
                ) from error
            if (
                self._approved_dataset_identity is not None
                and self._approved_dataset_identity != identity
            ):
                raise HoldoutAdmissionError("approved dataset identity changed")
            if self._approved_config is not None and self._approved_config != config:
                raise HoldoutAdmissionError("approved holdout config changed")
            self._approved_config = config
            self._approved_dataset_identity = identity

    def read_evidence(self, name: str) -> bytes:
        with self._lifecycle_lock:
            self._require_open()
            if name not in {
                "merge-verification.json",
                "run-authorization.json",
                "run-authorization.sig",
            }:
                raise HoldoutAdmissionError("unregistered evidence file")
            return _read_file(self._sealed, name, max_size=_MAX_METADATA_BYTES).content

    def read_dataset(
        self, capability: _ConsumptionCapability | None = None
    ) -> SecureFile:
        with self._lifecycle_lock:
            self._require_open()
            identity = self._approved_dataset_identity
            if identity is None:
                raise HoldoutAdmissionError("approved dataset identity is unavailable")
            try:
                consume_consumption_capability(
                    capability,
                    expected_marker=CANONICAL_MARKER,
                    expected_workspace_identity=self._reservation_workspace,
                    expected_dataset_identity=identity.sha256,
                )
            except HoldoutAlreadyConsumedError as error:
                raise HoldoutAdmissionError(
                    "sealed dataset read requires an active reservation authorization"
                ) from error
            secure_file = _read_file(
                self._sealed,
                "cases.json",
                max_size=identity.size_bytes,
                expected_size=identity.size_bytes,
            )
            if secure_file.mode != identity.mode:
                raise HoldoutAdmissionError(
                    "sealed dataset mode does not match approved manifest"
                )
            if hashlib.sha256(secure_file.content).hexdigest() != identity.sha256:
                raise HoldoutAdmissionError(
                    "sealed dataset digest does not match approved manifest"
                )
            return secure_file

    def _admission_evidence_locked(self) -> AdmissionEvidence:
        config = self._approved_config
        approved_identity = self._approved_dataset_identity
        if config is None or approved_identity is None:
            raise HoldoutAdmissionError("approved admission evidence is unavailable")
        try:
            merge = metadata_bytes(
                _read_file(
                    self._sealed,
                    "merge-verification.json",
                    max_size=_MAX_METADATA_BYTES,
                ).content,
                "merge-verification.json",
            )
            exact_fields(
                merge,
                {
                    "schema_id",
                    "schema_version",
                    "evaluated_source_sha",
                    "evaluated_source_tree_sha256",
                    "github_verification",
                    "github_verification_sha256",
                },
                "merge verification",
            )
            if (
                merge.get("schema_id") != "polis.a-b-one-shot.merge-verification"
                or merge.get("schema_version") != 1
            ):
                raise HoldoutAdmissionError("merge verification version is invalid")
            merge_commit = merge.get("evaluated_source_sha")
            verification = merge.get("github_verification")
            if not isinstance(merge_commit, str) or not merge_commit:
                raise HoldoutAdmissionError("merge verification identity is invalid")
            if not isinstance(verification, dict):
                raise HoldoutAdmissionError("merge verification payload is invalid")
            exact_fields(
                verification,
                {"verified", "reason", "signature", "payload", "verified_at"},
                "GitHub verification payload",
            )
            verified = verification.get("verified")
            reason = verification.get("reason")
            payload_sha256 = merge.get("github_verification_sha256")
            if type(verified) is not bool or not isinstance(reason, str):
                raise HoldoutAdmissionError("merge verification result is invalid")
            if not isinstance(payload_sha256, str) or not payload_sha256:
                raise HoldoutAdmissionError("merge verification digest is invalid")
            if canonical_sha256(verification) != payload_sha256:
                raise HoldoutAdmissionError("merge verification payload changed")
            evidence = AdmissionEvidence(
                config_sha256=canonical_sha256(
                    metadata_bytes(self._config.content, "config.json")
                ),
                source_sha256=source_sha256(config),
                dataset_sha256=approved_identity.sha256,
                merge_commit=merge_commit,
                verification_verified=verified,
                verification_reason=reason,
                verification_payload_sha256=payload_sha256,
            )
        except (HoldoutAdmissionError, HoldoutContractError) as error:
            raise HoldoutAdmissionError(
                "self-bound admission evidence is invalid"
            ) from error
        if (
            evidence.verification_verified is not True
            or evidence.verification_reason != "valid"
        ):
            raise HoldoutAdmissionError("self-bound admission verification is invalid")
        return evidence

    def reserve_dataset(
        self, admission: ExternalAdmission, *, reserved_at: str
    ) -> _ConsumptionCapability:
        with self._lifecycle_lock:
            self._require_open()
            approved_identity = self._approved_dataset_identity
            if approved_identity is None:
                raise HoldoutAdmissionError("approved dataset identity is unavailable")
            expected_evidence = self._admission_evidence_locked()
            if admission.evidence != expected_evidence:
                raise HoldoutAdmissionError("admission evidence identity mismatch")
            identity: JsonObject = {
                "experiment_id": self._approved_config.experiment_id
                if self._approved_config is not None
                else "",
                "config_sha256": expected_evidence.config_sha256,
                "source_sha256": expected_evidence.source_sha256,
                "dataset_sha256": expected_evidence.dataset_sha256,
                "merge_commit": expected_evidence.merge_commit,
                "verification_verified": expected_evidence.verification_verified,
                "verification_reason": expected_evidence.verification_reason,
                "verification_payload_sha256": (
                    expected_evidence.verification_payload_sha256
                ),
            }
            return reserve_consumption_secure(
                CANONICAL_MARKER,
                identity,
                reserved_at=reserved_at,
                write_marker=self._create_output_locked,
                workspace_identity=self._reservation_workspace,
                dataset_identity=approved_identity.sha256,
            )

    def read_output(self, name: str) -> bytes:
        with self._lifecycle_lock:
            self._require_open()
            _require_output_name(name)
            with _PUBLICATION_LOCK:
                _ensure_no_publication_failure(self._experiment)
                expected = self._published_outputs.get(name)
                if expected is None:
                    raise HoldoutAdmissionError("unregistered holdout output")
                actual = _read_file(
                    self._experiment, name, max_size=_MAX_METADATA_BYTES
                ).content
                if (
                    actual != expected.content
                    or hashlib.sha256(actual).hexdigest() != expected.digest
                ):
                    raise HoldoutAdmissionError("trusted holdout output changed")
                return actual

    def output_exists(self, name: str) -> bool:
        with self._lifecycle_lock:
            self._require_open()
            _require_output_name(name)
            with _PUBLICATION_LOCK:
                _ensure_no_publication_failure(self._experiment)
                try:
                    descriptor = os.open(
                        name, _secure_flags(directory=False), dir_fd=self._experiment
                    )
                except FileNotFoundError:
                    return False
                except OSError as error:
                    raise HoldoutAdmissionError(
                        "holdout output state is invalid"
                    ) from error
                try:
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                        raise HoldoutAdmissionError("holdout output state is invalid")
                finally:
                    os.close(descriptor)
                expected = self._published_outputs.get(name)
                if expected is not None:
                    actual = _read_file(
                        self._experiment, name, max_size=_MAX_METADATA_BYTES
                    ).content
                    if (
                        actual != expected.content
                        or hashlib.sha256(actual).hexdigest() != expected.digest
                    ):
                        raise HoldoutAdmissionError("trusted holdout output changed")
                return True

    def create_output(self, name: str, content: bytes) -> None:
        with self._lifecycle_lock:
            self._require_open()
            self._create_output_locked(name, content)

    def _create_output_locked(self, name: str, content: bytes) -> None:
        with _PUBLICATION_LOCK:
            self._create_output_transaction_locked(name, content)

    def _create_output_transaction_locked(self, name: str, content: bytes) -> None:
        _require_output_name(name)
        _ensure_no_publication_failure(self._experiment)
        temporary_name = f".{name}.{secrets.token_hex(16)}"
        descriptor: int | None = None
        published = False
        try:
            descriptor = os.open(
                temporary_name,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | (_secure_flags(directory=False) & os.O_NOFOLLOW),
                0o600,
                dir_fd=self._experiment,
            )
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
            expected_state = _file_publication_state(os.fstat(descriptor))
            os.fsync(descriptor)
            _verify_output(descriptor, content, 1, expected_state)
            os.link(
                temporary_name,
                name,
                src_dir_fd=self._experiment,
                dst_dir_fd=self._experiment,
                follow_symlinks=False,
            )
            published = True
            _fsync_directory(self._experiment)
            linked_metadata = os.fstat(descriptor)
            linked_state = (
                *expected_state[:5],
                linked_metadata.st_ctime_ns,
                *expected_state[6:],
            )
            _verify_output(descriptor, content, 2, linked_state)
            _verify_published_destination(
                self._experiment,
                name,
                descriptor,
                content,
                2,
                linked_state,
            )
            assert descriptor is not None
            _unlink_owned_temporary(self._experiment, temporary_name, descriptor, 2, 1)
            temporary_name = ""
            final_state = _file_publication_state(os.fstat(descriptor))
            _verify_published_destination(
                self._experiment,
                name,
                descriptor,
                content,
                1,
                final_state,
            )
            self._published_outputs[name] = _PublishedOutput(
                content, hashlib.sha256(content).hexdigest()
            )
        except FileExistsError as error:
            if descriptor is not None and not published:
                try:
                    _unlink_owned_temporary(
                        self._experiment, temporary_name, descriptor, 1, 0
                    )
                except HoldoutAdmissionError as cleanup_error:
                    raise cleanup_error from error
            raise
        except HoldoutAdmissionError as error:
            if descriptor is not None and published:
                _fail_closed_after_publication(
                    self._experiment,
                    name,
                    temporary_name,
                    descriptor,
                    error,
                )
            if descriptor is not None:
                _fail_closed_before_publication(
                    self._experiment, temporary_name, descriptor, error
                )
            raise
        except OSError as error:
            mapped = HoldoutAdmissionError("exclusive holdout output failed")
            if descriptor is not None and published:
                _fail_closed_after_publication(
                    self._experiment,
                    name,
                    temporary_name,
                    descriptor,
                    mapped,
                )
            if descriptor is not None:
                _fail_closed_before_publication(
                    self._experiment, temporary_name, descriptor, mapped
                )
            raise mapped from error
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as error:
                    if published:
                        try:
                            _write_publication_failure(self._experiment, name)
                        except HoldoutAdmissionError as marker_error:
                            raise HoldoutAdmissionError(
                                "exclusive holdout output failed"
                            ) from marker_error
                    raise HoldoutAdmissionError(
                        "exclusive holdout output close failed"
                    ) from error

    def close(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            invalidate_consumption_capabilities(self._reservation_workspace)
            for descriptor in (self._sealed, self._experiment, self._root):
                os.close(descriptor)

    def _require_open(self) -> None:
        if self._closed:
            raise HoldoutAdmissionError("secure holdout workspace is closed")
