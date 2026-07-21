# Role-correct specialist prompt benchmark

This experiment evaluates whether small local models can produce reviewable
Polish correction suggestions when system instructions, user data, schemas,
and specialist roles are separated. It never authorizes automatic correction.

## Protocol matrix

| CLI name | Contract | Calls per case |
| --- | --- | ---: |
| `finding` | Existing exact-span finding JSON v3.0 | 1 |
| `one_field` | One-field corrected-text JSON v1.0 | 1 |
| `specialist` | Category-specific corrected-text JSON v1.0 | 1 |
| `candidate` | Finite candidate-ID selection JSON v1.0; requires #58 generator | 1 |
| `proposal` | Specialist proposal followed by accept/reject verification | 1 when unchanged, otherwise 2 |

All contracts use separate system and user messages, deterministic generation,
delimited source text, strict response validation, and source-independent
prompt hashes. The implementation and schemas live in `protocols.py`,
`run_benchmark.py`, and `polis.llm.corrected_text`.

| Contract | Version | Prompt hash |
| --- | --- | --- |
| Finding | 3.0 | `761051727ebf2b958d3eadf5eab7f16f5d37dac616c6380dd56d186a8860545e` |
| Specialist inflection | 1.0 | `d0cceeb4c774bf7a3d269835dab0fab4546878212928bd1599a4cc47af6efc90` |
| Specialist syntax | 1.0 | `ea382408bfaf5c84f19723f7ce57c68218ae0eb2cf139bd9653536c239e68e93` |
| Specialist punctuation | 1.0 | `3dad8e72011fcce1cc95b7c9025e5109fd9aba322242f33ca8995552d1d792dd` |
| Candidate selection | 1.0 | `9fd9a8fef725ebea07f4e0255b36fc509d386f1520550e8ac59c8ac27ffa7f26` |
| Proposal verifier | 1.0 | `09278f05d67256846faa4e2900f37556095feea064a05c4070f5afb004c878f9` |

`one_field` uses the three Role-corrected specialist hashes shown above.
`specialist` uses the three specialist hashes, while `proposal` combines the
matching specialist hash with the verifier hash. Finding generation uses
`num_predict=512`; corrected-text, candidate, and verifier contracts use
`num_predict=384`. Every contract fixes `seed=42`, `temperature=0`, and
`top_p=0.95`. Ollama receives the model's official chat template through its
native `messages` API and the response schema through its native `format`
field.

## Reproduction

Prepare the model explicitly, start Ollama on loopback, and run development
before freezing or reading the holdout:

```bash
uv run python -m experiments.role_prompt_benchmark.run_benchmark \
  --engine ollama \
  --base-url http://127.0.0.1:11434 \
  --model qwen3:1.7b \
  --protocol all \
  --split development \
  --artifact-revision 8f68893c685c \
  --quantization ollama-default
```

After prompts are selected and the independently reviewed corpus is frozen,
run the selected protocol against holdout exactly once:

```bash
uv run python -m experiments.role_prompt_benchmark.run_benchmark \
  --engine ollama \
  --base-url http://127.0.0.1:11434 \
  --model qwen3:1.7b \
  --protocol specialist \
  --split holdout \
  --artifact-revision 8f68893c685c \
  --quantization ollama-default
```

Generated JSON reports stay outside the repository. Reports contain case IDs
and metrics, but never source text or raw model responses. All endpoints are
numeric loopback addresses; artifacts must already exist before offline runs.

## Results

Development used 80 cases through Ollama 0.20.7 on macOS 15.3.1, Apple M4 Mac
mini with 16 GB unified memory. Qwen3 1.7B (`8f68893c685c`) and Bielik 1.5B
Q8_0 (`9ab8e213bb88`) ran the corrected-text matrix. Bielik 4.5B Q8_0
(`ed35dfccf990`) was the larger quality control for the best corrected-text
protocol.

| Model / protocol | Valid | Negative changes | Edit P / R / F1 | Median / p95 | Calls | chars/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3 1.7B / finding | 80/80 | 0 | 0.000 / 0.000 / 0.000 | 448 / 477 ms | 1.000 | 87.2 |
| Qwen3 1.7B / one-field | 80/80 | 5 | 0.706 / 0.200 / 0.312 | 559 / 718 ms | 1.000 | 73.9 |
| Qwen3 1.7B / specialist | 80/80 | 6 | 0.700 / 0.233 / 0.350 | 547 / 749 ms | 1.000 | 72.4 |
| Qwen3 1.7B / proposal | 80/80 | 5 | 0.737 / 0.233 / 0.354 | 1,062 / 1,255 ms | 1.625 | 44.8 |
| Bielik 1.5B / specialist | 76/80 | 6 | 0.700 / 0.237 / 0.354 | 614 / 799 ms | 0.950 | 67.5 |
| Bielik 4.5B / specialist | 78/80 | 6 | 0.667 / 0.200 / 0.308 | 1,805 / 2,472 ms | 0.975 | 22.8 |

Schema validity is the `Valid` column and is reported independently of edit
quality. Post-load memory, read from Ollama `/api/ps` by the repaired runner,
was 2,355,771,424 bytes for Qwen3 1.7B, 2,145,648,640 bytes for Bielik 1.5B,
and 5,796,046,848 bytes for Bielik 4.5B. Memory depends on runtime context and
is a deployment measurement, not the on-disk artifact size.

The initial candidate diagnostic incorrectly derived finite options from gold
edits and is excluded from evidence. The runner now reports `unsupported`
without calling a model until #58 supplies an independent morphology generator.
This prevents evaluation answers from entering model input.

Qwen specialist punctuation was the only development slice to meet the
suggestion precision and validity gates: edit precision 1.000, recall 0.706,
and 17/17 valid responses. It was selected without prompt changes for the first
and only holdout run on frozen corpus SHA-256
`bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`.

The 160-case holdout run had 160/160 valid responses but changed nine protected
negatives. Overall edit precision was 0.727 and recall 0.200. Punctuation edit
precision was 0.889 with recall 0.421 and two false positives, below the 0.90
precision gate. No protocol qualifies for hybrid suggestions or automatic
correction. Holdout results were not used to edit prompts.

| Holdout stratum | Valid | Exact edits | Exact complete outputs |
| --- | ---: | ---: | ---: |
| Inflection | 40/40 | 0/40 (0.000) | 19/40 (0.475) |
| Syntax | 40/40 | 8/40 (0.200) | 16/40 (0.400) |
| Punctuation | 40/40 | 16/40 (0.400) | 16/40 (0.400) |
| Protected hard negatives | 40/40 | 31/40 (0.775) | 31/40 (0.775) |

The overall holdout exact-edit rate was 55/160 (0.344), and the complete-output
rate was 82/160 (0.512). Hard-negative exactness means that the input remained
unchanged; the nine misses are the nine unsafe changes reported above.
