from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.release_identity_authority import JsonValue, parse_json_value
from scripts.release_identity_models import ReleaseIdentityError, ReleaseManifest

_HTTP_TIMEOUT_SECONDS = 10.0


def download_pypi(
    *,
    package_index_url: str,
    manifest: ReleaseManifest,
    output: Path,
    max_attempts: int,
    retry_seconds: float,
) -> None:
    if max_attempts < 1 or retry_seconds < 0:
        raise ReleaseIdentityError("download retry settings are invalid")
    if not output.is_dir() or any(output.iterdir()):
        raise ReleaseIdentityError("download output directory must exist and be empty")
    entries = package_index_entries(
        read_json_with_retry(package_index_url, max_attempts, retry_seconds), manifest
    )
    with tempfile.TemporaryDirectory(
        prefix="polis-release-download-", dir=output.parent
    ) as temporary:
        staging = Path(temporary)
        for artifact in manifest.artifacts:
            (staging / artifact.filename).write_bytes(
                read_with_retry(entries[artifact.filename], max_attempts, retry_seconds)
            )
        manifest.verify_artifacts(staging)
        for artifact in manifest.artifacts:
            (staging / artifact.filename).replace(output / artifact.filename)


def package_index_entries(
    payload: JsonValue, manifest: ReleaseManifest
) -> dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("urls"), list):
        raise ReleaseIdentityError("package index returned an invalid schema")
    expected = {artifact.filename: artifact for artifact in manifest.artifacts}
    entries: dict[str, str] = {}
    for value in payload["urls"]:
        if not isinstance(value, dict):
            raise ReleaseIdentityError("package index returned an invalid schema")
        filename = value.get("filename")
        url = value.get("url")
        size = value.get("size")
        digests = value.get("digests")
        if (
            not isinstance(filename, str)
            or not isinstance(url, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or not isinstance(digests, dict)
            or not isinstance(digests.get("sha256"), str)
            or filename not in expected
            or filename in entries
        ):
            raise ReleaseIdentityError("package index returned an invalid file schema")
        artifact = expected[filename]
        if size != artifact.size or digests["sha256"] != artifact.sha256:
            raise ReleaseIdentityError(
                "package index file differs from release manifest"
            )
        entries[filename] = url
    if set(entries) != set(expected):
        raise ReleaseIdentityError(
            "package index file set differs from release manifest"
        )
    return entries


def read_json_with_retry(
    url: str, max_attempts: int, retry_seconds: float
) -> JsonValue:
    try:
        return parse_json_value(
            json.loads(read_with_retry(url, max_attempts, retry_seconds))
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReleaseIdentityError("package index returned invalid JSON") from error


def read_with_retry(url: str, max_attempts: int, retry_seconds: float) -> bytes:
    for attempt in range(max_attempts):
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
                if response.status != 200:
                    raise ReleaseIdentityError(
                        "download authority returned an unexpected status"
                    )
                raw = response.read()
        except HTTPError as error:
            failure = ReleaseIdentityError(
                f"download authority returned HTTP {error.code}"
            )
        except (TimeoutError, URLError):
            failure = ReleaseIdentityError("download authority request failed")
        else:
            if not isinstance(raw, bytes):
                raise ReleaseIdentityError("download authority returned non-byte data")
            return raw
        if attempt + 1 == max_attempts:
            raise failure
        time.sleep(retry_seconds)
    raise AssertionError("bounded download retry exhausted without a result")
