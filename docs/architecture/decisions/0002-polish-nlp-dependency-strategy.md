# ADR-0002: Standard-library-first Polish NLP dependency strategy

- Status: Accepted
- Date: 2026-07-20
- Owner: Paweł Cyroń
- Issue: #2

## Context

Polis needs stable text offsets, high-precision deterministic checks, and later
support for Polish morphology while preserving offline analysis. Adding a Polish
NLP stack now could constrain licensing, supported platforms, package size, and
runtime operations before production rules define which linguistic annotations
they actually need.

The reproducible [dependency spike](../../../experiments/nlp_dependencies/README.md)
ran four strategies on the same ten project-authored positive and hard-negative
examples. It measured raw token and sentence spans, four lemma probes, three
spelling probes, installed file size, offline configuration, package metadata,
and operational boundaries.

## Decision

Adopt a standard-library-first deterministic NLP strategy. No third-party
deterministic NLP package becomes a required runtime dependency at M0.

This decision sets these boundaries:

- M1-01 will implement and test project-owned paragraph and sentence segmentation
  with half-open offsets. The spike baseline is evidence only and must not be
  copied into production unchanged.
- Initial spelling work will use narrowly justified, project-owned deterministic
  rules. A generic unknown-word result is not sufficient for a user-facing
  suggestion.
- Morphology-dependent production rules must consume an explicit injected
  interface. They may return no finding when the required evidence is unavailable.
  Do not create an unused abstraction before such a rule exists.
- Morfeusz2 is the first candidate to reevaluate when a concrete rule requires
  morphology: it is offline, its program and included linguistic data are
  BSD-2-Clause, it satisfied all four bounded lemma probes, and its measured
  installed footprint was 40,793,559 bytes.
- Any Morfeusz2 adoption remains a separate issue. It must verify the supported
  CI matrix, ambiguity/offset mapping, required notices, dependency closure, and
  quality on the versioned evaluation set.
- No local LLM, model, or model-serving backend is selected by this decision.

The experiment-only code and results remain under `experiments/`; they are not a
runtime module or production API.

## Evidence summary

| Strategy | Installed bytes | Token cases | Sentence cases | Lemma probes | Direct spelling support |
| --- | ---: | ---: | ---: | ---: | --- |
| Standard library | 0 | 3/4 | 9/10 | 0/4 | No |
| Standard library + Morfeusz2 1.99.15 | 40,793,559 | 3/4 | 9/10 | 4/4 | No; unknown-form signal only |
| spaCy 3.8.14 + Polish model 3.8.0 | 111,473,931 | 2/4 | 10/10 | 4/4 | No |
| Stanza 1.14.0 Polish `default_fast` | 757,336,144 | 3/4 | 10/10 | 4/4 | No |

The ten cases are diagnostic, not a quality benchmark. Token differences can
represent valid policy choices, so the table supports architecture cost and
capability analysis rather than a universal ranking.

## Rejected alternatives

### Require Morfeusz2 now

Rejected as premature. It supplies strong Polish morphological analyses under an
allowed license, but no sentence segmenter or correction-grade spelling API. The
current wheel set omits Linux arm64 and publishes no source distribution, and
the package metadata declares no Python range. A 40.8 MB native/data dependency
is justified only when a production rule demonstrates the need.

### Require spaCy and `pl_core_news_sm`

Rejected. The stack measured 111.5 MB, has no spelling component, and imposes a
trained model/version pairing. More importantly, the Polish model release states
“GNU GPL 3.0,” which is outside ADR-0001's default dependency allowlist; the
release does not make the exact SPDX `-only` versus `-or-later` form verifiable.
The clean isolated install also required an unplanned explicit `click` repair
before import, which increases operational risk.

### Require Stanza Polish resources

Rejected. The minimized `default_fast` closure and models measured 757.3 MB and
include PyTorch plus separately downloaded model assets. The package is
Apache-2.0, but Stanza publishes its language packs under ODC-By-1.0 to the
extent it owns the rights; that term is outside ADR-0001's default allowlist.
The tested processors do not include spelling support.

### Select a general spelling dictionary now

Rejected because none was needed to resolve the minimum runtime strategy, and a
responsible comparison would add separate dictionary provenance, redistribution,
correction-ranking, proper-name, and false-positive evaluation work. M1-03 must
prefer no suggestion over an unjustified dictionary guess and can open a focused
dependency evaluation if project-owned high-precision rules prove insufficient.

## Consequences

- The default runtime remains small, offline, pure Python, and aligned with the
  ADR-0001 platform policy.
- Initial segmentation and spelling behavior is fully project-controlled and
  requires direct offset and false-positive tests.
- General morphology and broad spelling coverage are intentionally deferred; the
  system must not claim those capabilities until production implementations and
  evaluation evidence exist.
- Future optional adapters may have narrower platform support, but the core must
  not depend on them.
- Package and model licenses are assessed separately. An allowed code license
  does not make a model or dictionary automatically acceptable.

## Reevaluation triggers

Open a focused decision issue when at least one of these becomes true:

- a production agreement, inflection, or syntax rule cannot reach its measured
  precision target without morphological analysis;
- project-owned spelling rules miss a documented class of errors and a licensed
  dictionary candidate can be tested against representative hard negatives;
- Morfeusz2 publishes and passes the full required Python/platform matrix, or a
  smaller permissively licensed alternative becomes available;
- a candidate changes its code, model, dictionary, or redistribution terms;
- a representative evaluation set demonstrates that standard-library
  segmentation cannot meet the offset and boundary requirements economically.

Reevaluation must use the then-current package metadata, exact asset revisions,
license review, isolated offline runs, and the project's versioned evaluation
data. The ten spike cases are retained as regressions, not as acceptance gates.

## Verification

Run:

```bash
python3 experiments/nlp_dependencies/run_comparison.py \
  --validate --results experiments/nlp_dependencies/results.json
python3 experiments/nlp_dependencies/run_comparison.py --verify-assembly
python3 -m unittest tests/test_nlp_dependency_evaluation.py -v
```

The first command validates shared case identity, derived scores, and offsets.
The second verifies raw hashes and byte-for-byte reconstruction of the report,
including environment, install, and model metadata. The third validates the
manifest, assembly contract, accepted decision boundary, and architecture index.

## References

- [Experiment method and results](../../../experiments/nlp_dependencies/README.md)
- [ADR-0001 licensing and platform policy](0001-python-platform-licensing-policy.md)
- [Morfeusz2 1.99.15 metadata](https://pypi.org/pypi/morfeusz2/1.99.15/json)
- [Morfeusz2 license](https://morfeusz.sgjp.pl/doc/license/en)
- [spaCy 3.8.14 metadata](https://pypi.org/pypi/spacy/3.8.14/json)
- [spaCy Polish model 3.8.0 release](https://github.com/explosion/spacy-models/releases/tag/pl_core_news_sm-3.8.0)
- [Stanza 1.14.0 metadata](https://pypi.org/pypi/stanza/1.14.0/json)
- [Stanza processor reference](https://stanfordnlp.github.io/stanza/pipeline.html)
- [Stanza language-pack license statement](https://stanfordnlp.github.io/stanza/performance.html)
