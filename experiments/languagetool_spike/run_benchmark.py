"""Run the LanguageTool spike against a loopback-only 6.8 server."""

from __future__ import annotations

import argparse
import ipaddress
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode, urlparse
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from experiments.languagetool_spike.benchmark import (
    RuntimeConfig,
    corpus_sha256,
    load_cases,
    parse_response,
    report_as_json,
    score_case,
    summarize,
)

@dataclass(frozen=True, slots=True)
class LanguageToolClient:
    base_url: str
    timeout_seconds: float
    language: str = "pl-PL"

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("LanguageTool base URL must use HTTP")
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError as error:
            raise ValueError(
                "LanguageTool base URL must use a numeric loopback address"
            ) from error
        if not address.is_loopback:
            raise ValueError("LanguageTool base URL must use a loopback host")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.language != "pl-PL":
            raise ValueError("benchmark language must be pl-PL")

    def check(self, text: str) -> tuple[Mapping[str, object], float]:
        """POST one Polish text to the local `/v2/check` endpoint."""

        body = urlencode({"language": self.language, "text": text}).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/v2/check",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        started = time.perf_counter()
        with _no_proxy_opener().open(
            request, timeout=self.timeout_seconds
        ) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
        elapsed_ms = (time.perf_counter() - started) * 1_000
        payload: Any = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("LanguageTool response must be an object")
        return cast(Mapping[str, object], payload), elapsed_ms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8081")
    parser.add_argument("--tool-version", default="6.8")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/fixtures/e2e/polish_correction_corpus.json"),
    )
    parser.add_argument("--startup-ms", type=float)
    parser.add_argument("--rss-kib", type=int)
    parser.add_argument("--artifact", default="homebrew:languagetool@6.8")
    parser.add_argument(
        "--artifact-sha256",
        default="68783053c71a4a16dfc6a7fc977340ad4feaedbdfb92e606830003548ff00249",
    )
    parser.add_argument("--java-version", default="17.0.19")
    parser.add_argument(
        "--runtime-command",
        default="languagetool-server --config server.properties --port 8081",
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    client = LanguageToolClient(arguments.base_url, arguments.timeout_seconds)
    scores = []
    observed_versions: set[str] = set()
    for case in load_cases(arguments.corpus):
        payload, latency_ms = client.check(case.source)
        software = payload.get("software")
        if isinstance(software, dict) and isinstance(software.get("version"), str):
            observed_versions.add(software["version"])
        scores.append(
            score_case(case, parse_response(case.source, payload), latency_ms=latency_ms)
        )
    if observed_versions != {arguments.tool_version}:
        raise ValueError("server version does not match the pinned tool version")
    report = summarize(
        scores,
        tool_version=arguments.tool_version,
        corpus_sha256=corpus_sha256(arguments.corpus),
        startup_ms=arguments.startup_ms,
        rss_kib=arguments.rss_kib,
        runtime=RuntimeConfig(
            language="pl-PL",
            timeout_seconds=arguments.timeout_seconds,
            endpoint_policy="numeric-loopback-no-proxy",
            runtime_command=arguments.runtime_command,
            artifact=arguments.artifact,
            artifact_sha256=arguments.artifact_sha256,
            java_version=arguments.java_version,
        ),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(report_as_json(report), encoding="utf-8")
    return 0


def _no_proxy_opener() -> OpenerDirector:
    return build_opener(ProxyHandler({}))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LanguageToolClient", "main"]
