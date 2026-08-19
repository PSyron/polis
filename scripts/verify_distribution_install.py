"""Verify wheel and sdist installation while every socket connection is denied."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__:
    from scripts.distribution_wheelhouse import validate_wheelhouse
else:
    from distribution_wheelhouse import validate_wheelhouse

SOCKET_BLOCKER = """import socket
def _deny(*args, **kwargs):
    raise OSError("network blocked by Polis distribution verifier")
socket.socket.connect = _deny
socket.socket.connect_ex = _deny
socket.socket.sendto = _deny
if hasattr(socket.socket, "sendmsg"):
    socket.socket.sendmsg = _deny
socket.create_connection = _deny
"""
SOCKET_PROBE = """import socket
probes = [
    ("socket.connect", lambda: socket.socket().connect(("127.0.0.1", 9))),
    ("socket.connect_ex", lambda: socket.socket().connect_ex(("127.0.0.1", 9))),
    ("socket.create_connection", lambda: socket.create_connection(("127.0.0.1", 9))),
    (
        "socket.sendto",
        lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(
            b"probe", ("127.0.0.1", 9)
        ),
    ),
]
if hasattr(socket.socket, "sendmsg"):
    probes.append(
        (
            "socket.sendmsg",
            lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendmsg(
                [b"probe"], [], 0, ("127.0.0.1", 9)
            ),
        )
    )
for name, probe in probes:
    try:
        probe()
    except OSError as exc:
        if str(exc) != "network blocked by Polis distribution verifier":
            message = f"{name} failed without the socket blocker: {exc}"
            raise SystemExit(message) from exc
        print(f"{name}=blocked")
    else:
        raise SystemExit(f"{name} was not blocked")
"""
EVALUATION_EXPORTS = (
    "BaselineResult",
    "EvaluationDataset",
    "QualityCounts",
    "SAFETY_CORPUS_ID",
    "SAFETY_CORPUS_V2_ID",
    "SAFETY_REVIEW_CHECKLIST_VERSION",
    "SAFETY_REVIEW_CHECKLIST_V2_VERSION",
    "assert_no_cross_corpus_leakage",
    "evaluate_baseline",
    "findings_snapshot_for_run",
    "load_dataset",
    "load_safety_corpus_json",
    "load_safety_corpus_xml",
    "safety_corpus_digest",
    "safety_entity_catalog_ids",
    "select_safety_cases_for_purpose",
    "validate_dataset",
    "validate_safety_corpus",
)
PUBLIC_EVAL_IMPORTS = (
    "polis.evaluation.datasets",
    "polis.evaluation.datasets.quality",
    "polis.evaluation.datasets.quality.v1",
    "polis.evaluation.datasets.quality.v2",
    "polis.evaluation.datasets.v1",
)
PUBLIC_EVAL_RESOURCES = (
    ("polis.evaluation.datasets.quality.v1", "cases.json"),
    ("polis.evaluation.datasets.quality.v1", "manifest.json"),
    ("polis.evaluation.datasets.quality.v2", "cases.json"),
    ("polis.evaluation.datasets.quality.v2", "manifest.json"),
    ("polis.evaluation.datasets.v1", "cases.json"),
)
EVALUATION_SOURCE = Path(__file__).resolve().parents[1] / "src" / "polis" / "evaluation"
FORBIDDEN_REPOSITORY_MODULES = tuple(
    f"polis.evaluation.{path.stem}"
    for path in sorted(
        (
            EVALUATION_SOURCE / "__main__.py",
            *EVALUATION_SOURCE.glob("calibration_*.py"),
            *EVALUATION_SOURCE.glob("holdout_*.py"),
            EVALUATION_SOURCE / "rule_family_qualification.py",
        )
    )
)


def _venv_python(venv_dir: Path) -> Path:
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    for candidate in (bin_dir / "python", bin_dir / "python3", bin_dir / "python.exe"):
        if candidate.exists():
            return candidate
    raise SystemExit(f"could not locate python executable in virtualenv at {venv_dir}")


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        check=False,
        env=env,
        capture_output=True,
        timeout=120,
    )


def _assert_distribution_public_import_contract(
    python: Path, *, label: str, smoke_cwd: Path, env: dict[str, str]
) -> None:
    module_check = f"""
from importlib import resources, util


required_modules = {PUBLIC_EVAL_IMPORTS}
for module in required_modules:
    if util.find_spec(module) is None:
        raise SystemExit("{label} missing public evaluation module: " + module)
    print("public_module=" + module + " present")

for module, resource in {PUBLIC_EVAL_RESOURCES}:
    if not resources.files(module).joinpath(resource).is_file():
        raise SystemExit(
            "{label} missing public dataset resource: " + module + ":" + resource
        )
    print("public_resource=" + module + ":" + resource + " present")

for module in {FORBIDDEN_REPOSITORY_MODULES}:
    if util.find_spec(module) is not None:
        raise SystemExit("{label} exposed repository-only module: " + module)
    print("forbidden_module=" + module + " absent")
"""
    result = _run(
        [str(python), "-c", module_check.strip()],
        cwd=smoke_cwd,
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr)
    print(result.stdout.strip())
    print(f"artifact={label} public_dataset_imports=ok")
    print(f"artifact={label} repository_only_modules=absent")


def _offline_environment(blocker: Path, wheelhouse: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PIP_NO_INDEX"] = "1"
    env["PIP_FIND_LINKS"] = str(wheelhouse.resolve())
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONPATH"] = str(blocker)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        raise SystemExit(f"{label} failed:\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def _install_and_smoke(
    artifact: Path,
    *,
    label: str,
    interpreter: Path,
    wheelhouse: Path,
    smoke_cwd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"polis-install-{label}-") as workdir:
        work = Path(workdir)
        venv = work / "venv"
        blocker = work / "network-blocker"
        blocker.mkdir()
        (blocker / "sitecustomize.py").write_text(SOCKET_BLOCKER, encoding="utf-8")
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        _require_success(
            _run([str(interpreter), "-m", "venv", str(venv)], cwd=work, env=clean_env),
            "virtualenv creation",
        )
        python = _venv_python(venv)
        env = _offline_environment(blocker, wheelhouse)
        probe = _require_success(
            _run([str(python), "-c", SOCKET_PROBE], cwd=smoke_cwd, env=env),
            "socket denial probe",
        )
        _require_success(
            _run(
                [str(python), "-m", "pip", "install", "--no-input", str(artifact)],
                cwd=smoke_cwd,
                env=env,
            ),
            f"{label} offline installation",
        )
        api = _require_success(
            _run(
                [
                    str(python),
                    "-c",
                    "from importlib.metadata import version; "
                    "from polis import Analyzer, AnalyzerConfig; "
                    "r=Analyzer(AnalyzerConfig()).analyze("
                    "'Zeby nauczyc sie polskiego.'); "
                    "print(f\"version={version('polis-nlp')} "
                    'issues={len(r.issues)} text={r.text}")',
                ],
                cwd=smoke_cwd,
                env=env,
            ),
            f"{label} API smoke",
        )
        exports = _require_success(
            _run(
                [
                    str(python),
                    "-c",
                    "import polis.evaluation as evaluation; "
                    f"expected = {EVALUATION_EXPORTS!r}; "
                    "actual = tuple(evaluation.__all__); "
                    "assert actual == expected, 'evaluation export contract'; "
                    "print(f'evaluation_exports={actual!r}')",
                ],
                cwd=smoke_cwd,
                env=env,
            ),
            f"{label} evaluation export contract",
        )
        _require_success(
            _run(
                [
                    str(python),
                    "-c",
                    "import polis.evaluation\nprint('evaluation import ok')",
                ],
                cwd=smoke_cwd,
                env=env,
            ),
            f"{label} package import",
        )
        _assert_distribution_public_import_contract(
            python, label=label, smoke_cwd=smoke_cwd, env=env
        )
        evaluation_cli = _run(
            [str(python), "-m", "polis.evaluation", "--help"],
            cwd=smoke_cwd,
            env=env,
        )
        if evaluation_cli.returncode == 0 or "polis.evaluation.__main__" not in (
            evaluation_cli.stdout + evaluation_cli.stderr
        ):
            raise SystemExit(f"{label} exposed repository-only evaluation CLI")
        cli_env = env | {"PYTHONIOENCODING": "cp1252"}
        cli = _require_success(
            _run(
                [str(python), "-m", "polis.cli", "analyze", "--json", "Witaj,świecie."],
                cwd=smoke_cwd,
                env=cli_env,
            ),
            f"{label} CLI smoke",
        )
        try:
            payload = json.loads(cli)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{label} CLI emitted malformed JSON") from exc
        if payload.get("text") != "Witaj,świecie." or "issues" not in payload:
            raise SystemExit(f"{label} CLI JSON failed Unicode contract")
        print(probe)
        print(f"artifact={label} {api}")
        print(f"artifact={label} {exports}")
        print(f"artifact={label} repository_only_evaluation_cli=absent")
        print(cli)


def _require_empty_smoke_cwd(path: Path) -> Path:
    smoke_cwd = path.resolve()
    if not smoke_cwd.exists():
        raise SystemExit(f"smoke cwd must exist: {smoke_cwd}")
    if not smoke_cwd.is_dir():
        raise SystemExit(f"smoke cwd must be a directory: {smoke_cwd}")
    if any(smoke_cwd.iterdir()):
        raise SystemExit(f"smoke cwd must be empty: {smoke_cwd}")
    checkout = Path(__file__).resolve().parents[1]
    try:
        smoke_cwd.relative_to(checkout)
    except ValueError:
        return smoke_cwd
    raise SystemExit(f"smoke cwd must be outside checkout: {smoke_cwd}")


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument(
        "--smoke-cwd",
        type=Path,
        required=True,
        help="Existing empty directory used by all installed smoke subprocesses",
    )
    parser.add_argument("--python", type=Path, action="append")
    args = parser.parse_args()
    dist = args.dist.resolve()
    wheelhouse = args.wheelhouse.resolve()
    wheelhouse_manifest = args.wheelhouse_manifest.resolve()
    smoke_cwd = _require_empty_smoke_cwd(args.smoke_cwd)
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("dist must contain exactly one wheel and one source archive")
    lock = Path(__file__).resolve().parents[1] / "uv.lock"
    validate_wheelhouse(wheelhouse_manifest, wheelhouse, lock)
    interpreters = args.python or [Path(sys.executable)]
    for interpreter in interpreters:
        if not interpreter.is_file():
            raise SystemExit(f"python interpreter not found: {interpreter}")
        _install_and_smoke(
            wheels[0],
            label="wheel",
            interpreter=interpreter,
            wheelhouse=wheelhouse,
            smoke_cwd=smoke_cwd,
        )
        _install_and_smoke(
            sdists[0],
            label="sdist",
            interpreter=interpreter,
            wheelhouse=wheelhouse,
            smoke_cwd=smoke_cwd,
        )
    print(f"smoke-cwd={smoke_cwd}")
    print("distribution installation checks passed with network denied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
