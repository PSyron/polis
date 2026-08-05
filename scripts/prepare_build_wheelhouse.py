"""Prepare the exact locked build-backend wheelhouse used by offline checks."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from distribution_wheelhouse import locked_wheels, sha256_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit("wheelhouse output must be empty")
    if args.manifest.exists():
        raise SystemExit("wheelhouse manifest must not already exist")
    args.output.mkdir(parents=True, exist_ok=True)

    manifest_wheels: list[dict[str, str | int]] = []
    for locked in locked_wheels(args.lock):
        url = str(locked.pop("url"))
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            content = response.read()
        if len(content) != locked["size"] or sha256_bytes(content) != locked["sha256"]:
            raise SystemExit(f"download does not match uv.lock: {locked['filename']}")
        (args.output / str(locked["filename"])).write_bytes(content)
        manifest_wheels.append(locked)

    payload = {
        "schema_version": 1,
        "lock_sha256": sha256_bytes(args.lock.read_bytes()),
        "wheels": manifest_wheels,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"prepared wheelhouse wheels={len(manifest_wheels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
