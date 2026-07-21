"""Run pinned offline MLX-LM QLoRA and record local-only training evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from experiments.qlora_benchmark.experiment import (
    build_mlx_training_config,
    load_experiment_config,
    parse_mlx_training_log,
    prepare_mlx_dataset,
    verify_pinned_artifacts,
)

ROOT = Path(__file__).parents[2]
DEFAULT_CONFIG = ROOT / "experiments" / "qlora_benchmark" / "config.json"
DEFAULT_DATASET = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
DEFAULT_CORPUS = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_corpus_v3.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model-snapshot", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--mlx-lora", type=Path, required=True)
    parser.add_argument("--iterations", type=int)
    args = parser.parse_args(argv)

    config = load_experiment_config(args.config)
    verify_pinned_artifacts(
        config,
        model_snapshot=args.model_snapshot,
        dataset_directory=DEFAULT_DATASET,
        corpus_v3_path=DEFAULT_CORPUS,
    )
    if args.iterations is not None and args.iterations <= 0:
        raise ValueError("iterations must be positive")
    work_dir = args.work_dir.resolve()
    if _inside(work_dir, ROOT):
        raise ValueError("QLoRA work directory must be outside the repository")
    work_dir.mkdir(parents=True, exist_ok=True)
    data_dir = work_dir / "mlx-data"
    adapter_dir = work_dir / "adapter"
    prepare_mlx_dataset(
        config,
        dataset_directory=DEFAULT_DATASET,
        corpus_v3_path=DEFAULT_CORPUS,
        output_directory=data_dir,
    )
    mlx_config = build_mlx_training_config(
        config,
        model_snapshot=args.model_snapshot.resolve(),
        data_directory=data_dir,
        adapter_directory=adapter_dir,
        iterations=args.iterations,
    )
    generated_config = work_dir / "mlx-training-config.json"
    generated_config.write_text(
        json.dumps(mlx_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    log_path = work_dir / "training.log"
    metadata_path = work_dir / "training-metadata.json"
    swap_before = _swap_used_bytes()
    started = time.time()
    peak_rss_bytes = 0
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [str(args.mlx_lora), "--config", str(generated_config)],
            cwd=work_dir,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        while process.poll() is None:
            peak_rss_bytes = max(peak_rss_bytes, _rss_bytes(process.pid))
            time.sleep(0.25)
        exit_code = process.wait()
    finished = time.time()
    swap_after = _swap_used_bytes()
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    curves = parse_mlx_training_log(log_text)
    weights = adapter_dir / "adapters.safetensors"
    metadata = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "exit_code": exit_code,
        "started_unix": started,
        "finished_unix": finished,
        "duration_seconds": finished - started,
        "peak_process_rss_bytes": peak_rss_bytes,
        "swap_used_before_bytes": swap_before,
        "swap_used_after_bytes": swap_after,
        "swap_delta_bytes": swap_after - swap_before,
        "iterations": mlx_config["iters"],
        "learning_curve": [asdict(point) for point in curves],
        "adapter_sha256": _sha256(weights) if weights.is_file() else None,
        "adapter_size_bytes": weights.stat().st_size if weights.is_file() else None,
        "generated_config_sha256": _sha256(generated_config),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if exit_code != 0:
        raise RuntimeError(f"MLX-LM training failed; inspect {log_path}")
    if not curves or not weights.is_file():
        raise RuntimeError("MLX-LM training did not produce complete evidence")
    print(metadata_path)
    return 0


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _rss_bytes(pid: int) -> int:
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        return int(result.stdout.strip()) * 1024
    except ValueError:
        return 0


def _swap_used_bytes() -> int:
    result = subprocess.run(
        ["sysctl", "-n", "vm.swapusage"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"used = ([0-9.]+)([MG])", result.stdout)
    if match is None:
        raise RuntimeError("cannot parse macOS swap usage")
    scale = 1024**2 if match.group(2) == "M" else 1024**3
    return round(float(match.group(1)) * scale)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
