from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.release_identity_models import ReleaseIdentityError

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_HTTP_TIMEOUT_SECONDS = 10.0


def read_json(url: str) -> JsonValue:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            if response.status != 200:
                raise ReleaseIdentityError(
                    "release authority returned an unexpected status"
                )
            raw = response.read()
    except HTTPError as error:
        raise ReleaseIdentityError(
            f"release authority returned HTTP {error.code}"
        ) from error
    except (TimeoutError, URLError) as error:
        raise ReleaseIdentityError("release authority request failed") from error
    try:
        return parse_json_value(json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReleaseIdentityError("release authority returned invalid JSON") from error


def project_is_absent(package_index_url: str) -> bool:
    request = Request(package_index_url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            if response.status == 200:
                response.read()
                return False
            raise ReleaseIdentityError("package index returned an unexpected status")
    except HTTPError as error:
        if error.code == 404:
            return True
        raise ReleaseIdentityError(
            f"package index returned HTTP {error.code}"
        ) from error
    except (TimeoutError, URLError) as error:
        raise ReleaseIdentityError("package index request failed") from error


def parse_github_releases(payload: JsonValue) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ReleaseIdentityError("GitHub releases returned an invalid schema")
    tags: list[str] = []
    for release in payload:
        if not isinstance(release, dict):
            raise ReleaseIdentityError("GitHub releases returned an invalid schema")
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            raise ReleaseIdentityError("GitHub releases returned an invalid schema")
        tags.append(tag)
    return tuple(tags)


def parse_json_value(value: JsonValue) -> JsonValue:
    match value:
        case None | bool() | str() | int() | float():
            return value
        case list():
            return [parse_json_value(item) for item in value]
        case dict():
            if not all(isinstance(key, str) for key in value):
                raise ReleaseIdentityError("release authority returned invalid JSON")
            return {key: parse_json_value(item) for key, item in value.items()}
        case _:
            raise ReleaseIdentityError("release authority returned invalid JSON")
