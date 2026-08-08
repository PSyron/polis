from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.morphology_provider_benchmark import (
    UnsupportedPlatformError,
    run_benchmark,
)
from scripts.morphology_provider_contract import load_qualification_dataset
from scripts.morphology_provider_json import ContractError, JsonValue
from scripts.morphology_provider_morfeusz import load_provider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qualify the pinned offline morphology provider."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


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


def main(arguments: list[str] | None = None) -> int:
    namespace = _parser().parse_args(arguments)
    dataset_path: Path = namespace.dataset
    output_path: Path = namespace.output
    manifest_path = dataset_path.with_suffix(".manifest.json")
    try:
        dataset = load_qualification_dataset(dataset_path, manifest_path)
    except ContractError as error:
        print(f"invalid qualification dataset: {error}", file=sys.stderr)
        return 2
    try:
        started = time.perf_counter_ns()
        provider = load_provider()
        startup_ns = time.perf_counter_ns() - started
        result = run_benchmark(dataset, provider, startup_ns=startup_ns)
    except (ImportError, UnsupportedPlatformError) as error:
        print(f"qualification inconclusive: {error}", file=sys.stderr)
        return 3
    _write_atomic(output_path, result.report)
    print(f"{result.verdict}: {result.report['normalized_digest']}")
    return 3 if result.verdict == "INCONCLUSIVE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
