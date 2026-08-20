from __future__ import annotations

import _socket
import argparse
import builtins
import hashlib
import importlib
import importlib.metadata
import json
import multiprocessing
import os
import platform
import socket
import stat
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast
from zipfile import BadZipFile, ZipFile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.morphology_provider_json import (
    ContractError,
    JsonValue,
    canonical_bytes,
    exact_fields,
    integer,
    mapping,
    optional_string,
    read_json,
    string,
)

EXPECTED_PUBLIC_DATASET_ID = "polis-polish-spelling-provider-v1"
EXPECTED_PUBLIC_DATASET_SHA256 = (
    "a090e7b8ff3b18bc11dfc39fd7ca564f6768fe9f9555068e923268fe4602a8a3"
)
PUBLIC_DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/v1/spelling_provider_qualification.json"
)
PUBLIC_MANIFEST_PATH = PUBLIC_DATASET_PATH.with_suffix(".manifest.json")
EXPECTED_PROVIDER_METADATA = {
    "spylls": {
        "package_version": "0.1.7",
        "package_license": (
            "MPL-2.0 upstream; wheel metadata UNKNOWN/classifier MIT; "
            "PyPI license field empty"
        ),
        "package_license_status": "unresolved-contradictory",
        "package_sha256": (
            "0c7fa4b66615f390bd12fd37939b85934c012309fd3cce8584844c54270b7776"
        ),
        "data_id": (
            "LibreOffice/dictionaries@f2ff99058268502bdcf4cad25c1ca2935ad8aa7d:pl_PL"
        ),
        "data_license": "GPL OR LGPL OR MPL OR Apache-2.0 OR CC-ShareAlike",
        "data_license_status": "unresolved-multi-license",
        "data_source": (
            "https://github.com/LibreOffice/dictionaries/tree/"
            "f2ff99058268502bdcf4cad25c1ca2935ad8aa7d/pl_PL"
        ),
        "data_source_sha256": (
            "f17a7b7ddcdeef3e40d01aaaee496dc15b1888041d702eddddc7e2fbb2cc33b2"
        ),
        "data_sha256": {
            "pl_PL.aff": (
                "82973651651aa930335c865b339b98db376ca3dbf3a661b70b9eeb71fdf41dca"
            ),
            "pl_PL.dic": (
                "c0848440599eb88e5aca500418d5f389e562ec2c157b63dbe39d354658ffba49"
            ),
            "README_en.txt": (
                "fb5f9b4a0643821cf88775c0932810c1cd05f236136c913e3eaf1e24806f3f44"
            ),
        },
    },
    "symspellpy": {
        "package_version": "6.10.0",
        "package_license": "MIT",
        "package_license_status": "clear",
        "package_sha256": (
            "e31707f6d6e06b89973588c02c0c7941c9ca1e3144859a8e2e46d8b815dda75e"
        ),
        "data_id": (
            "K7TRY/WordFreqLists@204bc67cca6daee769137ec95169afb5ccb2b565:"
            "Polish Word Frequency List.txt -> deterministic SymSpell "
            "2-column derivation"
        ),
        "data_license": "GPL-3.0",
        "data_license_status": "incompatible-for-Polis-distribution",
        "data_source": (
            "https://raw.githubusercontent.com/K7TRY/WordFreqLists/"
            "204bc67cca6daee769137ec95169afb5ccb2b565/Polish%20Word%20Frequency%20List.txt"
        ),
        "data_source_sha256": (
            "956b2071998cbe72edb8eac070aa792cf00b171faddf7403116d8d9b8f47e783"
        ),
        "data_sha256": {
            "symspell.txt": (
                "516543c11caca422912eef552bbd8cceeb1110bfdecc6a1cf3918f3f1a28acd8"
            ),
        },
    },
}


class CandidateProvider(Protocol):
    def known(self, token: str) -> bool: ...

    def suggest(self, token: str, limit: int) -> tuple[str, ...]: ...


class _SpyllsDictionary(Protocol):
    def lookup(self, token: str) -> bool: ...

    def suggest(self, token: str) -> Iterable[str]: ...


class _SymspellResult(Protocol):
    term: str


class _SymspellDictionary(Protocol):
    def lookup(
        self, token: str, verbosity: object, *, max_edit_distance: int
    ) -> Iterable[_SymspellResult]: ...


class _SymspellVerbosity(Protocol):
    TOP: object


@dataclass(frozen=True, slots=True)
class QualificationCase:
    id: str
    category: str
    text: str
    start: int
    end: int
    expected_action: str
    expected_candidates: tuple[str, ...]
    expected_top1: str | None
    guard: str

    @property
    def token(self) -> str:
        return self.text[self.start : self.end]


@dataclass(frozen=True, slots=True)
class QualificationDataset:
    dataset_id: str
    dataset_version: int
    canonical_sha256: str
    cases: tuple[QualificationCase, ...]


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    case_id: str
    status: str
    known: bool | None
    candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Artifact:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    name: str
    package_version: str
    package_license: str
    package_license_status: str
    data_id: str
    data_license: str
    data_license_status: str
    data_source: str
    data_source_sha256: str
    package_artifact: Artifact
    dependency_artifacts: tuple[Artifact, ...]
    data_artifacts: tuple[Artifact, ...]


def _canonical_sha256(value: JsonValue) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path) -> Artifact:
    if not path.is_file():
        raise ContractError(f"artifact does not exist: {path}")
    return Artifact(
        path=path, sha256=_file_sha256(path), size_bytes=path.stat().st_size
    )


_SOCKET_BOUNDARY_LOCK = threading.RLock()


@contextmanager
def _offline_only() -> Iterator[Callable[[], None]]:
    with _SOCKET_BOUNDARY_LOCK:
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create_connection = socket.create_connection
        original_getaddrinfo = socket.getaddrinfo
        original_gethostbyname = socket.gethostbyname
        original_gethostbyname_ex = socket.gethostbyname_ex
        original_gethostbyaddr = socket.gethostbyaddr
        original_getnameinfo = socket.getnameinfo
        original_getfqdn = socket.getfqdn
        original_send = socket.socket.send
        original_sendall = socket.socket.sendall
        original_sendto = socket.socket.sendto
        original_sendmsg = socket.socket.sendmsg
        original_sendfile = socket.socket.sendfile
        original_reload = importlib.reload
        original_os_write = os.write
        original_os_fdopen = os.fdopen
        original_os_writev = getattr(os, "writev", None)
        original_os_sendfile = getattr(os, "sendfile", None)
        original_os_splice = getattr(os, "splice", None)
        original_native_socket = _socket.socket
        original_process_entries = (
            (os, "system", os.system),
            (os, "popen", os.popen),
            (subprocess, "Popen", subprocess.Popen),
            (subprocess, "run", subprocess.run),
            (subprocess, "call", subprocess.call),
            (subprocess, "check_call", subprocess.check_call),
            (subprocess, "check_output", subprocess.check_output),
            (multiprocessing, "Process", multiprocessing.Process),
            (multiprocessing, "get_context", multiprocessing.get_context),
        ) + tuple(
            (os, name, getattr(os, name))
            for name in (
                "fork",
                "posix_spawn",
                "posix_spawnp",
                "spawnv",
                "spawnve",
                "spawnvp",
                "spawnvpe",
            )
            if hasattr(os, name)
        )

        def blocked(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise OSError("network access is disabled during qualification")

        def guarded_reload(module: ModuleType) -> ModuleType:
            if module is socket:
                raise OSError("reloading socket is disabled during qualification")
            return original_reload(module)

        def guarded_os_write(fd: int, data: bytes) -> int:
            try:
                is_socket = stat.S_ISSOCK(os.fstat(fd).st_mode)
            except OSError:
                is_socket = False
            if is_socket:
                raise OSError("writing to sockets is disabled during qualification")
            return original_os_write(fd, data)

        def guarded_os_fdopen(fd: int, *args: object, **kwargs: object) -> object:
            try:
                is_socket = stat.S_ISSOCK(os.fstat(fd).st_mode)
            except OSError:
                is_socket = False
            if is_socket:
                raise OSError("writing to sockets is disabled during qualification")
            return cast(Callable[..., object], original_os_fdopen)(fd, *args, **kwargs)

        def guarded_os_writev(fd: int, buffers: Iterable[bytes]) -> int:
            try:
                is_socket = stat.S_ISSOCK(os.fstat(fd).st_mode)
            except OSError:
                is_socket = False
            if is_socket:
                raise OSError("writing to sockets is disabled during qualification")
            if not callable(original_os_writev):
                raise OSError("os.writev is unavailable during qualification")
            return cast(Callable[[int, Iterable[bytes]], int], original_os_writev)(
                fd, buffers
            )

        def guarded_os_sendfile(
            out_fd: int, in_fd: int, offset: int | None, count: int
        ) -> int:
            try:
                is_socket = stat.S_ISSOCK(os.fstat(out_fd).st_mode)
            except OSError:
                is_socket = False
            if is_socket:
                raise OSError("writing to sockets is disabled during qualification")
            if not callable(original_os_sendfile):
                raise OSError("os.sendfile is unavailable during qualification")
            return cast(
                Callable[[int, int, int | None, int], int], original_os_sendfile
            )(out_fd, in_fd, offset, count)

        def guarded_os_splice(
            source_fd: int,
            destination_fd: int,
            count: int,
            offset_source: int | None = None,
            offset_destination: int | None = None,
            flags: int = 0,
        ) -> int:
            del offset_source, offset_destination, flags
            try:
                source_is_socket = stat.S_ISSOCK(os.fstat(source_fd).st_mode)
                destination_is_socket = stat.S_ISSOCK(os.fstat(destination_fd).st_mode)
            except OSError:
                source_is_socket = destination_is_socket = False
            if source_is_socket or destination_is_socket:
                raise OSError("writing to sockets is disabled during qualification")
            if not callable(original_os_splice):
                raise OSError("os.splice is unavailable during qualification")
            return cast(Callable[..., int], original_os_splice)(
                source_fd, destination_fd, count, None, None, 0
            )

        original_import_module = importlib.import_module
        original_import = builtins.__import__

        def guarded_import_module(name: str, package: str | None = None) -> ModuleType:
            if name == "multiprocessing" or name.startswith("multiprocessing."):
                raise OSError("process creation is disabled during qualification")
            return original_import_module(name, package)

        def guarded_import(
            name: str,
            globals: Mapping[str, object] | None = None,
            locals: Mapping[str, object] | None = None,
            fromlist: Sequence[str] | None = None,
            level: int = 0,
        ) -> ModuleType:
            if name == "multiprocessing" or name.startswith("multiprocessing."):
                raise OSError("process creation is disabled during qualification")
            return original_import(name, globals, locals, fromlist, level)

        blocked_native_socket = type(
            "_BlockedNativeSocket",
            (original_native_socket,),
            {
                "connect": blocked,
                "connect_ex": blocked,
                "send": blocked,
                "sendall": blocked,
                "sendto": blocked,
                "sendmsg": blocked,
            },
        )

        socket_spec = socket.__spec__
        original_socket_loader = socket_spec.loader if socket_spec is not None else None

        class _ReloadBlockedLoader:
            def exec_module(self, module: ModuleType) -> None:
                del module
                raise OSError("reloading socket is disabled during qualification")

        patches: tuple[tuple[object, str, object], ...] = (
            (socket.socket, "connect", blocked),
            (socket.socket, "connect_ex", blocked),
            (socket, "create_connection", blocked),
            (socket, "getaddrinfo", blocked),
            (socket, "gethostbyname", blocked),
            (socket, "gethostbyname_ex", blocked),
            (socket, "gethostbyaddr", blocked),
            (socket, "getnameinfo", blocked),
            (socket, "getfqdn", blocked),
            (socket.socket, "send", blocked),
            (socket.socket, "sendall", blocked),
            (socket.socket, "sendto", blocked),
            (socket.socket, "sendmsg", blocked),
            (socket.socket, "sendfile", blocked),
            (importlib, "reload", guarded_reload),
            (os, "write", guarded_os_write),
            (os, "fdopen", guarded_os_fdopen),
        )
        if callable(original_os_writev):
            patches += ((os, "writev", guarded_os_writev),)
        if callable(original_os_sendfile):
            patches += ((os, "sendfile", guarded_os_sendfile),)
        if callable(original_os_splice):
            patches += ((os, "splice", guarded_os_splice),)
        patches += ((_socket, "socket", blocked_native_socket),)
        patches += ((_socket, "getaddrinfo", blocked),)
        patches += tuple(
            (owner, name, blocked) for owner, name, _ in original_process_entries
        )
        patches += (
            (importlib, "import_module", guarded_import_module),
            (builtins, "__import__", guarded_import),
        )
        blocked_socket_loader = _ReloadBlockedLoader()
        for owner, name, replacement in patches:
            setattr(owner, name, replacement)
        if socket_spec is not None:
            loader_name = "loader"
            setattr(socket_spec, loader_name, blocked_socket_loader)

        def assert_boundary() -> None:
            for owner, name, replacement in patches:
                if getattr(owner, name) is not replacement:
                    raise ContractError(
                        f"offline boundary was replaced: {owner!r}.{name}"
                    )
            if (
                socket_spec is not None
                and cast(object, socket_spec.loader) is not blocked_socket_loader
            ):
                raise ContractError("offline socket loader boundary was replaced")

        try:
            yield assert_boundary
        finally:
            originals: tuple[tuple[object, str, object], ...] = (
                (socket.socket, "connect", original_connect),
                (socket.socket, "connect_ex", original_connect_ex),
                (socket, "create_connection", original_create_connection),
                (socket, "getaddrinfo", original_getaddrinfo),
                (socket, "gethostbyname", original_gethostbyname),
                (socket, "gethostbyname_ex", original_gethostbyname_ex),
                (socket, "gethostbyaddr", original_gethostbyaddr),
                (socket, "getnameinfo", original_getnameinfo),
                (socket, "getfqdn", original_getfqdn),
                (socket.socket, "send", original_send),
                (socket.socket, "sendall", original_sendall),
                (socket.socket, "sendto", original_sendto),
                (socket.socket, "sendmsg", original_sendmsg),
                (socket.socket, "sendfile", original_sendfile),
                (importlib, "reload", original_reload),
                (os, "write", original_os_write),
                (os, "fdopen", original_os_fdopen),
            )
            for owner, name, replacement in originals:
                setattr(owner, name, replacement)
            if callable(original_os_writev):
                setattr(os, "writev", original_os_writev)  # noqa: B010
            if callable(original_os_sendfile):
                setattr(os, "sendfile", original_os_sendfile)  # noqa: B010
            if callable(original_os_splice):
                setattr(os, "splice", original_os_splice)  # noqa: B010
            setattr(_socket, "socket", original_native_socket)  # noqa: B010
            for owner, name, original in original_process_entries:
                setattr(owner, name, original)
            setattr(importlib, "import_module", original_import_module)  # noqa: B010
            setattr(builtins, "__import__", original_import)  # noqa: B010
            if socket_spec is not None:
                setattr(socket_spec, loader_name, original_socket_loader)


def _validate_public_fixture_paths(dataset_path: Path, manifest_path: Path) -> None:
    if dataset_path.resolve() != PUBLIC_DATASET_PATH:
        raise ContractError(
            "qualification dataset must be the committed public fixture"
        )
    if manifest_path.resolve() != PUBLIC_MANIFEST_PATH:
        raise ContractError("qualification manifest must match the public fixture")


def _validate_output_path(options: argparse.Namespace) -> None:
    input_paths = [
        options.dataset,
        options.manifest,
        options.package_artifact,
        *options.dependency_artifact,
        *options.data_file,
    ]
    if options.dictionary_prefix is not None:
        input_paths.extend(
            (
                options.dictionary_prefix.with_suffix(".aff"),
                options.dictionary_prefix.with_suffix(".dic"),
            )
        )
    if options.frequency_file is not None:
        input_paths.append(options.frequency_file)
    if options.output.resolve() in {path.resolve() for path in input_paths}:
        raise ContractError("output path must not overwrite a qualification input")


def _verify_installed_package(
    provider_name: str, package_artifact: Artifact
) -> tuple[Path, frozenset[str]]:
    if package_artifact.path.suffix != ".whl":
        raise ContractError("package artifact must be a wheel")
    distribution = importlib.metadata.distribution(provider_name)
    install_root = Path(str(distribution.locate_file("")))
    verified_members: set[str] = set()
    try:
        with ZipFile(package_artifact.path) as wheel:
            for member in wheel.namelist():
                if member.endswith(".dist-info/RECORD"):
                    continue
                verified_members.add(member)
                installed = install_root / member
                if not installed.is_file():
                    raise ContractError(f"installed provider file is missing: {member}")
                if (
                    _file_sha256(installed)
                    != hashlib.sha256(wheel.read(member)).hexdigest()
                ):
                    raise ContractError(f"installed provider file drift: {member}")
    except BadZipFile as error:
        raise ContractError(
            f"invalid wheel artifact: {package_artifact.path}"
        ) from error
    return install_root, frozenset(verified_members)


def _verify_module_origin(
    module: ModuleType,
    provider_name: str,
    install_root: Path,
    verified_members: frozenset[str],
    stdlib_root: Path,
) -> None:
    del provider_name
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str):
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if origin in {"built-in", "frozen"}:
            return
        raise ContractError("imported module has no verifiable file")
    module_origin = Path(module_file).resolve()
    if module_origin.is_relative_to(stdlib_root):
        return
    package_root = install_root.resolve()
    if not module_origin.is_relative_to(package_root):
        raise ContractError(
            "imported module is outside the verified runtime closure: "
            f"{module.__name__}"
        )
    member = module_origin.relative_to(package_root).as_posix()
    if member not in verified_members:
        raise ContractError(
            f"imported module is not in the verified wheel: {module.__name__}"
        )


@contextmanager
def _provider_import_boundary(
    provider_name: str,
    install_root: Path,
    verified_members: frozenset[str],
) -> Iterator[None]:
    original_import = builtins.__import__
    original_import_module = importlib.import_module
    stdlib_root = Path(sysconfig.get_paths()["stdlib"]).resolve()

    def verify_module(module: object) -> None:
        if isinstance(module, ModuleType):
            _verify_module_origin(
                module, provider_name, install_root, verified_members, stdlib_root
            )

    def guarded_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] | None = None,
        level: int = 0,
    ) -> ModuleType:
        result = original_import(name, globals, locals, fromlist, level)
        verify_module(result)
        if isinstance(fromlist, (tuple, list)):
            result_name = getattr(result, "__name__", name)
            for item in fromlist:
                if isinstance(item, str) and item != "*":
                    verify_module(sys.modules.get(f"{result_name}.{item}"))
        return result

    def guarded_import_module(name: str, package: str | None = None) -> ModuleType:
        result = original_import_module(name, package)
        verify_module(result)
        return result

    builtins.__import__ = guarded_import
    importlib.import_module = guarded_import_module
    try:
        yield
    finally:
        builtins.__import__ = original_import
        importlib.import_module = original_import_module


def _verify_loaded_package(provider_name: str, package_artifact: Artifact) -> None:
    install_root, verified_members = _verify_installed_package(
        provider_name, package_artifact
    )
    module = importlib.import_module(provider_name)
    del module
    for loaded_name, loaded_module in tuple(sys.modules.items()):
        if loaded_name != provider_name and not loaded_name.startswith(
            f"{provider_name}."
        ):
            continue
        module_file = getattr(loaded_module, "__file__", None)
        if not isinstance(module_file, str):
            raise ContractError(f"loaded provider module has no file: {loaded_name}")
        module_origin = Path(module_file).resolve()
        if not module_origin.is_relative_to(install_root.resolve()):
            raise ContractError(
                "loaded provider module is outside its verified distribution: "
                f"{loaded_name}"
            )
        member = module_origin.relative_to(install_root.resolve()).as_posix()
        if member not in verified_members:
            raise ContractError(
                f"loaded provider module is not in the verified wheel: {loaded_name}"
            )


def _verify_loaded_module_closure(
    provider_name: str,
    package_artifact: Artifact,
    baseline_module_names: frozenset[str],
) -> None:
    install_root, verified_members = _verify_installed_package(
        provider_name, package_artifact
    )
    stdlib_root = Path(sysconfig.get_paths()["stdlib"]).resolve()
    for loaded_name in set(sys.modules) - baseline_module_names:
        loaded_module = sys.modules[loaded_name]
        if isinstance(loaded_module, ModuleType):
            try:
                _verify_module_origin(
                    loaded_module,
                    provider_name,
                    install_root,
                    verified_members,
                    stdlib_root,
                )
            except ContractError as error:
                raise ContractError(
                    "new loaded module is not in the verified runtime closure: "
                    f"{loaded_name}"
                ) from error


def _clear_loaded_provider_modules(provider_name: str) -> None:
    for loaded_name in tuple(sys.modules):
        if loaded_name == provider_name or loaded_name.startswith(f"{provider_name}."):
            del sys.modules[loaded_name]


def _verify_loaded_data(
    provider_name: str,
    *,
    dictionary_prefix: Path | None,
    frequency_file: Path | None,
    data_artifacts: tuple[Artifact, ...],
) -> None:
    provided = {artifact.path.resolve() for artifact in data_artifacts}
    if provider_name == "spylls":
        if dictionary_prefix is None:
            raise ContractError("spylls requires --dictionary-prefix")
        required = {
            dictionary_prefix.with_suffix(".aff").resolve(),
            dictionary_prefix.with_suffix(".dic").resolve(),
        }
    else:
        if frequency_file is None:
            raise ContractError("symspellpy requires --frequency-file")
        required = {frequency_file.resolve()}
    if not required <= provided:
        raise ContractError("loaded provider data is not covered by declared digests")


def _parse_string_list(value: JsonValue, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractError(f"{context} must be a string list")
    return tuple(value)


def _parse_case(value: JsonValue, index: int) -> QualificationCase:
    context = f"cases[{index}]"
    raw = mapping(value, context)
    exact_fields(
        raw,
        frozenset(
            {
                "id",
                "category",
                "text",
                "start",
                "end",
                "expected_action",
                "expected_candidates",
                "expected_top1",
                "guard",
            }
        ),
        context,
    )
    category = string(raw["category"], f"{context}.category")
    expected_action = string(raw["expected_action"], f"{context}.expected_action")
    if expected_action not in {"candidate", "abstain"}:
        raise ContractError(f"{context}.expected_action is unsupported")
    expected_candidates = _parse_string_list(
        raw["expected_candidates"], f"{context}.expected_candidates"
    )
    expected_top1 = optional_string(raw["expected_top1"], f"{context}.expected_top1")
    if expected_action == "candidate":
        if not expected_candidates or expected_top1 not in expected_candidates:
            raise ContractError(f"{context} must define exact candidates and top1")
    elif expected_top1 is not None or (
        expected_candidates and category != "ambiguous_suggestions"
    ):
        raise ContractError(f"{context} abstention cannot define candidates")
    elif category == "ambiguous_suggestions" and len(expected_candidates) < 2:
        raise ContractError(
            f"{context} ambiguity must define at least two plausible candidates"
        )
    start = integer(raw["start"], f"{context}.start")
    end = integer(raw["end"], f"{context}.end")
    text = string(raw["text"], f"{context}.text")
    if start < 0 or end <= start or end > len(text):
        raise ContractError(f"{context} has invalid half-open span")
    if not string(raw["id"], f"{context}.id").startswith(
        ("typo_", "negative_", "guard_")
    ):
        raise ContractError(f"{context}.id is outside the declared scope")
    return QualificationCase(
        id=string(raw["id"], f"{context}.id"),
        category=category,
        text=text,
        start=start,
        end=end,
        expected_action=expected_action,
        expected_candidates=expected_candidates,
        expected_top1=expected_top1,
        guard=string(raw["guard"], f"{context}.guard"),
    )


def load_dataset(dataset_path: Path, manifest_path: Path) -> QualificationDataset:
    raw = mapping(read_json(dataset_path), "dataset")
    exact_fields(
        raw,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "dataset_id",
                "dataset_version",
                "license",
                "source",
                "cases",
            }
        ),
        "dataset",
    )
    if (
        raw["schema_id"] != "polis.spelling-provider-qualification"
        or raw["schema_version"] != 1
    ):
        raise ContractError("dataset schema identity mismatch")
    if raw["license"] != "CC0-1.0":
        raise ContractError("dataset license must be CC0-1.0")
    source = mapping(raw["source"], "dataset.source")
    exact_fields(
        source,
        frozenset(
            {"author", "created", "description", "protected_data_overlap", "provenance"}
        ),
        "dataset.source",
    )
    if (
        source["author"] != "Paweł Cyroń"
        or source["protected_data_overlap"] is not False
    ):
        raise ContractError("dataset provenance is not acceptable")
    raw_cases = raw["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ContractError("dataset.cases must be a non-empty array")
    cases = tuple(_parse_case(value, index) for index, value in enumerate(raw_cases))
    ids = tuple(case.id for case in cases)
    if len(ids) != len(set(ids)):
        raise ContractError("dataset has duplicate case id")
    if any(case.token == "" for case in cases):
        raise ContractError("dataset contains an empty token span")
    dataset_hash = _canonical_sha256(raw)
    dataset = QualificationDataset(
        dataset_id=string(raw["dataset_id"], "dataset.dataset_id"),
        dataset_version=integer(raw["dataset_version"], "dataset.dataset_version"),
        canonical_sha256=dataset_hash,
        cases=cases,
    )
    manifest = mapping(read_json(manifest_path), "manifest")
    exact_fields(
        manifest,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "dataset_id",
                "dataset_version",
                "canonical_sha256",
                "source",
                "case_ids",
            }
        ),
        "manifest",
    )
    if manifest["schema_id"] != "polis.spelling-provider-qualification-manifest":
        raise ContractError("manifest schema identity mismatch")
    if manifest["schema_version"] != 1:
        raise ContractError("manifest schema version mismatch")
    if (
        manifest["dataset_id"] != dataset.dataset_id
        or manifest["dataset_version"] != dataset.dataset_version
    ):
        raise ContractError("manifest dataset identity mismatch")
    if manifest["canonical_sha256"] != dataset.canonical_sha256:
        raise ContractError("manifest canonical hash mismatch")
    manifest_source = mapping(manifest["source"], "manifest.source")
    exact_fields(
        manifest_source,
        frozenset({"license", "provenance", "protected_data_overlap"}),
        "manifest.source",
    )
    if (
        manifest_source["license"] != "CC0-1.0"
        or manifest_source["protected_data_overlap"] is not False
    ):
        raise ContractError("manifest provenance is not acceptable")
    if tuple(_parse_string_list(manifest["case_ids"], "manifest.case_ids")) != ids:
        raise ContractError("manifest case order does not match dataset")
    return dataset


class _SpyllsAdapter:
    def __init__(self, dictionary: _SpyllsDictionary) -> None:
        self._dictionary = dictionary

    def known(self, token: str) -> bool:
        return self._dictionary.lookup(token)

    def suggest(self, token: str, limit: int) -> tuple[str, ...]:
        values = (str(value) for value in self._dictionary.suggest(token))
        return tuple(dict.fromkeys(values))[:limit]


class _SymspellAdapter:
    def __init__(
        self, dictionary: _SymspellDictionary, verbosity: _SymspellVerbosity
    ) -> None:
        self._dictionary = dictionary
        self._verbosity = verbosity

    def _lookup(self, token: str, distance: int) -> tuple[_SymspellResult, ...]:
        return tuple(
            self._dictionary.lookup(
                token, self._verbosity.TOP, max_edit_distance=distance
            )
        )

    def known(self, token: str) -> bool:
        return bool(self._lookup(token, 0))

    def suggest(self, token: str, limit: int) -> tuple[str, ...]:
        values = (value.term for value in self._lookup(token, 2))
        return tuple(dict.fromkeys(values))[:limit]


def _load_provider(
    provider_name: str, *, dictionary_prefix: Path | None, frequency_file: Path | None
) -> CandidateProvider:
    if provider_name == "spylls":
        if dictionary_prefix is None:
            raise ContractError("spylls requires --dictionary-prefix")
        module = importlib.import_module("spylls.hunspell")
        dictionary = module.Dictionary.from_files(str(dictionary_prefix))
        return _SpyllsAdapter(cast(_SpyllsDictionary, dictionary))
    if provider_name == "symspellpy":
        if frequency_file is None:
            raise ContractError("symspellpy requires --frequency-file")
        module = importlib.import_module("symspellpy")
        dictionary = module.SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        if not dictionary.load_dictionary(
            str(frequency_file), term_index=0, count_index=1
        ):
            raise ContractError(f"cannot load frequency dictionary: {frequency_file}")
        return _SymspellAdapter(
            cast(_SymspellDictionary, dictionary),
            cast(_SymspellVerbosity, module.Verbosity),
        )
    raise ContractError(f"unsupported provider: {provider_name}")


def _evaluate(
    dataset: QualificationDataset,
    provider: CandidateProvider,
    limit: int,
) -> tuple[tuple[QueryOutcome, ...], tuple[int, ...]]:
    outcomes: list[QueryOutcome] = []
    durations: list[int] = []
    for case in dataset.cases:
        if case.guard != "natural_language":
            outcomes.append(QueryOutcome(case.id, "guarded", None, ()))
            continue
        started = time.perf_counter_ns()
        known = provider.known(case.token)
        candidates = provider.suggest(case.token, limit)
        durations.append(time.perf_counter_ns() - started)
        status = "known" if known else ("candidate" if candidates else "abstain")
        outcomes.append(QueryOutcome(case.id, status, known, candidates))
    return tuple(outcomes), tuple(durations)


def _outcome_json(outcome: QueryOutcome) -> dict[str, JsonValue]:
    return {
        "case_id": outcome.case_id,
        "status": outcome.status,
        "known": outcome.known,
        "candidates": list(outcome.candidates),
    }


def _quality(
    dataset: QualificationDataset, outcomes: tuple[QueryOutcome, ...]
) -> dict[str, JsonValue]:
    by_id = {outcome.case_id: outcome for outcome in outcomes}
    correction_cases = [
        case for case in dataset.cases if case.expected_action == "candidate"
    ]
    negative_cases = [
        case
        for case in dataset.cases
        if case.expected_action == "abstain" and case.guard == "natural_language"
    ]
    recall_hits = sum(
        bool(set(case.expected_candidates) & set(by_id[case.id].candidates))
        for case in correction_cases
    )
    top1_hits = sum(
        by_id[case.id].candidates[:1] == (case.expected_top1,)
        for case in correction_cases
    )
    detected = sum(by_id[case.id].status == "candidate" for case in correction_cases)
    false_alarm_ids = tuple(
        case.id for case in negative_cases if by_id[case.id].status == "candidate"
    )
    guarded = [case for case in dataset.cases if case.guard != "natural_language"]
    ambiguous_diacritic = [
        case for case in negative_cases if case.category == "ambiguous_diacritic"
    ]
    ambiguous_suggestions = [
        case for case in negative_cases if case.category == "ambiguous_suggestions"
    ]
    return {
        "correction_cases": len(correction_cases),
        "candidate_detection_rate": detected / len(correction_cases),
        "candidate_recall": recall_hits / len(correction_cases),
        "top1_exactness": top1_hits / len(correction_cases),
        "negative_cases": len(negative_cases),
        "false_alarm_cases": len(false_alarm_ids),
        "false_alarm_rate": len(false_alarm_ids) / len(negative_cases),
        "false_alarm_case_ids": list(false_alarm_ids),
        "ambiguous_diacritic_cases": len(ambiguous_diacritic),
        "ambiguous_diacritic_abstentions": sum(
            by_id[case.id].status in {"known", "abstain"}
            for case in ambiguous_diacritic
        ),
        "ambiguous_suggestion_cases": len(ambiguous_suggestions),
        "ambiguous_suggestion_abstentions": sum(
            by_id[case.id].status in {"known", "abstain"}
            for case in ambiguous_suggestions
        ),
        "guarded_cases": len(guarded),
        "guarded_provider_calls": 0,
    }


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999) - 1))
    return ordered[index]


def _peak_rss_bytes() -> int:
    try:
        import resource
    except ImportError as error:
        raise ContractError("resource usage is unavailable on this platform") from error
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(value)
    if sys.platform.startswith("linux"):
        return int(value * 1024)
    raise ContractError(f"unsupported ru_maxrss units on {sys.platform}")


def _write_atomic(path: Path, payload: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qualify one offline spelling provider."
    )
    parser.add_argument("--provider", choices=("spylls", "symspellpy"), required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-artifact", type=Path, required=True)
    parser.add_argument("--dependency-artifact", type=Path, action="append", default=[])
    parser.add_argument("--data-file", type=Path, action="append", required=True)
    parser.add_argument("--dictionary-prefix", type=Path)
    parser.add_argument("--frequency-file", type=Path)
    parser.add_argument("--data-id", required=True)
    parser.add_argument("--data-license", required=True)
    parser.add_argument("--data-license-status", required=True)
    parser.add_argument("--data-source", required=True)
    parser.add_argument("--data-source-sha256", required=True)
    parser.add_argument("--expected-package-version", required=True)
    parser.add_argument("--package-license", required=True)
    parser.add_argument("--package-license-status", required=True)
    parser.add_argument("--expected-artifact-sha256", action="append", default=[])
    parser.add_argument("--expected-data-sha256", action="append", default=[])
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--limit", type=int, default=5)
    return parser


def _expected_hashes(values: list[str], context: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, digest = value.partition("=")
        if not separator or not name or len(digest) != 64:
            raise ContractError(f"invalid {context} entry: {value}")
        if name in result:
            raise ContractError(f"duplicate {context} entry: {name}")
        result[name] = digest
    return result


def _verify_hashes(
    artifacts: tuple[Artifact, ...], expected: dict[str, str], context: str
) -> None:
    if set(expected) != {artifact.path.name for artifact in artifacts}:
        raise ContractError(f"{context} hash declarations do not match artifacts")
    for item in artifacts:
        if expected.get(item.path.name) != item.sha256:
            raise ContractError(f"{context} digest mismatch for {item.path.name}")


def _verify_pinned_metadata(
    options: argparse.Namespace,
    package_artifact: Artifact,
    dependency_artifacts: tuple[Artifact, ...],
    data_artifacts: tuple[Artifact, ...],
) -> None:
    expected = EXPECTED_PROVIDER_METADATA[options.provider]
    if dependency_artifacts:
        raise ContractError(
            "qualification does not accept unpinned provider dependencies"
        )
    comparisons = {
        "expected_package_version": "package_version",
        "package_license": "package_license",
        "package_license_status": "package_license_status",
        "data_id": "data_id",
        "data_license": "data_license",
        "data_license_status": "data_license_status",
        "data_source": "data_source",
        "data_source_sha256": "data_source_sha256",
    }
    for option_name, metadata_name in comparisons.items():
        if getattr(options, option_name) != expected[metadata_name]:
            raise ContractError(f"provider metadata drift: {metadata_name}")
    if package_artifact.sha256 != expected["package_sha256"]:
        raise ContractError("provider package is not the approved artifact")
    actual_data = {artifact.path.name: artifact.sha256 for artifact in data_artifacts}
    if actual_data != expected["data_sha256"]:
        raise ContractError("provider data artifacts are not the approved set")


def run(arguments: list[str]) -> dict[str, JsonValue]:
    options = _parser().parse_args(arguments)
    if options.repetitions < 2 or options.limit < 1:
        raise ContractError("repetitions must be at least 2 and limit must be positive")
    _validate_public_fixture_paths(options.dataset, options.manifest)
    _validate_output_path(options)
    dataset = load_dataset(options.dataset, options.manifest)
    if (
        dataset.dataset_id != EXPECTED_PUBLIC_DATASET_ID
        or dataset.canonical_sha256 != EXPECTED_PUBLIC_DATASET_SHA256
    ):
        raise ContractError("qualification dataset identity or digest is not approved")
    package_artifact = _artifact(options.package_artifact)
    dependency_artifacts = tuple(
        _artifact(path) for path in options.dependency_artifact
    )
    data_artifacts = tuple(_artifact(path) for path in options.data_file)
    expected_artifact_hashes = _expected_hashes(
        options.expected_artifact_sha256, "artifact hash"
    )
    expected_data_hashes = _expected_hashes(options.expected_data_sha256, "data hash")
    _verify_hashes(
        (package_artifact, *dependency_artifacts),
        expected_artifact_hashes,
        "artifact",
    )
    _verify_hashes(data_artifacts, expected_data_hashes, "data")
    _verify_pinned_metadata(
        options, package_artifact, dependency_artifacts, data_artifacts
    )

    def verify_current_artifacts() -> None:
        nonlocal package_artifact, dependency_artifacts, data_artifacts
        package_artifact = _artifact(package_artifact.path)
        dependency_artifacts = tuple(
            _artifact(artifact.path) for artifact in dependency_artifacts
        )
        data_artifacts = tuple(_artifact(artifact.path) for artifact in data_artifacts)
        _verify_hashes(
            (package_artifact, *dependency_artifacts),
            expected_artifact_hashes,
            "artifact",
        )
        _verify_hashes(data_artifacts, expected_data_hashes, "data")

    with _offline_only() as assert_offline_boundary:
        install_root, verified_members = _verify_installed_package(
            options.provider, package_artifact
        )
        _clear_loaded_provider_modules(options.provider)
        baseline_module_names = frozenset(sys.modules)
        started = time.perf_counter_ns()
        with _provider_import_boundary(
            options.provider, install_root, verified_members
        ):
            provider = _load_provider(
                options.provider,
                dictionary_prefix=options.dictionary_prefix,
                frequency_file=options.frequency_file,
            )
        startup_ns = time.perf_counter_ns() - started
        assert_offline_boundary()
        verify_current_artifacts()
        _verify_loaded_package(options.provider, package_artifact)
        _verify_loaded_module_closure(
            options.provider, package_artifact, baseline_module_names
        )
        _verify_loaded_data(
            options.provider,
            dictionary_prefix=options.dictionary_prefix,
            frequency_file=options.frequency_file,
            data_artifacts=data_artifacts,
        )
        package_version = importlib.metadata.version(options.provider)
        if package_version != options.expected_package_version:
            raise ContractError(
                "package version drift: "
                f"expected {options.expected_package_version}, got {package_version}"
            )
        repetitions: list[tuple[QueryOutcome, ...]] = []
        repetition_durations: list[int] = []
        query_durations: list[int] = []
        for _ in range(options.repetitions):
            outcomes, durations = _evaluate(dataset, provider, options.limit)
            assert_offline_boundary()
            verify_current_artifacts()
            _verify_loaded_package(options.provider, package_artifact)
            _verify_loaded_module_closure(
                options.provider, package_artifact, baseline_module_names
            )
            _verify_loaded_data(
                options.provider,
                dictionary_prefix=options.dictionary_prefix,
                frequency_file=options.frequency_file,
                data_artifacts=data_artifacts,
            )
            repetition_durations.append(sum(durations))
            query_durations.extend(durations)
            repetitions.append(outcomes)
        assert_offline_boundary()
        verify_current_artifacts()
    final_outcomes = repetitions[-1]
    repetition_hashes = [
        _canonical_sha256([_outcome_json(outcome) for outcome in outcomes])
        for outcomes in repetitions
    ]
    identity = ProviderIdentity(
        name=options.provider,
        package_version=package_version,
        package_license=options.package_license,
        package_license_status=options.package_license_status,
        data_id=options.data_id,
        data_license=options.data_license,
        data_license_status=options.data_license_status,
        data_source=options.data_source,
        data_source_sha256=options.data_source_sha256,
        package_artifact=package_artifact,
        dependency_artifacts=dependency_artifacts,
        data_artifacts=data_artifacts,
    )
    quality = _quality(dataset, final_outcomes)
    if not query_durations:
        raise ContractError("dataset contains no measurable natural-language queries")
    package_bytes = sum(
        artifact.size_bytes for artifact in (package_artifact, *dependency_artifacts)
    )
    data_bytes = sum(artifact.size_bytes for artifact in data_artifacts)
    report: dict[str, JsonValue] = {
        "schema_id": "polis.spelling-provider-qualification-provider-report",
        "schema_version": 1,
        "identity": {
            "provider": identity.name,
            "package_version": identity.package_version,
            "package_license": identity.package_license,
            "package_license_status": identity.package_license_status,
            "data_id": identity.data_id,
            "data_license": identity.data_license,
            "data_license_status": identity.data_license_status,
            "data_source": identity.data_source,
            "data_source_sha256": identity.data_source_sha256,
        },
        "artifacts": {
            "package": {
                "filename": package_artifact.path.name,
                "sha256": package_artifact.sha256,
                "size_bytes": package_artifact.size_bytes,
            },
            "dependencies": [
                {
                    "filename": artifact.path.name,
                    "sha256": artifact.sha256,
                    "size_bytes": artifact.size_bytes,
                }
                for artifact in dependency_artifacts
            ],
            "data": [
                {
                    "filename": artifact.path.name,
                    "sha256": artifact.sha256,
                    "size_bytes": artifact.size_bytes,
                }
                for artifact in data_artifacts
            ],
        },
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "dataset_version": dataset.dataset_version,
            "canonical_sha256": dataset.canonical_sha256,
        },
        "outcomes": [_outcome_json(outcome) for outcome in final_outcomes],
        "quality": quality,
        "performance": {
            "startup_ns": startup_ns,
            "repetition_total_ns": repetition_durations,
            "repetition_mean_ns": int(statistics.fmean(repetition_durations)),
            "measured_queries": len(query_durations),
            "query_p50_ns": _percentile(query_durations, 0.50),
            "query_p95_ns": _percentile(query_durations, 0.95),
            "throughput_cases_per_second": len(query_durations)
            * 1_000_000_000
            / sum(query_durations),
            "peak_rss_bytes": _peak_rss_bytes(),
            "dependency_size_bytes": package_bytes,
            "data_size_bytes": data_bytes,
        },
        "reproducibility": {
            "repetitions": options.repetitions,
            "stable": len(set(repetition_hashes)) == 1,
            "repetition_hashes": repetition_hashes,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "platform_constraints": {
            "python": ">=3.12",
            "supported_platforms": ["darwin", "linux"],
            "rss_units": {
                "darwin": "bytes",
                "linux": "kibibytes converted to bytes",
            },
        },
    }
    report["normalized_digest"] = _canonical_sha256(
        {
            key: report[key]
            for key in (
                "schema_id",
                "schema_version",
                "identity",
                "artifacts",
                "dataset",
                "outcomes",
                "quality",
                "reproducibility",
            )
        }
    )
    return report


def main(arguments: list[str] | None = None) -> int:
    try:
        report = run(arguments if arguments is not None else sys.argv[1:])
    except (ContractError, ImportError, OSError, ValueError) as error:
        print(f"qualification inconclusive: {error}", file=sys.stderr)
        return 3
    output = Path(
        str(
            _parser()
            .parse_args(arguments if arguments is not None else sys.argv[1:])
            .output
        )
    )
    print(f"{report['identity']['provider']}: {report['normalized_digest']}")
    if report["reproducibility"]["stable"] is not True:
        return 3
    _write_atomic(output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
