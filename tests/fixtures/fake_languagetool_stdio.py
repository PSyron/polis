from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from io import TextIOWrapper
from typing import cast


def _write(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _candidate_id(
    start: int,
    end: int,
    lemma: str,
    form: str,
    features: list[str],
    tags: list[str],
) -> str:
    signature = "\0".join((str(start), str(end), lemma, form, *features, *tags)).encode(
        "utf-8"
    )
    return "ltpl:" + hashlib.sha256(signature).hexdigest()


def _candidate(
    start: int,
    end: int,
    lemma: str,
    form: str,
    features: list[str],
    tags: list[str],
) -> dict[str, object]:
    normalized_features = sorted(set(features))
    normalized_tags = sorted(set(tags))
    return {
        "candidate_id": _candidate_id(
            start,
            end,
            lemma,
            form,
            normalized_features,
            normalized_tags,
        ),
        "start": start,
        "end": end,
        "lemma": lemma,
        "form": form,
        "features": normalized_features,
        "tags": normalized_tags,
    }


def main() -> None:
    # The stdio protocol is UTF-8 even when Windows inherits a legacy console codec.
    cast(TextIOWrapper, sys.stdin).reconfigure(encoding="utf-8")
    cast(TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
    request_sequence = 0
    for line in sys.stdin:
        request_sequence += 1
        request = json.loads(line)
        text = request["text"]
        if text == "__timeout__":
            time.sleep(2)
            continue
        if text == "__invalid_json__":
            sys.stdout.write("not-json\n")
            sys.stdout.flush()
            continue
        if text == "__array__":
            _write([])
            continue
        if text == "__oversized__":
            sys.stdout.write("x" * 1_048_577 + "\n")
            sys.stdout.flush()
            continue
        if text == "__exit__":
            return
        identity = {
            "process_id": os.getpid(),
            "request_sequence": request_sequence,
        }
        if text == "__double_response__":
            response = {
                **identity,
                "request_id": request.get("request_id"),
                "software": {"name": "LanguageTool", "version": "6.8"},
                "matches": [],
            }
            _write(response)
            _write(response)
            continue
        if request.get("operation") == "synthesize_context":
            results = []
            for span in request["spans"]:
                start = span["start"]
                end = span["end"]
                surface = text[start:end]
                candidates = [
                    _candidate(
                        start,
                        end,
                        surface,
                        surface,
                        ["inst", "m1", "sg", "subst"]
                        if surface == "Janem"
                        else ["m1", "nom", "sg", "subst"],
                        ["subst:sg:inst:m1"]
                        if surface == "Janem"
                        else ["subst:sg:nom:m1"],
                    )
                ]
                if surface == "Nowak":
                    candidates.append(
                        _candidate(
                            start,
                            end,
                            "Nowak",
                            "Nowakiem",
                            ["inst", "m1", "sg", "subst"],
                            ["subst:sg:inst:m1"],
                        )
                    )
                results.append(
                    {
                        "start": start,
                        "end": end,
                        "surface": surface,
                        "unsupported_reason": None,
                        "candidates": candidates,
                    }
                )
            _write(
                {
                    "request_id": request.get("request_id"),
                    "operation": "synthesize_context",
                    "language": "pl-PL",
                    "results": results,
                }
            )
            continue
        matches = []
        if text.startswith("Wiem że"):
            matches.append(
                {
                    "offset": 0,
                    "length": 7,
                    "replacements": [{"value": "Wiem, że"}],
                    "rule": {"id": "BRAK_PRZECINKA_ZE"},
                }
            )
        _write(
            {
                **identity,
                "request_id": request.get("request_id"),
                "software": {"name": "LanguageTool", "version": "6.8"},
                "matches": matches,
            }
        )


if __name__ == "__main__":
    main()
