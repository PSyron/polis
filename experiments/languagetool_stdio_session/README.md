# Persistent vendored LanguageTool session benchmark

This experiment runs the 69 independently reviewed corpus-v3 development
sentences through one analyzer and one vendored LanguageTool 6.8 stdio process.
It measures process reuse, repeatability, warm latency, throughput, Python and
Java RSS, swap growth, and open sockets. It does not open holdout data.
The closed configuration authenticates the exact checked-in runner, built JAR,
and canonical runtime-dependency set before starting the measurement. Runtime
override variables accepted by the general-purpose runner are rejected for this
qualification path.

Build the pinned local module first, then run:

```console
env -u POLIS_LT_MAIN_CLASS -u POLIS_LT_ARTIFACT \
  -u POLIS_LT_DEPENDENCIES -u JAVA_BIN \
  POLIS_LT_VENDOR_INTEGRATION=1 python -m \
  experiments.languagetool_stdio_session.run_benchmark \
  --config experiments/languagetool_stdio_session/config.json \
  --output experiments/languagetool_stdio_session/report.json
```

The report contains artifact hashes, case IDs, input character counts, and
hashes of normalized findings, never sentence text, visible corrections, or raw
LanguageTool responses.
