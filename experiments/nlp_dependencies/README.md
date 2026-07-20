# Polish deterministic NLP dependency spike

This bounded experiment supports issue #2. It compares four deterministic
strategies on one synthetic Polish case manifest without implementing production
segmentation or rules. The committed [cases](cases.json),
[runner](run_comparison.py), [assembly metadata](assembly.json),
[canonical raw outputs](raw/), and [results](results.json) are intentionally
small; candidate environments and model files remain external.

## Question and scope

The spike asks which minimum dependency strategy is justified before Polis has
production rules or a measured evaluation baseline. It covers tokenization,
sentence segmentation, morphology, spelling support, licensing, installation
footprint, offline operation, Python/platform availability, and operational
complexity. It does not evaluate correction quality, throughput, peak memory,
LLMs, model servers, or production-ready segmentation.

`positive` cases contain a straightforward target behavior, such as a known
inflection or misspelling. `hard_negative` cases are correct or ambiguous text
that commonly causes an unjustified split or spelling flag: abbreviations,
initials, decimal/time punctuation, quotations, rare words, and proper names.
All examples were written for this project and released as CC0-1.0.

## Candidates

1. CPython 3.12.13 standard library, using a transparent `re` baseline only.
2. The same baseline plus `morfeusz2==1.99.15` for SGJP morphology and an
   unknown-form spelling suspicion signal.
3. `spacy==3.8.14` with `pl_core_news_sm==3.8.0`.
4. `stanza==1.14.0` with its Polish `default_fast` tokenize, MWT, POS, and lemma
   resources from `resources_1.14.0.json`; the environment resolved
   `torch==2.13.0`.

These candidates expose different capability boundaries. The standard-library
and Morfeusz2 strategies share the same experiment-only tokenizer and sentence
splitter. spaCy and Stanza use their own trained segmentation and morphology.
Only the Morfeusz2 probe supplies even a lexical spelling signal; none of the
documented spaCy Polish components or Stanza processors is a spelling checker.
That statement is an inference from their official component lists, not a claim
that spelling could never be added through a third-party extension.

## Exact environment

- Host: Apple arm64, macOS 15.3.1, Darwin 24.3.0.
- Experiment interpreter: CPython 3.12.13 installed by `uv`.
- Installer: `uv 0.11.2`.
- Observation date: 2026-07-20, Europe/Warsaw.
- Network: enabled for package and model installation. Morfeusz2 and spaCy then
  require no network. Stanza inference used `download_method=None`; the host
  transport itself was not externally blocked, so this verifies configuration
  rather than a physical network-denial test.

## Exact commands

The commands below reproduce the isolated environments and raw observations from
the repository root. The temporary path prevents environments, caches, and model
weights from entering the repository.

```bash
SPIKE_DIR="$(mktemp -d /tmp/polis-issue2-nlp.XXXXXX)"
UV_VERSION="0.11.2"
UV_ARCHIVE="$SPIKE_DIR/uv-aarch64-apple-darwin.tar.gz"
curl --fail --location --output "$UV_ARCHIVE" \
  "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-apple-darwin.tar.gz"
test "$(LC_ALL=C shasum -a 256 "$UV_ARCHIVE")" = \
  "4beaa9550f93ef7f0fc02f7c28c9c48cd61fe30db00f5ac8947e0a425c3fb282  $UV_ARCHIVE"
tar -xzf "$UV_ARCHIVE" -C "$SPIKE_DIR"
UV_EXE="$SPIKE_DIR/uv-aarch64-apple-darwin/uv"
test "$("$UV_EXE" --version)" = \
  "uv $UV_VERSION (02036a8ba 2026-03-26 aarch64-apple-darwin)"

export UV_PYTHON_INSTALL_DIR="$SPIKE_DIR/python"
"$UV_EXE" python install 3.12.13
PYTHON_312="$("$UV_EXE" python find 3.12.13)"
test "$("$PYTHON_312" --version)" = "Python 3.12.13"
mkdir "$SPIKE_DIR/raw"

"$UV_EXE" venv --python "$PYTHON_312" "$SPIKE_DIR/stdlib-venv"
"$UV_EXE" pip sync --strict --allow-empty-requirements \
  --python "$SPIKE_DIR/stdlib-venv/bin/python" \
  experiments/nlp_dependencies/closures/stdlib.txt

"$UV_EXE" venv --python "$PYTHON_312" "$SPIKE_DIR/morfeusz-venv"
"$UV_EXE" pip sync --strict \
  --python "$SPIKE_DIR/morfeusz-venv/bin/python" \
  experiments/nlp_dependencies/closures/stdlib-morfeusz2.txt

"$UV_EXE" venv --python "$PYTHON_312" "$SPIKE_DIR/spacy-venv"
"$UV_EXE" pip sync --strict \
  --python "$SPIKE_DIR/spacy-venv/bin/python" \
  experiments/nlp_dependencies/closures/spacy-pl.txt

"$UV_EXE" venv --python "$PYTHON_312" "$SPIKE_DIR/stanza-venv"
"$UV_EXE" pip sync --strict \
  --python "$SPIKE_DIR/stanza-venv/bin/python" \
  experiments/nlp_dependencies/closures/stanza-pl.txt
STANZA_MODEL_DIR="$SPIKE_DIR/stanza-models" \
  "$SPIKE_DIR/stanza-venv/bin/python" - <<'PY'
import os

import stanza

stanza.download(
    "pl",
    model_dir=os.environ["STANZA_MODEL_DIR"],
    package="default_fast",
    processors="tokenize,pos,lemma",
    resources_url=(
        "https://raw.githubusercontent.com/stanfordnlp/stanza-resources/"
        "f2976f2de7509a59c964c23fccbda2ec5d0852e3"
    ),
    resources_version="1.14.0",
    model_url=(
        "https://huggingface.co/stanfordnlp/stanza-pl/resolve/"
        "731f2075c63dc52779dd07617e75aaa9ee178c20/models/{filename}"
    ),
    verbose=True,
)
PY

"$SPIKE_DIR/stdlib-venv/bin/python" \
  experiments/nlp_dependencies/run_comparison.py \
  --candidate stdlib > "$SPIKE_DIR/raw/stdlib.json"
"$SPIKE_DIR/morfeusz-venv/bin/python" \
  experiments/nlp_dependencies/run_comparison.py \
  --candidate stdlib-morfeusz2 > "$SPIKE_DIR/raw/stdlib-morfeusz2.json"
"$SPIKE_DIR/spacy-venv/bin/python" \
  experiments/nlp_dependencies/run_comparison.py \
  --candidate spacy-pl > "$SPIKE_DIR/raw/spacy-pl.json"
"$SPIKE_DIR/stanza-venv/bin/python" \
  experiments/nlp_dependencies/run_comparison.py \
  --candidate stanza-pl --model-dir "$SPIKE_DIR/stanza-models" \
  > "$SPIKE_DIR/raw/stanza-pl.json"

"$PYTHON_312" experiments/nlp_dependencies/run_comparison.py \
  --assemble \
  --metadata experiments/nlp_dependencies/assembly.json \
  --raw-dir "$SPIKE_DIR/raw" \
  --closure-dir experiments/nlp_dependencies/closures \
  --output "$SPIKE_DIR/results.json"
cmp "$SPIKE_DIR/results.json" experiments/nlp_dependencies/results.json
"$PYTHON_312" experiments/nlp_dependencies/run_comparison.py \
  --verify-assembly \
  --metadata experiments/nlp_dependencies/assembly.json \
  --raw-dir "$SPIKE_DIR/raw" \
  --closure-dir experiments/nlp_dependencies/closures \
  --results experiments/nlp_dependencies/results.json
```

The assembler verifies the case manifest and every fresh raw file against the
SHA-256 values recorded in `assembly.json`, checks each candidate's exact
installed-distribution closure against its hashed `closures/*.txt` file, checks
candidate identity and direct distribution version, recomputes every per-case
score and derived total, and inserts the recorded environment, install, license,
platform, limitation, and Stanza model metadata. `cmp` then proves that the
result is byte-for-byte identical to the committed report. The four canonical
raw files and all four closure files are committed so this standard-library
verification also runs without reinstalling candidates:

```bash
python3 experiments/nlp_dependencies/run_comparison.py --verify-assembly
```

To repeat the footprint method, sum `stat().st_size` for regular, non-symlink
files below each environment's `lib/python3.12/site-packages`; add the external
Stanza model directory. This is logical installed size, not compressed download
size, allocated disk blocks, or runtime memory. `assembly.json` is the canonical
record of these environment/install/model measurements; modifying any of them
causes byte comparison or `--verify-assembly` to fail.

After inspecting the raw files, remove the temporary directory by resolving and
checking that `SPIKE_DIR` starts with `/tmp/polis-issue2-nlp.` before deleting it.

## Raw and derived measurements

Canonical raw token and sentence spans use half-open offsets into the original
string. Morphology output is retained only for the four declared lemma probes,
keeping the artifact reviewable. `results.json` also contains all Stanza model
file sizes and SHA-256 hashes.

A second warm run of each candidate produced byte-identical raw JSON under the
recorded environment. This narrow repeat does not establish bitwise determinism
across Python versions, platforms, native libraries, or model revisions.

| Strategy | Installed bytes | Token exact | Sentence exact | Lemma probes | Spelling capability |
| --- | ---: | ---: | ---: | ---: | --- |
| Standard library | 0 | 3/4 | 9/10 | 0/4 | None; missed the typo |
| Standard library + Morfeusz2 | 40,793,559 | 3/4 | 9/10 | 4/4 | Unknown-form signal; 3/3 bounded probes |
| spaCy Polish | 111,473,931 | 2/4 | 10/10 | 4/4 | None; missed the typo |
| Stanza Polish `default_fast` | 757,336,144 | 3/4 | 10/10 | 4/4 | None; missed the typo |

The denominators include only cases with an explicit expectation for that
measurement. A spelling exact match for candidates without spelling support can
only mean they correctly emitted no flag on a negative case; it does not make
them spelling-capable.

Observed hard cases:

- The standard-library splitter and its Morfeusz2 extension treated `J.` as a
  sentence and two tokens. This confirms that the baseline cannot become
  production code unchanged.
- spaCy split `12.30` into three tokens and `e-mail` into three tokens; this is a
  policy difference, not proof that spaCy is linguistically wrong.
- Stanza split the initial `J.` into two tokens but kept the intended two
  sentences.
- All three morphology-capable candidates returned the expected lemmas for the
  four narrow probes.
- Morfeusz2 marked `rzodki` as unknown without flagging the two correct spelling
  negatives. The sample is far too small to treat unknown-form detection as a
  spell checker or set a quality threshold.

## Licensing and availability

| Strategy | Direct code/resource terms | Availability observed from current metadata |
| --- | --- | --- |
| Standard library | PSF-2.0 | Follows the supported CPython/platform policy |
| Morfeusz2 1.99.15 | Program and included linguistic data: BSD-2-Clause | macOS universal2, manylinux 2.28 x86_64, Windows amd64 wheels; no sdist or Linux arm64 wheel; `Requires-Python` absent |
| spaCy + Polish model | spaCy: MIT; model release: “GNU GPL 3.0” with exact SPDX suffix unstated | spaCy requires Python >=3.9,<3.15 and publishes platform wheels; model is a universal wheel |
| Stanza + Polish models | Stanza: Apache-2.0; language packs: ODC-By-1.0 to the extent Stanford owns the rights | Stanza requires Python >=3.9 and is a universal wheel; PyTorch controls practical platform coverage |

BSD-2-Clause, MIT, Apache-2.0, and PSF-2.0 are within ADR-0001's default
allowlist. The spaCy Polish model's GPL terms and Stanza pack's ODC-By-1.0 terms
are not. This spike did not perform a complete transitive-license audit, and it
does not guess whether the model's unspecified GPL 3.0 form is `-only` or
`-or-later`.

## Limitations

- Ten synthetic cases are diagnostic examples, not a representative corpus or
  quality benchmark. Exact ratios must not become release gates.
- The tested platform/interpreter is macOS arm64 with CPython 3.12.13. Metadata
  review is not a substitute for the ADR-0001 CI matrix on 3.12–3.14.
- Runs measured installed file bytes, not download transfer, latency, throughput,
  peak memory, warm-up, or model accuracy on licensed evaluation data.
- Candidate versions were current on the observation date and will age. A future
  adoption issue must regenerate the candidate closure with `uv 0.11.2`, record
  every changed distribution or resource revision, and re-audit it.
- The spaCy behavioral result includes the explicit `click==8.4.2` repair after
  the clean resolver output passed `uv pip check` but failed at import.
- No candidate was physically sandboxed from the network during inference.
- Morfeusz2's unknown-word result cannot provide a correction, distinguish all
  proper names, or justify a user-facing suggestion by itself.

## Evidence

- [Python standard-library reference](https://docs.python.org/3.12/library/index.html)
- [uv release 0.11.2](https://github.com/astral-sh/uv/releases/tag/0.11.2)
- [Morfeusz2 package metadata 1.99.15](https://pypi.org/pypi/morfeusz2/1.99.15/json)
- [Morfeusz2 official license](https://morfeusz.sgjp.pl/doc/license/en)
- [Morfeusz2 official project description](https://morfeusz.sgjp.pl/)
- [spaCy package metadata 3.8.14](https://pypi.org/pypi/spacy/3.8.14/json)
- [spaCy Polish pipeline release 3.8.0](https://github.com/explosion/spacy-models/releases/tag/pl_core_news_sm-3.8.0)
- [spaCy Polish model documentation](https://spacy.io/models/pl)
- [Stanza package metadata 1.14.0](https://pypi.org/pypi/stanza/1.14.0/json)
- [Stanza processors](https://stanfordnlp.github.io/stanza/pipeline.html)
- [Stanza offline model loading](https://stanfordnlp.github.io/stanza/getting_started.html#downloading-models-for-offline-usage)
- [Stanza language-pack license statement](https://stanfordnlp.github.io/stanza/performance.html)
- [Stanza 1.14.0 resource manifest](https://raw.githubusercontent.com/stanfordnlp/stanza-resources/f2976f2de7509a59c964c23fccbda2ec5d0852e3/resources_1.14.0.json)
