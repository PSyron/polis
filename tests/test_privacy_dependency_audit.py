from __future__ import annotations

import re
import socket
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

from polis import Analyzer, AnalyzerConfig, UnknownFindingError

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS: Final = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_pat": re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "slack_token": re.compile(r"\bxoxb-[A-Za-z0-9-]{10,}\b"),
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    ),
}
SUSPICIOUS_DISTRIBUTION_EXTENSIONS: Final = {
    ".onnx",
    ".ggml",
    ".gguf",
    ".ckpt",
    ".safetensors",
    ".pt",
    ".pth",
    ".bin",
    ".npy",
    ".npz",
}


def _list_tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def _read_text_if_possible(path: Path) -> str | None:
    if path.suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".zip",
        ".whl",
        ".gz",
        ".pdf",
        ".bin",
    }:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def test_no_secret_literals_in_versioned_files() -> None:
    findings: list[str] = []
    for path in _list_tracked_files():
        content = _read_text_if_possible(path)
        if content is None:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path}: {name}")
                break

    assert not findings, "Potential secret artifacts detected: " + "; ".join(findings)


def test_analysis_diagnostics_do_not_leak_user_text_by_default() -> None:
    text = "To jest prywatny_przypadek_123"
    result = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False)).analyze(text)

    with pytest.raises(UnknownFindingError) as exc_info:
        result.apply(("finding_does_not_exist",))

    assert text not in str(exc_info.value)
    assert text not in str(exc_info.value.context)


def test_analyzer_without_model_backends_does_not_attempt_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _blocked(
        _address: tuple[str, int] | str,
        *_args: object,
        **_kwargs: object,
    ) -> object:
        raise AssertionError("network blocked")

    monkeypatch.setattr(socket, "create_connection", _blocked)

    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))
    result = analyzer.analyze("Witaj, świecie")
    assert isinstance(result.text, str)


def test_built_release_artifacts_do_not_include_model_files(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr

    wheel = next(dist.glob("*.whl"))
    sdist = next(dist.glob("*.tar.gz"))

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()

    for ext in SUSPICIOUS_DISTRIBUTION_EXTENSIONS:
        assert not any(name.endswith(ext) for name in wheel_names), (
            f"wheel includes suspicious distribution artifact with extension {ext}"
        )
        assert not any(name.endswith(ext) for name in sdist_names), (
            f"sdist includes suspicious distribution artifact with extension {ext}"
        )
