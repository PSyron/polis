# Changelog

## Unreleased

### Dodano

- Dodano wąskie deterministyczne korekty dla rekcji po negacji, kierunku z
  `do`, początkowych zdań warunkowych, podwójnych przecinków, zapisu `napewno`
  i zamkniętego wzorca zgody `Te zdanie`.
- Dodano kwalifikację dostawcy morfologii offline i ograniczone reguły
  korzystające z morfologii. Zachowania bez dokładnej niezależnej kwalifikacji
  pozostają review-only i nie rozszerzają listy automatycznych korekt.
- Dodano edytowalny baseline jakości oraz narzędzia kalibracji i niezależnych
  zbiorów dla opcjonalnej ewaluacji, bez włączania danych badawczych do
  dystrybucji ani ścieżki wydania runtime'u.
- Dodano widoczny w runtime kontrakt tożsamości źródeł reguł i diagnostykę
  brakujących oraz nadmiarowych tożsamości.

### Zmieniono

- CLI respektuje domyślne kategorie i próg pewności wczytane z TOML, a jawne
  wartości wiersza poleceń nadal mają pierwszeństwo dla każdego pola osobno.
- Nieprawidłowe wartości skonfigurowanego progu pewności są odrzucane podczas
  tworzenia lub wczytywania konfiguracji zgodnie ze stabilnym publicznym
  kontraktem błędów.
- `Analyzer.correct()` kończy się kontrolowanym błędem w działającej pętli
  zdarzeń i kieruje kod asynchroniczny do `await Analyzer.correct_async(...)`,
  bez ostrzeżenia o coroutine pozbawionej `await`.
- Fast CI i weryfikacja dystrybucji ściślej sprawdzają wykonywalne polecenia
  workflow, zainstalowane moduły publiczne, instalację offline i wykluczenie
  materiałów dostępnych wyłącznie w repozytorium.

### Zmiany łamiące

- Usunięto `Analyzer.language_tool_process_start_count` z publicznego API;
  runtime v1 nie uruchamia procesu LanguageTool i nie udostępnia już tego
  historycznego licznika.

### Decyzja o wydaniu

- Następnym zamierzonym wydaniem runtime'u jest `0.3.0`. Przyrost minor zapisuje
  kompatybilne rozszerzenia wspieranego deterministycznego zestawu reguł i
  publicznych zachowań od `0.2.0`; nie jest to wyłącznie zestaw poprawek patch.
  Metadane źródłowe pozostają w wersji `0.2.0`, dopóki osobna zmiana wykonująca
  wydanie nie utworzy kandydata.
- Oczekująca propozycja progów jakości jest odroczona i niezależna od `0.3.0`.
  Nie jest wymuszana, nie kwalifikuje zachowań review-only do automatycznej
  korekty i nie stanowi bramki budowy, testów, pakowania ani publikacji tego
  wydania runtime'u.
- Opcjonalne badania, kwalifikacja morfologii, praca modelowa, kalibracja i
  holdouty pozostają poza krytyczną ścieżką runtime'u. Włączenie któregokolwiek
  z tych elementów do zależności wydania wymaga osobnej zaakceptowanej decyzji.

## 0.2.0 (2026-08-06)

- Added a build-once release-identity manifest, explicit publication checks, and
  immutable tagged release-evidence verification. Historical 0.1.0 evidence is
  restored to the tag; its published-asset digest correction is append-only.
- Completed both commas for the two narrowly reviewed relative-clause and
  parenthetical-vocative sentence shapes without broadening the qualified
  LanguageTool source channel.
- Added the #77 sentence-only vendored LanguageTool stdio mode, which reuses one
  persistent local process for qualified punctuation and reviewable contextual
  inflection. It has explicit lifecycle control, bounded privacy-safe failures,
  no network sockets, and no implicit artifact download.
- Added two deterministic, sentence-only residual syntax sources for three
  narrow missing-`się` and missing-`tym` constructions. They remain reviewable
  because the one-shot holdout contained no eligible examples and therefore
  could not qualify them for automatic correction.
- Added and benchmarked a closed two-pass diagnostic and evidence-bound
  Qwen3.5 2B protocol; rejected all three development variants for zero exact
  recall, with no frozen-holdout run or production backend activation.
- Added privacy-safe local benchmark evidence for prompt hashes, finite
  LanguageTool candidates, per-focus edit quality, call counts, latency,
  throughput, loaded memory, process RSS, and swap growth.
- Benchmarked a pinned Bielik 1.5B MLX QLoRA adapter on the 16 GB Apple Silicon
  target and rejected it after frozen holdout failures in response validity,
  protected-negative safety, and edit precision; adapter weights remain local.
- Added a deterministic CC0 Polish correction fine-tuning bundle with 1,200
  training and 240 validation records balanced across inflection, syntax,
  punctuation, and protected no-change examples.
- Added strict dataset, ChatML, provenance, minimal-edit, split-isolation, and
  corpus-v3 leakage validation plus reproducible statistics and file hashes.
- Added the rules-first hybrid suggestion policy with injected specialist task
  routing, finite-candidate selection, bounded corrected-text proposals, and an
  accept/reject verifier.
- Added equivalent synchronous and asynchronous correction paths, explicit
  optional-suggestion outcomes and call counts, and caller-selected application
  of reviewable suggestions.
- Model-derived edits remain suggestion-only regardless of confidence or
  verifier acceptance; no real specialist model is enabled by default.

## 0.1.0 (2026-07-20)

- Added release-focused reliability work before stable publication:
  - end-to-end Polish spelling/grammar/punctuation acceptance corpus and tests,
  - dedicated privacy and dependency audit evidence and tests,
  - distribution packaging/build/install validation utilities and documentation,
  - release-artifact verification checklist for M4.
- Confirmed that release artifacts contain the expected modules and metadata and
  pass clean installation smoke tests from both wheel and sdist.
- No runtime dependencies were introduced; production distribution remains
  dependency-light.

### Known limitations

- Model-assisted backend remains constrained to the repository’s selected local
  backend abstraction and mock path used for deterministic tests.
- Styling and broad linguistic rewriting are intentionally out of scope for this
  release.
- No DOCX/ODT/RTF adapters are included; use external tooling for document
  containers.

## 0.0.0

- Initial project scaffold and core offline analysis baseline.
