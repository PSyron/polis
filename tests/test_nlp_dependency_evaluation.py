from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/nlp_dependencies"
CASES = EXPERIMENT / "cases.json"
RESULTS = EXPERIMENT / "results.json"
RUNNER = EXPERIMENT / "run_comparison.py"
ASSEMBLY = EXPERIMENT / "assembly.json"
RAW = EXPERIMENT / "raw"
CLOSURES = EXPERIMENT / "closures"
README = EXPERIMENT / "README.md"
ADR = ROOT / "docs/architecture/decisions/0002-polish-nlp-dependency-strategy.md"
INDEX = ROOT / "docs/architecture/README.md"
PLAN = ROOT / "docs/superpowers/plans/2026-07-20-issue-2-nlp-dependency-evaluation.md"


def load_json(path: Path) -> dict[str, Any]:
    raw_data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict) or not all(
        isinstance(key, str) for key in raw_data
    ):
        raise ValueError(f"expected JSON object with string keys: {path}")
    return cast(dict[str, Any], raw_data)


class NlpDependencyExperimentTests(unittest.TestCase):
    def test_byte_exact_experiment_inputs_force_lf_checkout(self) -> None:
        """Byte-verified inputs must not change when Git checks out on Windows."""
        metadata = load_json(ASSEMBLY)
        paths = [CASES, RESULTS]
        paths.extend(RAW / item["path"] for item in metadata["raw_inputs"].values())
        paths.extend(
            CLOSURES / item["closure"]["path"] for item in metadata["candidates"]
        )
        relative_paths = [str(path.relative_to(ROOT)) for path in paths]
        completed = subprocess.run(
            ["git", "check-attr", "-z", "eol", "--", *relative_paths],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            os.fsdecode(completed.stderr),
        )
        fields = completed.stdout.split(b"\0")
        self.assertEqual(fields.pop(), b"")
        self.assertEqual(len(fields) % 3, 0, fields)
        reported = {
            (os.fsdecode(path), os.fsdecode(attribute)): os.fsdecode(value)
            for path, attribute, value in zip(
                fields[::3], fields[1::3], fields[2::3], strict=True
            )
        }
        self.assertEqual(
            reported,
            {(path, "eol"): "lf" for path in relative_paths},
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn(b"\r\n", path.read_bytes())

    def test_case_manifest_has_shared_licensed_positive_and_hard_negative_data(
        self,
    ) -> None:
        manifest = load_json(CASES)
        self.assertEqual(manifest["schema_version"], 1)
        provenance = manifest["provenance"]
        self.assertEqual(provenance["license"], "CC0-1.0")
        self.assertEqual(provenance["source"], "project-authored synthetic examples")

        cases = manifest["cases"]
        self.assertGreaterEqual(len(cases), 8)
        kinds = {case["kind"] for case in cases}
        self.assertEqual(kinds, {"positive", "hard_negative"})
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))

        capabilities = {
            capability for case in cases for capability in case["capabilities"]
        }
        self.assertEqual(
            capabilities,
            {"tokenization", "sentence_segmentation", "morphology", "spelling"},
        )

    def test_results_compare_every_candidate_on_the_same_cases(self) -> None:
        manifest = load_json(CASES)
        results = load_json(RESULTS)
        case_ids = [case["id"] for case in manifest["cases"]]

        self.assertEqual(results["schema_version"], 1)
        self.assertEqual(results["case_manifest"], "cases.json")
        self.assertGreaterEqual(len(results["candidates"]), 2)
        for candidate in results["candidates"]:
            with self.subTest(candidate=candidate["id"]):
                self.assertEqual(
                    [
                        observation["case_id"]
                        for observation in candidate["observations"]
                    ],
                    case_ids,
                )
                self.assertTrue(candidate["version"])
                self.assertTrue(candidate["license"]["spdx"])
                self.assertTrue(
                    candidate["license"]["evidence_url"].startswith("https://")
                )
                self.assertTrue(
                    candidate["package_metadata_url"].startswith("https://")
                )
                self.assertIn(candidate["offline_after_install"], (True, False))
                self.assertGreaterEqual(candidate["install_footprint"]["bytes"], 0)
                self.assertIn(
                    candidate["install_footprint"]["method"],
                    ("installed-files", "no-third-party-files"),
                )
                self.assertTrue(candidate["python_availability"])
                self.assertTrue(candidate["platform_availability"])
                self.assertTrue(candidate["operational_complexity"])
                self.assertTrue(candidate["limitations"])
                self.assertEqual(
                    set(candidate["derived"]),
                    {
                        "tokenization",
                        "sentence_segmentation",
                        "morphology",
                        "spelling",
                    },
                )
                for observation in candidate["observations"]:
                    self.assertEqual(
                        set(observation),
                        {
                            "case_id",
                            "tokens",
                            "sentences",
                            "morphology",
                            "spelling",
                            "score",
                        },
                    )

    def test_raw_offsets_map_back_to_original_text(self) -> None:
        manifest = load_json(CASES)
        texts = {case["id"]: case["text"] for case in manifest["cases"]}
        results = load_json(RESULTS)

        for candidate in results["candidates"]:
            for observation in candidate["observations"]:
                text = texts[observation["case_id"]]
                for field in ("tokens", "sentences"):
                    for span in observation[field]:
                        with self.subTest(
                            candidate=candidate["id"],
                            case=observation["case_id"],
                            field=field,
                            span=span,
                        ):
                            self.assertEqual(
                                text[span["start"] : span["end"]], span["text"]
                            )

    def test_results_record_exact_reproduction_environment(self) -> None:
        results = load_json(RESULTS)
        environment = results["environment"]
        required = (
            "recorded_at",
            "os",
            "architecture",
            "python",
            "installer",
            "network_policy",
        )
        for field in required:
            with self.subTest(field=field):
                self.assertTrue(environment[field])

        readme = README.read_text(encoding="utf-8")
        self.assertIn("## Exact commands", readme)
        self.assertIn("## Raw and derived measurements", readme)
        self.assertIn("## Limitations", readme)
        self.assertIn("## Evidence", readme)
        self.assertIn('UV_VERSION="0.11.2"', readme)
        self.assertIn('"$UV_EXE" python install 3.12.13', readme)
        self.assertIn('PYTHON_312="$("$UV_EXE" python find 3.12.13)"', readme)
        self.assertIn('"$UV_EXE" pip sync', readme)

    def test_runner_validates_committed_data_with_only_the_standard_library(
        self,
    ) -> None:
        completed = subprocess.run(
            [sys.executable, RUNNER, "--validate", "--results", RESULTS],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("validated", completed.stdout)

    def test_assembly_reproduces_committed_results_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assembled = Path(directory) / "results.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    RUNNER,
                    "--assemble",
                    "--metadata",
                    ASSEMBLY,
                    "--raw-dir",
                    RAW,
                    "--output",
                    assembled,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(assembled.read_bytes(), RESULTS.read_bytes())

    def test_assembly_rejects_raw_input_drift(self) -> None:
        metadata = load_json(ASSEMBLY)
        first_input = next(iter(metadata["raw_inputs"].values()))

        with tempfile.TemporaryDirectory() as directory:
            raw_dir = Path(directory)
            for raw_input in metadata["raw_inputs"].values():
                raw_path = RAW / raw_input["path"]
                (raw_dir / raw_input["path"]).write_bytes(raw_path.read_bytes())
            drifted = raw_dir / first_input["path"]
            drifted.write_bytes(drifted.read_bytes() + b"\n")

            completed = subprocess.run(
                [
                    sys.executable,
                    RUNNER,
                    "--assemble",
                    "--metadata",
                    ASSEMBLY,
                    "--raw-dir",
                    raw_dir,
                    "--output",
                    Path(directory) / "results.json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("hash mismatch", completed.stderr)

    def test_assembly_recomputes_scores_after_hash_verification(self) -> None:
        metadata = load_json(ASSEMBLY)
        candidate_id = "stdlib"
        raw_input = metadata["raw_inputs"][candidate_id]
        raw = load_json(RAW / raw_input["path"])
        raw["observations"][0]["score"]["token_exact"] = False
        raw_bytes = (json.dumps(raw, ensure_ascii=False, indent=2) + "\n").encode()

        with tempfile.TemporaryDirectory() as directory:
            raw_dir = Path(directory) / "raw"
            raw_dir.mkdir()
            for candidate in metadata["raw_inputs"].values():
                source = RAW / candidate["path"]
                (raw_dir / candidate["path"]).write_bytes(source.read_bytes())
            (raw_dir / raw_input["path"]).write_bytes(raw_bytes)

            drifted_metadata = copy.deepcopy(metadata)
            drifted_metadata["raw_inputs"][candidate_id]["sha256"] = hashlib.sha256(
                raw_bytes
            ).hexdigest()
            metadata_path = Path(directory) / "assembly.json"
            metadata_path.write_text(
                json.dumps(drifted_metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    RUNNER,
                    "--assemble",
                    "--metadata",
                    metadata_path,
                    "--raw-dir",
                    raw_dir,
                    "--output",
                    Path(directory) / "results.json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("score mismatch", completed.stderr)

    def test_verification_rejects_environment_install_and_model_metadata_drift(
        self,
    ) -> None:
        metadata = load_json(ASSEMBLY)
        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "environment": lambda value: value["environment"].__setitem__(
                "python", "CPython 0.0.0"
            ),
            "install": lambda value: value["candidates"][1][
                "install_footprint"
            ].__setitem__("bytes", 1),
            "model": lambda value: value["candidates"][3]["model_files"][0].__setitem__(
                "sha256", "0" * 64
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                drifted = copy.deepcopy(metadata)
                mutate(drifted)
                metadata_path = Path(directory) / "assembly.json"
                metadata_path.write_text(
                    json.dumps(drifted, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [
                        sys.executable,
                        RUNNER,
                        "--verify-assembly",
                        "--metadata",
                        metadata_path,
                        "--raw-dir",
                        RAW,
                        "--results",
                        RESULTS,
                    ],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("assembled results differ", completed.stderr)

    def test_assembly_verifies_exact_candidate_closure_files(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                RUNNER,
                "--verify-assembly",
                "--metadata",
                ASSEMBLY,
                "--raw-dir",
                RAW,
                "--closure-dir",
                CLOSURES,
                "--results",
                RESULTS,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_assembly_rejects_hashed_candidate_closure_drift(self) -> None:
        metadata = load_json(ASSEMBLY)
        candidate_index = 2
        candidate = metadata["candidates"][candidate_index]
        closure = candidate["closure"]
        original = (CLOSURES / closure["path"]).read_text(encoding="utf-8")
        mutations = {
            "added": original + "surprise==1.0.0\n",
            "missing": original.replace("click==8.4.2\n", ""),
            "version": original.replace("click==8.4.2", "click==8.4.1"),
        }

        for name, drifted_text in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                directory_path = Path(directory)
                closure_dir = directory_path / "closures"
                closure_dir.mkdir()
                for item in metadata["candidates"]:
                    source = CLOSURES / item["closure"]["path"]
                    (closure_dir / item["closure"]["path"]).write_bytes(
                        source.read_bytes()
                    )

                drifted_path = closure_dir / closure["path"]
                drifted_path.write_text(drifted_text, encoding="utf-8")
                drifted_metadata = copy.deepcopy(metadata)
                drifted_metadata["candidates"][candidate_index]["closure"]["sha256"] = (
                    hashlib.sha256(drifted_path.read_bytes()).hexdigest()
                )
                metadata_path = directory_path / "assembly.json"
                metadata_path.write_text(
                    json.dumps(drifted_metadata, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                completed = subprocess.run(
                    [
                        sys.executable,
                        RUNNER,
                        "--assemble",
                        "--metadata",
                        metadata_path,
                        "--raw-dir",
                        RAW,
                        "--closure-dir",
                        closure_dir,
                        "--output",
                        directory_path / "results.json",
                    ],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(
                    "installed distribution closure mismatch", completed.stderr
                )

    def test_stanza_model_urls_use_pinned_remote_paths_without_language_prefix(
        self,
    ) -> None:
        metadata = load_json(ASSEMBLY)
        stanza = next(
            candidate
            for candidate in metadata["candidates"]
            if candidate["id"] == "stanza-pl"
        )
        revision = stanza["model_revision"]
        model_base = (
            f"https://huggingface.co/{revision['model_repository']}/resolve/"
            f"{revision['model_commit']}/models"
        )

        model_files = [
            model_file
            for model_file in stanza["model_files"]
            if model_file["path"] != "resources.json"
        ]
        self.assertEqual(len(model_files), 5)
        for model_file in model_files:
            _language, separator, remote_path = model_file["path"].partition("/")
            self.assertEqual(separator, "/")
            with self.subTest(path=model_file["path"]):
                self.assertEqual(model_file["url"], f"{model_base}/{remote_path}")
                self.assertNotIn("/models/pl/", model_file["url"])

    def test_readme_evidence_pins_the_stanza_resource_manifest_commit(self) -> None:
        readme = README.read_text(encoding="utf-8")
        pinned_manifest_url = (
            "https://raw.githubusercontent.com/stanfordnlp/stanza-resources/"
            "f2976f2de7509a59c964c23fccbda2ec5d0852e3/resources_1.14.0.json"
        )
        self.assertIn(pinned_manifest_url, readme)
        self.assertNotIn(
            "stanfordnlp/stanza-resources/main/resources_1.14.0.json", readme
        )

    def test_accepted_adr_selects_only_a_standard_library_first_strategy(self) -> None:
        adr = ADR.read_text(encoding="utf-8")
        normalized_adr = " ".join(adr.split())
        required = (
            "Status: Accepted",
            "Adopt a standard-library-first deterministic NLP strategy.",
            "No third-party deterministic NLP package becomes a required "
            "runtime dependency",
            "No local LLM, model, or model-serving backend is selected by "
            "this decision.",
            "Reevaluation triggers",
            "Rejected alternatives",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, normalized_adr)

        index = INDEX.read_text(encoding="utf-8")
        self.assertIn(
            "| [ADR-0002](decisions/0002-polish-nlp-dependency-strategy.md) | "
            "Accepted | Standard-library-first Polish NLP dependency strategy |",
            index,
        )

    def test_plan_does_not_name_automated_workflows(self) -> None:
        plan = PLAN.read_text(encoding="utf-8")
        self.assertNotIn("superpowers:", plan)
        self.assertNotIn("agentic", plan.lower())


if __name__ == "__main__":
    unittest.main()
