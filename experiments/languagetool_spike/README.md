# Local LanguageTool 6.8 benchmark

This experiment evaluates the open-source Polish rules through LanguageTool's
local HTTP API. It never calls the public proofreading API and does not make
Java or LanguageTool a package dependency.

## Install and start

On macOS with Homebrew:

```bash
brew install languagetool
/opt/homebrew/opt/languagetool/bin/languagetool-server \
  --config /opt/homebrew/etc/languagetool/server.properties \
  --port 8081
```

The benchmark fixes `language=pl-PL`, so fastText language detection is not
required. The client accepts only numeric loopback addresses and uses an HTTP
opener with proxies disabled. Do not add `--public` or `--allow-origin`.
Confirm that the server is loopback-only:

```bash
lsof -nP -iTCP:8081 -sTCP:LISTEN
```

## Run

Warm the server with one Polish request, sample the Java process RSS in KiB,
measure cold startup on the target machine, then run. Replace the example
startup and RSS values with the measurements from that run:

```bash
uv run --locked --extra dev python -m \
  experiments.languagetool_spike.run_benchmark \
  --tool-version 6.8 \
  --startup-ms 1340.318 \
  --rss-kib 644880 \
  --output experiments/languagetool_spike/results.json
```

The generated report is ignored. It contains case identifiers, counts,
latencies, version metadata, and hashes, but no source text, corrected text, or
raw LanguageTool response. Run the live non-BMP offset regression with:

```bash
POLIS_LANGUAGETOOL_URL=http://127.0.0.1:8081 \
  uv run --locked --extra dev pytest \
  tests/test_languagetool_benchmark.py::test_local_languagetool_68_preserves_non_bmp_offsets
```

## Scoring interpretation

Exact edit metrics require the same category, Python code-point range,
original fragment, and proposed correction as the corpus. LanguageTool often
uses a wider replacement span for whitespace and punctuation, so the report
also records whether any offered replacements can produce the complete gold
output. These measurements must not be conflated.

`top_output_exact` is evaluation evidence only. The experiment does not make
LanguageTool suggestions eligible for automatic correction.
