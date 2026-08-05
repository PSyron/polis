from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_PACKAGES = {
    "hatchling": "1.31.0",
    "packaging": "26.2",
    "pathspec": "1.1.1",
    "pluggy": "1.6.0",
    "trove-classifiers": "2026.6.1.19",
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def locked_wheels(lock: Path) -> list[dict[str, str | int]]:
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    selected: list[dict[str, str | int]] = []
    for package in packages:
        name = package["name"]
        if name not in EXPECTED_PACKAGES:
            continue
        version = package["version"]
        if version != EXPECTED_PACKAGES[name]:
            expected_version = EXPECTED_PACKAGES[name]
            raise SystemExit(
                f"uv.lock version mismatch for {name}: {version} != {expected_version}"
            )
        universal = [
            wheel
            for wheel in package.get("wheels", [])
            if wheel["url"].endswith("-py3-none-any.whl")
        ]
        if len(universal) != 1:
            raise SystemExit(f"uv.lock must contain one universal wheel for {name}")
        wheel = universal[0]
        selected.append(
            {
                "name": name,
                "version": version,
                "filename": Path(urlparse(wheel["url"]).path).name,
                "url": wheel["url"],
                "size": wheel["size"],
                "sha256": wheel["hash"].removeprefix("sha256:"),
            }
        )
    if {entry["name"] for entry in selected} != set(EXPECTED_PACKAGES):
        raise SystemExit(
            "uv.lock does not contain the exact build wheelhouse package set"
        )
    return sorted(selected, key=lambda entry: str(entry["name"]))


def validate_wheelhouse(manifest: Path, wheelhouse: Path, lock: Path) -> None:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if set(payload) != {"schema_version", "lock_sha256", "wheels"}:
            raise ValueError
        if payload["schema_version"] != 1 or not isinstance(payload["wheels"], list):
            raise ValueError
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SystemExit("wheelhouse manifest is malformed") from exc

    expected = locked_wheels(lock)
    for entry in expected:
        entry.pop("url")
    if payload["lock_sha256"] != sha256_path(lock) or payload["wheels"] != expected:
        raise SystemExit("wheelhouse manifest does not match uv.lock")

    expected_files = {str(entry["filename"]) for entry in expected}
    try:
        members = list(wheelhouse.iterdir())
    except OSError as exc:
        raise SystemExit("wheelhouse cannot be read") from exc
    if any(path.is_symlink() or not path.is_file() for path in members):
        raise SystemExit("wheelhouse contains non-regular members")
    actual_files = {path.name for path in members}
    if actual_files != expected_files:
        raise SystemExit("wheelhouse contains missing or extra members")
    for entry in expected:
        path = wheelhouse / str(entry["filename"])
        if path.stat().st_size != entry["size"] or sha256_path(path) != entry["sha256"]:
            raise SystemExit("wheelhouse member is missing or tampered")
