"""Fail-closed bindings between a wheel archive and an installed interpreter."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from polis.evaluation.quality_report_models import QualityReportError

_CHECK_SCRIPT = r"""
import base64
import csv
import hashlib
import importlib.metadata
import io
import os
import pathlib
import sys
import zipfile


def digest(content):
    encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
    return "sha256=" + encoded.decode("ascii").rstrip("=")


def fail(message):
    raise SystemExit(message)


wheel = pathlib.Path(sys.argv[1])
expected_digest = sys.argv[2]
if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected_digest:
    fail("wheel digest does not match declared artifact")
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    if len(names) != len(set(names)):
        fail("wheel archive contains duplicate members")
    prefixes = {name.split("/", 1)[0] for name in names if ".dist-info/" in name}
    if len(prefixes) != 1:
        fail("wheel must contain one dist-info directory")
    prefix = next(iter(prefixes))
    metadata_name = prefix + "/METADATA"
    record_name = prefix + "/RECORD"
    if metadata_name not in names or record_name not in names:
        fail("wheel must contain METADATA and RECORD")
    metadata = archive.read(metadata_name).decode("utf-8")
    fields = dict(
        line.split(": ", 1) for line in metadata.splitlines() if ": " in line
    )
    version = fields.get("Version")
    if fields.get("Name") != "polis-nlp" or not version:
        fail("wheel distribution identity mismatch")
    if not wheel.name.startswith("polis_nlp-" + version + "-"):
        fail("wheel filename identity mismatch")
    if prefix != "polis_nlp-" + version + ".dist-info":
        fail("wheel dist-info identity mismatch")
    rows = list(csv.reader(io.StringIO(archive.read(record_name).decode("utf-8"))))
    if any(len(row) != 3 for row in rows):
        fail("wheel RECORD is malformed")
    wheel_records = {row[0]: (row[1], row[2]) for row in rows}
    if len(wheel_records) != len(rows) or set(wheel_records) != set(names):
        fail("wheel RECORD does not cover wheel members")
    for name, (member_digest, size) in wheel_records.items():
        content = archive.read(name)
        if name == record_name:
            if member_digest or size:
                fail("wheel RECORD self-entry is malformed")
        elif member_digest != digest(content) or size != str(len(content)):
            fail("wheel RECORD does not match wheel bytes")

distribution = importlib.metadata.distribution("polis-nlp")
if (
    distribution.metadata.get("Name") != "polis-nlp"
    or distribution.version != version
):
    fail("installed distribution identity mismatch")
installed_files = distribution.files
if installed_files is None or not set(names).issubset(
    {item.as_posix() for item in installed_files}
):
    fail("installed distribution is missing wheel members")
installed_record = pathlib.Path(
    str(distribution.locate_file(pathlib.PurePosixPath(record_name)))
)
installed_rows = list(
    csv.reader(io.StringIO(installed_record.read_text(encoding="utf-8")))
)
installed_records = {
    row[0]: (row[1], row[2]) for row in installed_rows if len(row) == 3
}
for name, record in wheel_records.items():
    if installed_records.get(name) != record:
        fail("installed RECORD does not match wheel RECORD")
for name, (member_digest, size) in wheel_records.items():
    if name == record_name:
        continue
    installed = pathlib.Path(
        str(distribution.locate_file(pathlib.PurePosixPath(name)))
    )
    if not installed.is_file():
        fail("installed wheel member is missing: " + name)
    content = installed.read_bytes()
    if member_digest != digest(content) or size != str(len(content)):
        fail("installed bytes do not match wheel bytes")
import polis
installed_init = pathlib.Path(
    str(distribution.locate_file("polis/__init__.py"))
).resolve()
if pathlib.Path(polis.__file__).resolve() != installed_init:
    fail("interpreter is not executing installed polis")
"""


def validate_interpreter_wheel(python: str, wheel: Path, wheel_sha256: str) -> None:
    """Verify exact wheel-member bytes in the distribution seen by ``python``."""

    if not wheel.is_file() or wheel.suffix != ".whl":
        raise QualityReportError("v4 wheel path must point to an existing wheel")
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != wheel_sha256:
        raise QualityReportError("v4 wheel digest does not match declared artifact")
    try:
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [python, "-c", _CHECK_SCRIPT, str(wheel), wheel_sha256],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
    except OSError as error:
        raise QualityReportError(
            f"v4 interpreter cannot verify the provided wheel: {python}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise QualityReportError(
            f"v4 interpreter is not bound to the provided wheel: {detail}"
        )


__all__ = ["validate_interpreter_wheel"]
