#!/usr/bin/env python3
"""Run or validate the bounded Polish NLP dependency experiment.

This is research tooling, not production segmentation or rule code. Candidate
imports are deliberately local so ``--validate`` needs only the standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

Span = dict[str, Any]
Observation = dict[str, Any]
TOKEN_RE = re.compile(
    r"\d+(?:[,.]\d+)+|[\wĄĆĘŁŃÓŚŹŻąćęłńóśźż]+(?:[-’'][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)*|[^\w\s]",
    re.UNICODE,
)
ABBREVIATIONS = {"dr.", "godz.", "mgr.", "prof.", "ul."}


def spans_from_matches(text: str) -> list[Span]:
    return [
        {"text": match.group(0), "start": match.start(), "end": match.end()}
        for match in TOKEN_RE.finditer(text)
    ]


def baseline_sentences(text: str) -> list[Span]:
    """Return transparent spike-only sentence spans for the comparison baseline."""
    boundaries: list[int] = []
    for match in re.finditer(r"[.!?]+(?:[”\"»])?", text):
        end = match.end()
        fragment = text[:end].rstrip().lower()
        last_word = fragment.rsplit(maxsplit=1)[-1]
        if last_word in ABBREVIATIONS:
            continue
        if (
            match.group(0) == "."
            and match.start() > 0
            and end < len(text)
            and text[match.start() - 1].isdigit()
            and text[end].isdigit()
        ):
            continue
        if end == len(text) or text[end:].startswith(" "):
            boundaries.append(end)

    spans: list[Span] = []
    start = 0
    for end in boundaries:
        while start < end and text[start].isspace():
            start += 1
        spans.append({"text": text[start:end], "start": start, "end": end})
        start = end
    if text[start:].strip():
        start += len(text[start:]) - len(text[start:].lstrip())
        spans.append({"text": text[start:], "start": start, "end": len(text)})
    return spans


def observe_stdlib(case: dict[str, Any], _: Path | None) -> Observation:
    return {
        "case_id": case["id"],
        "tokens": spans_from_matches(case["text"]),
        "sentences": baseline_sentences(case["text"]),
        "morphology": [],
        "spelling": {"supported": False, "flags": []},
    }


def observe_morfeusz(case: dict[str, Any], _: Path | None) -> Observation:
    import morfeusz2  # type: ignore[import-not-found]

    analyzer = morfeusz2.Morfeusz()
    tokens = spans_from_matches(case["text"])
    probe_surfaces = {
        probe["surface"].casefold() for probe in case.get("morphology_probes", [])
    }
    morphology: list[dict[str, Any]] = []
    flags: list[str] = []
    for token in tokens:
        if not token["text"].isalpha():
            continue
        analyses = []
        recognized = False
        for _start, _end, interpretation in analyzer.analyse(token["text"]):
            orth, lemma, tag, name, qualifiers = interpretation
            analyses.append(
                {
                    "surface": orth,
                    "lemma": lemma.split(":", maxsplit=1)[0],
                    "tag": tag,
                    "name": name,
                    "qualifiers": qualifiers,
                }
            )
            recognized = recognized or tag != "ign"
        if token["text"].casefold() in probe_surfaces:
            morphology.append({"text": token["text"], "analyses": analyses})
        if not recognized:
            flags.append(token["text"])
    return {
        "case_id": case["id"],
        "tokens": tokens,
        "sentences": baseline_sentences(case["text"]),
        "morphology": morphology,
        "spelling": {
            "supported": "lexicon-signal-only",
            "flags": flags,
        },
    }


class SpacyObserver:
    """Cache the optional spaCy pipeline while remaining explicitly callable."""

    def __init__(self) -> None:
        self.pipeline: Any | None = None

    def __call__(self, case: dict[str, Any], model_dir: Path | None) -> Observation:
        import spacy  # type: ignore[import-not-found]

        model_name = str(model_dir) if model_dir else "pl_core_news_sm"
        if self.pipeline is None:
            self.pipeline = spacy.load(model_name)
        doc = self.pipeline(case["text"])
        probe_surfaces = {
            probe["surface"].casefold() for probe in case.get("morphology_probes", [])
        }
        return {
            "case_id": case["id"],
            "tokens": [
                {
                    "text": token.text,
                    "start": token.idx,
                    "end": token.idx + len(token.text),
                }
                for token in doc
                if not token.is_space
            ],
            "sentences": [
                {
                    "text": sentence.text,
                    "start": sentence.start_char,
                    "end": sentence.end_char,
                }
                for sentence in doc.sents
            ],
            "morphology": [
                {
                    "text": token.text,
                    "lemma": token.lemma_,
                    "pos": token.pos_,
                    "features": str(token.morph),
                }
                for token in doc
                if not token.is_space and token.text.casefold() in probe_surfaces
            ],
            "spelling": {"supported": False, "flags": []},
        }


class StanzaObserver:
    """Cache the optional Stanza pipeline while remaining explicitly callable."""

    def __init__(self) -> None:
        self.pipeline: Any | None = None

    def __call__(self, case: dict[str, Any], model_dir: Path | None) -> Observation:
        import stanza  # type: ignore[import-not-found]

        if self.pipeline is None:
            kwargs: dict[str, Any] = {
                "lang": "pl",
                "processors": "tokenize,mwt,pos,lemma",
                "package": "default_fast",
                "download_method": None,
                "use_gpu": False,
                "verbose": False,
            }
            if model_dir:
                kwargs["dir"] = str(model_dir)
            self.pipeline = stanza.Pipeline(**kwargs)
        document = self.pipeline(case["text"])
        probe_surfaces = {
            probe["surface"].casefold() for probe in case.get("morphology_probes", [])
        }
        tokens: list[Span] = []
        sentences: list[Span] = []
        morphology: list[dict[str, Any]] = []
        for sentence in document.sentences:
            for token in sentence.tokens:
                tokens.append(
                    {
                        "text": token.text,
                        "start": token.start_char,
                        "end": token.end_char,
                    }
                )
                morphology.extend(
                    {
                        "text": word.text,
                        "lemma": word.lemma,
                        "pos": word.upos,
                        "features": word.feats or "",
                    }
                    for word in token.words
                    if word.text.casefold() in probe_surfaces
                )
            if sentence.tokens:
                start = sentence.tokens[0].start_char
                end = sentence.tokens[-1].end_char
                sentences.append(
                    {"text": case["text"][start:end], "start": start, "end": end}
                )
        return {
            "case_id": case["id"],
            "tokens": tokens,
            "sentences": sentences,
            "morphology": morphology,
            "spelling": {"supported": False, "flags": []},
        }


observe_spacy = SpacyObserver()
observe_stanza = StanzaObserver()


CANDIDATES: dict[
    str,
    tuple[Callable[[dict[str, Any], Path | None], Observation], str | None],
] = {
    "stdlib": (observe_stdlib, None),
    "stdlib-morfeusz2": (observe_morfeusz, "morfeusz2"),
    "spacy-pl": (observe_spacy, "spacy"),
    "stanza-pl": (observe_stanza, "stanza"),
}


def load_cases(path: Path) -> dict[str, Any]:
    raw_data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict) or not all(
        isinstance(key, str) for key in raw_data
    ):
        raise ValueError("case manifest must be a JSON object with string keys")
    data = cast(dict[str, Any], raw_data)
    if data.get("schema_version") != 1 or not data.get("cases"):
        raise ValueError("unsupported or empty case manifest")
    return data


def score(case: dict[str, Any], observation: Observation) -> dict[str, Any]:
    token_expected = case.get("expected_tokens")
    sentence_expected = case.get("expected_sentences")
    morphology_expected = case.get("morphology_probes", [])
    spelling_expected = case.get("expected_spelling_flags")

    observed_lemmas: set[tuple[str, str]] = set()
    for item in observation["morphology"]:
        if "analyses" in item:
            observed_lemmas.update(
                (item["text"].casefold(), analysis["lemma"].casefold())
                for analysis in item["analyses"]
            )
        elif item.get("lemma"):
            observed_lemmas.add((item["text"].casefold(), item["lemma"].casefold()))
    probe_hits = sum(
        (probe["surface"].casefold(), probe["lemma"].casefold()) in observed_lemmas
        for probe in morphology_expected
    )
    return {
        "token_exact": None
        if token_expected is None
        else [span["text"] for span in observation["tokens"]] == token_expected,
        "sentence_exact": None
        if sentence_expected is None
        else [span["text"] for span in observation["sentences"]] == sentence_expected,
        "morphology_probe_hits": probe_hits,
        "morphology_probe_total": len(morphology_expected),
        "spelling_exact": None
        if spelling_expected is None
        else [value.casefold() for value in observation["spelling"]["flags"]]
        == [value.casefold() for value in spelling_expected],
    }


def aggregate(observations: list[Observation]) -> dict[str, Any]:
    scores = [observation["score"] for observation in observations]

    def exact(field: str) -> dict[str, int]:
        values = [item[field] for item in scores if item[field] is not None]
        return {"exact_cases": sum(values), "evaluated_cases": len(values)}

    return {
        "tokenization": exact("token_exact"),
        "sentence_segmentation": exact("sentence_exact"),
        "morphology": {
            "probe_hits": sum(item["morphology_probe_hits"] for item in scores),
            "probe_total": sum(item["morphology_probe_total"] for item in scores),
        },
        "spelling": exact("spelling_exact"),
    }


def run(candidate_id: str, cases_path: Path, model_dir: Path | None) -> dict[str, Any]:
    manifest = load_cases(cases_path)
    observer, distribution = CANDIDATES[candidate_id]
    observations = []
    for case in manifest["cases"]:
        observation = observer(case, model_dir)
        observation["score"] = score(case, observation)
        observations.append(observation)
    return {
        "candidate": candidate_id,
        "distribution_version": (
            importlib.metadata.version(distribution)
            if distribution
            else sys.version.split()[0]
        ),
        "observations": observations,
    }


def validate_observations(
    manifest: dict[str, Any], candidate_id: str, observations: list[Observation]
) -> None:
    expected_ids = [case["id"] for case in manifest["cases"]]
    observed_ids = [item["case_id"] for item in observations]
    if observed_ids != expected_ids:
        raise ValueError(f"case mismatch for {candidate_id}")
    cases = {case["id"]: case for case in manifest["cases"]}
    for observation in observations:
        case = cases[observation["case_id"]]
        text = case["text"]
        expected_score = score(case, observation)
        if observation.get("score") != expected_score:
            raise ValueError(
                f"score mismatch for {candidate_id}:{observation['case_id']}"
            )
        for field in ("tokens", "sentences"):
            for span in observation[field]:
                if not 0 <= span["start"] <= span["end"] <= len(text):
                    raise ValueError(
                        f"invalid {field} range for "
                        f"{candidate_id}:{observation['case_id']}"
                    )
                if text[span["start"] : span["end"]] != span["text"]:
                    raise ValueError(
                        f"invalid {field} offset for "
                        f"{candidate_id}:{observation['case_id']}"
                    )


def validate(cases_path: Path, results_path: Path) -> None:
    manifest = load_cases(cases_path)
    results = json.loads(results_path.read_text(encoding="utf-8"))
    if results.get("schema_version") != 1:
        raise ValueError("unsupported results schema")
    if len(results.get("candidates", [])) < 2:
        raise ValueError("at least two candidates are required")
    for candidate in results["candidates"]:
        validate_observations(manifest, candidate["id"], candidate["observations"])
        if candidate.get("derived") != aggregate(candidate["observations"]):
            raise ValueError(f"derived score mismatch for {candidate['id']}")


def canonical_json(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def normalize_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_closure(path: Path) -> dict[str, str]:
    distributions: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if " @ " in line:
            name, url = line.split(" @ ", maxsplit=1)
            parsed_url = urlparse(url)
            if not parsed_url.fragment.startswith("sha256="):
                raise ValueError(
                    f"direct requirement lacks sha256 at {path}:{line_number}"
                )
            filename = Path(unquote(parsed_url.path)).name
            if not filename.endswith(".whl"):
                raise ValueError(
                    f"direct requirement is not a wheel at {path}:{line_number}"
                )
            wheel_parts = filename.removesuffix(".whl").split("-")
            if len(wheel_parts) < 5:
                raise ValueError(f"invalid wheel name at {path}:{line_number}")
            version = wheel_parts[1]
        elif "==" in line:
            name, version = line.split("==", maxsplit=1)
        else:
            raise ValueError(f"unpinned requirement at {path}:{line_number}")

        normalized_name = normalize_distribution(name.strip())
        if normalized_name in distributions:
            raise ValueError(f"duplicate distribution {normalized_name} in {path}")
        distributions[normalized_name] = version.strip()
    return distributions


def assemble(
    cases_path: Path,
    metadata_path: Path,
    raw_dir: Path,
    closure_dir: Path,
) -> bytes:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1:
        raise ValueError("unsupported assembly metadata schema")
    if metadata.get("case_manifest") != cases_path.name:
        raise ValueError("assembly case manifest mismatch")
    manifest_hash = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    if metadata.get("case_manifest_sha256") != manifest_hash:
        raise ValueError("case manifest hash mismatch")
    manifest = load_cases(cases_path)

    raw_inputs = metadata.get("raw_inputs", {})
    candidate_metadata = metadata.get("candidates", [])
    candidate_ids = [candidate["id"] for candidate in candidate_metadata]
    if candidate_ids != list(raw_inputs):
        raise ValueError("candidate metadata and raw input order mismatch")

    candidates = []
    for candidate in candidate_metadata:
        candidate_id = candidate["id"]
        closure = candidate["closure"]
        closure_path = closure_dir / closure["path"]
        closure_bytes = closure_path.read_bytes()
        if hashlib.sha256(closure_bytes).hexdigest() != closure["sha256"]:
            raise ValueError(f"closure hash mismatch for {candidate_id}")
        if parse_closure(closure_path) != closure["installed_distributions"]:
            raise ValueError(
                f"installed distribution closure mismatch for {candidate_id}"
            )

        raw_input = raw_inputs[candidate_id]
        raw_path = raw_dir / raw_input["path"]
        raw_bytes = raw_path.read_bytes()
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()
        if actual_hash != raw_input["sha256"]:
            raise ValueError(f"raw input hash mismatch for {candidate_id}")

        raw = json.loads(raw_bytes)
        if raw.get("candidate") != candidate_id:
            raise ValueError(f"raw candidate mismatch for {candidate_id}")
        if raw.get("distribution_version") != raw_input["distribution_version"]:
            raise ValueError(f"raw distribution version mismatch for {candidate_id}")
        observations = raw.get("observations")
        if not isinstance(observations, list):
            raise ValueError(f"raw observations missing for {candidate_id}")
        validate_observations(manifest, candidate_id, observations)

        assembled_candidate = dict(candidate)
        assembled_candidate["derived"] = aggregate(observations)
        assembled_candidate["observations"] = observations
        candidates.append(assembled_candidate)

    assembled = {
        "schema_version": metadata["schema_version"],
        "case_manifest": metadata["case_manifest"],
        "environment": metadata["environment"],
        "measurement_method": metadata["measurement_method"],
        "candidates": candidates,
    }
    return canonical_json(assembled)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("cases.json")
    )
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument(
        "--metadata", type=Path, default=Path(__file__).with_name("assembly.json")
    )
    parser.add_argument("--raw-dir", type=Path, default=Path(__file__).with_name("raw"))
    parser.add_argument(
        "--closure-dir", type=Path, default=Path(__file__).with_name("closures")
    )
    parser.add_argument(
        "--results", type=Path, default=Path(__file__).with_name("results.json")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--assemble", action="store_true")
    parser.add_argument("--verify-assembly", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.validate:
        validate(args.cases, args.results)
        print(f"validated {args.results}")
        return 0
    if args.assemble:
        if args.output is None:
            raise SystemExit("--assemble requires --output")
        args.output.write_bytes(
            assemble(args.cases, args.metadata, args.raw_dir, args.closure_dir)
        )
        print(f"assembled {args.output}")
        return 0
    if args.verify_assembly:
        assembled = assemble(args.cases, args.metadata, args.raw_dir, args.closure_dir)
        if assembled != args.results.read_bytes():
            raise ValueError(f"assembled results differ from {args.results}")
        print(
            f"verified {args.results} from "
            f"{len(json.loads(args.metadata.read_text())['raw_inputs'])} raw inputs"
        )
        return 0
    if args.candidate is None:
        raise SystemExit(
            "select --candidate, --validate, --assemble, or --verify-assembly"
        )
    json.dump(
        run(args.candidate, args.cases, args.model_dir),
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
