# Publiczny zbiór jakości v4

Zbiór `polis_v4_quality_development` jest publicznym, projektowym zbiorem
rozwojowym dla konserwatywnych reguł v1. Nie jest korpusem kalibracyjnym,
holdoutem ani raportem wyników. Etykiety i oczekiwane sugestie zostały opisane
przez autora projektu niezależnie od analizatora, modelu, sieci i Javy.

## Zakres

Artefakt zawiera 124 przypadki w pięciu kategoriach: agreement, inflection,
punctuation, spelling i syntax. Każda kategoria ma co najmniej osiem
oczekiwanych znalezisk, szesnaście kontrolowanych hard negative, co najmniej
trzy odrębne audytowane rodziny reguł lub zjawiska i co najmniej cztery
pary pozytyw/negatyw. Pary pokrywają wszystkie siedem wymaganych strat.
Każda kategoria jest obecna w siedmiu
stratach kształtu wejścia: `simple-local`, `sentence-internal`,
`multi-sentence`, `repeated-occurrence`, `unicode-and-case`,
`quotation-or-literal` oraz `conflict-or-abstention`.

Każde znalezisko ma półotwarty zakres `[start, end)`, zgodny z oryginalnym
tekstem, minimalną sugestię, uzasadnienie i dokładną rodzinę reguły `rule:*`.
Traceability każdego przypadku wiąże identyczne `source_identity`, `rule_family`
i `audit_row` z aktualnym `behavior_version` z publicznego audytu źródeł.
Nieznane, podstawione albo niespójne identyfikatory są odrzucane. Hard negative
musi wyjaśniać granicę językową, a para wskazuje oba identyfikatory oraz cechę,
która rozróżnia przypadki. Przypadki zależne od morfologii opisują osobno
zachowanie bez providera i po uzyskaniu kwalifikowanej zdolności.

## Proweniencja i wersjonowanie

Manifest wiąże zbiór z zaakceptowanym kontraktem pokrycia reguł z issue #364,
pełnym zestawem identyfikatorów po przeglądzie maintenera, skrótem treści oraz
osobnym skrótem manifestu. Wersje v1, v2 i v3 są niezmiennymi poprzednikami i
nie są przenoszone do v4. Manifest przechowuje również skróty bajtów v3, aby
walidacja wykrywała przypadkową zmianę wcześniejszych artefaktów.

### Korekta kontroli konfliktu (#376)

Kontrolka `v4_control_conflict_punctuation` używa projektu `Pada deszcz Anna
wraca.`. To celowo nieinterpunkcyjna granica dwóch niezależnych zdań. Bez
kontekstu dyskursowego obie następujące, normatywnie dopuszczalne interpunkcje
są uzasadnione:

- wstawienie kropki w offset `[11, 11)`: `Pada deszcz. Anna wraca.`;
- wstawienie średnika w offset `[11, 11)`: `Pada deszcz; Anna wraca.`.

Są to dwie minimalne insercje (pusty oryginał, brak niezmienionego kontekstu),
mają różne teksty końcowe i pozostają konfliktem według produkcyjnego
`findings_conflict`, ponieważ dzielą ten sam offset insercji. Żaden aktualny
runtime source nie rozstrzyga tej niejednoznaczności; traceability jawnie używa
projektowej tożsamości `project-authored:ambiguity.punctuation_boundary`, a nie
podszywa kandydatów pod niepasującą regułę. Walidator dopuszcza tę jedną
projektową tożsamość wyłącznie w kontrolce konfliktu, jako najmniejszą korektę
schematu zgodną z #364/#366.

Poprzednia wersja błędnie używała `Te dziecko śpi.`: druga sugestia była
nieminimalnym zakresem prowadzącym do tego samego tekstu, a analizator emitował
`rule:agreement.te_neuter_noun`. Zastąpienie kontrolki nie zmienia runtime'u
ani polityki korekt. Dla dokładnego nowego tekstu aktualny Analyzer zasadnie
abstenuje w profilu bez providera i z kwalifikowaną morfologią: wybór kropki lub
średnika wymaga niedostępnego kontekstu dyskursowego, którego v1 nie wnioskuje.

Po korekcie canonical digest zbioru to
`0a767850af7f5d37ccb8f4b63544dad91a7bd11744fe02b9652ebf33f644af5c`, a digest
manifestu to `120247819ff38ec45341b0ad44ea72d3a1015c19d48f7d0b8ab298a9329382bf`.
Digest listy przejrzanych identyfikatorów to
`0ca59077aa406d02128147b63a95116eec67f886c569129207a6b872d2ab7703`;
review obejmuje nadal wszystkie 124 przypadki. Wiązania bajtów v3 pozostają
bez zmian.

Konflikty i abstencje pozostają wynikami review-only. Zbiór nie zmienia
zachowania runtime'u i nie upoważnia do automatycznego wdrażania żadnej reguły.

## Kanoniczny pomiar i gate'y #367

Pomiar wykonano z czystego commita
`07cd485d9778c56d195f93da899917035a808a39` i jednego koła
`polis_nlp-0.2.0-py3-none-any.whl` o SHA-256
`7b8df55e83df14cfadf1cff974131a3030912346672e33bf3f4e0b0e6662e091`.
Oba profile używają Pythona 3.13.12 na Darwin arm64. Profil `default` dowodzi
braku `morfeusz2`; profil `morphology` wiąże kwalifikowany provider 1.99.15 i
zaakceptowaną tożsamość słownika.

Kanoniczne artefakty znajdują się w:

- `docs/quality-baseline-v4-default.json` i
  `docs/quality-baseline-v4-morphology.json`;
- `docs/quality-result-v4-default.json` i
  `docs/quality-result-v4-morphology.json`;
- `docs/runtime-performance-v2-v4-{reference,current}-{default,morphology}.json`;
- `docs/quality-threshold-proposal-v4.json`;
- `docs/quality-comparison-v4.json`.

W obu profilach precision, recall, F1, dokładność zakresu i dokładność sugestii
wynoszą `1.0`; false-alarm rate, naruszenia konfliktu i naruszenia abstencji
wynoszą `0`. Pięć mierzonych powtórzeń jest deterministycznych. Maintainer
zatwierdził proposal 2026-08-19 bez dodatkowego marginesu stabilności.

Gate'y izolowanej wydajności zachowują pełną precyzję surowego pomiaru; wartości
w nawiasach są prezentacją do trzech miejsc po przecinku:

| Profil | Maks. p95 | Min. throughput | Maks. incremental RSS |
|---|---:|---:|---:|
| default | 30 042 ns | 52 610.38294758326/s (52 610.383/s) | 147 456 B |
| morphology | 37 500 ns | 39 030.16339159529/s (39 030.163/s) | 114 688 B |

SHA-256 zatwierdzonej propozycji to
`24e83bb6013934184c87f3e27ad90f2f3e773b8ad5f2a6eb54dc15f0279166e7`, a
comparison — `b59a4fe78d5fa69fc18e00301809e52036f3f6ed343352eda5005fdefaaeb190`.
Comparison ma `aggregate_verdict: pass`; oba profile przechodzą wszystkie
gate'y. Wymuszenie tych gate'ów nie jest zgodą na zmianę reguł ani polityki
korekt. Zweryfikowane luki można teraz kwalifikować wyłącznie w zakresie #368.

## Walidacja

Walidator czyta wyłącznie publiczne pliki v4 i nie uruchamia sieci, modelu,
Javy, kalibracji ani holdoutu. Przekazanie techniczne do ponownego pomiaru #367
oraz późniejszej kwalifikacji #368 znajduje się w
[`quality-v4-368-handoff.md`](quality-v4-368-handoff.md): nie jest ono zgodą na
próg ani implementację reguły.

```bash
uv run --locked --extra dev python scripts/validate_quality_dataset_v4.py --json
```

Walidacja odrzuca między innymi duplikaty identyfikatorów, rozjazd skrótów,
niezgodne zakresy, nieoznaczone nakładanie znalezisk, niekompletne pary,
brakujące uzasadnienia hard negative, niepełną proweniencję i niespełnione
minima kategorii lub strat.

## Reprodukcja pomiaru

Pomiar wykonuj wyłącznie z jednego czystego commita i jednego zbudowanego
koła. Digest koła należy przekazać w `--artifact-sha256`, a digest commita w
`--source-sha` oraz `--source-repository`; `--source-sha` musi być dokładnym
HEAD-em czystego tracked tree wskazanego repozytorium/worktree (untracked
`.omo/` jest ignorowany). Nie wolno używać zerowego digestu ani artefaktu z brudnego
drzewa roboczego. Provider-absent i qualified-morphology są osobnymi
środowiskami. W pierwszym środowisku `morfeusz2` musi być nieimportowalny, a w
drugim musi odpowiadać kwalifikacji z manifestu.

```bash
uv run --locked --extra dev python scripts/validate_quality_dataset_v4.py --json
uv run --locked --extra dev python -m build --wheel --outdir /tmp/polis-367-dist
shasum -a 256 /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl

python -m venv /tmp/polis-367-default
/tmp/polis-367-default/bin/python -m pip install --no-deps /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl
/tmp/polis-367-default/bin/python -m polis.evaluation.quality_runner baseline \
  --dataset-version v4 --warmup 1 --repetitions 5 \
  --artifact-sha256 WHEEL_SHA256 --source-sha CLEAN_COMMIT_SHA \
  --source-repository /path/to/clean/polis-worktree \
  --wheel-path /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl \
  --profile default --output /tmp/polis-367-baseline-default.json

python -m venv /tmp/polis-367-morphology
/tmp/polis-367-morphology/bin/python -m pip install --no-deps /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl
/tmp/polis-367-morphology/bin/python -m pip install morfeusz2==1.99.15
/tmp/polis-367-morphology/bin/python -m polis.evaluation.quality_runner baseline \
  --dataset-version v4 --warmup 1 --repetitions 5 \
  --artifact-sha256 WHEEL_SHA256 --source-sha CLEAN_COMMIT_SHA \
  --source-repository /path/to/clean/polis-worktree \
  --wheel-path /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl \
  --profile morphology --output /tmp/polis-367-baseline-morphology.json
```

Po zmianie wykonaj dwa polecenia `result` z tymi samymi tożsamościami i
repetitions, używając `--artifact-sha256` digestu koła wynikowego. Następnie
utwórz propozycję wyłącznie z obu zmierzonych baseline'ów: jej początkowy
status to `pending_maintainer_approval`, `enforced: false`, a `decision: null`.
Walidacja propozycji nie jest zgodą. Maintainer musi dopisać jawne metadane
decyzji (`status: approved`, `enforced: true`, autor, czas i uzasadnienie),
a dopiero potem można uruchomić comparison:

```bash
/tmp/polis-367-default/bin/python -m polis.evaluation.quality_runner result \
  --dataset-version v4 --warmup 1 --repetitions 5 \
  --artifact-sha256 WHEEL_SHA256 --source-sha CLEAN_COMMIT_SHA \
  --wheel-path /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl \
  --profile default --output /tmp/polis-367-result-default.json
/tmp/polis-367-morphology/bin/python -m polis.evaluation.quality_runner result \
  --dataset-version v4 --warmup 1 --repetitions 5 \
  --artifact-sha256 WHEEL_SHA256 --source-sha CLEAN_COMMIT_SHA \
  --wheel-path /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl \
  --profile morphology --output /tmp/polis-367-result-morphology.json
python -m polis.evaluation.quality_runner propose \
  --baseline /tmp/polis-367-baseline-default.json \
  --morphology-baseline /tmp/polis-367-baseline-morphology.json \
  --wheel-filename polis_nlp-0.2.0-py3-none-any.whl \
  --wheel-path /tmp/polis-367-dist/polis_nlp-0.2.0-py3-none-any.whl \
  --protocol-sha256 PROTOCOL_FILE_SHA256 --worker-sha256 WORKER_FILE_SHA256 \
  --performance-default-reference /tmp/polis-367-performance/runtime-performance-v2-reference-default.json \
  --performance-default-reference-sha256 DEFAULT_REFERENCE_SHA256 \
  --performance-default-current /tmp/polis-367-performance/runtime-performance-v2-current-default.json \
  --performance-default-current-sha256 DEFAULT_CURRENT_SHA256 \
  --performance-morphology-reference /tmp/polis-367-performance/runtime-performance-v2-reference-morphology.json \
  --performance-morphology-reference-sha256 MORPH_REFERENCE_SHA256 \
  --performance-morphology-current /tmp/polis-367-performance/runtime-performance-v2-current-morphology.json \
  --performance-morphology-current-sha256 MORPH_CURRENT_SHA256 \
  --default-maximum-p95-latency-ns DEFAULT_P95_CAP \
  --default-minimum-throughput-cases-per-second DEFAULT_THROUGHPUT_FLOOR \
  --default-maximum-worker-incremental-peak-rss-bytes DEFAULT_RSS_CAP \
  --morphology-maximum-p95-latency-ns MORPH_P95_CAP \
  --morphology-minimum-throughput-cases-per-second MORPH_THROUGHPUT_FLOOR \
  --morphology-maximum-worker-incremental-peak-rss-bytes MORPH_RSS_CAP \
  --output /tmp/polis-367-proposal.json
python -m polis.evaluation.quality_runner validate-proposal \
  --baseline /tmp/polis-367-baseline-default.json \
  --morphology-baseline /tmp/polis-367-baseline-morphology.json \
  --proposal /tmp/polis-367-proposal.json
python -m polis.evaluation.quality_runner compare \
  --baseline-default /tmp/polis-367-baseline-default.json \
  --baseline-morphology /tmp/polis-367-baseline-morphology.json \
  --result-default /tmp/polis-367-result-default.json \
  --result-morphology /tmp/polis-367-result-morphology.json \
  --proposal /tmp/polis-367-proposal-approved.json \
  --output /tmp/polis-367-comparison.json
```

Najpierw zbuduj wheel z czystego SHA i zapisz jego digest (macOS: `shasum -a
256 dist/*.whl`). Dla obu ról (`reference`, `current`) uruchom izolowany
performance-v2, nie mieszaj jego metryk z pomiarem quality runnera:

```bash
python scripts/run_runtime_performance_v2.py \
  --role current --source-sha CLEAN_COMMIT_SHA \
  --source-repository /path/to/clean/polis-worktree \
  --wheel /path/to/polis_nlp.whl \
  --default-python /tmp/polis-367-default/bin/python \
  --morphology-python /tmp/polis-367-morphology/bin/python \
  --output-dir /tmp/polis-367-performance \
  --protocol-sha PROTOCOL_SHA256 --worker-sha WORKER_SHA256 \
  --dataset-version v4
```

Uruchom to samo polecenie dla roli `reference`. Każdy artefakt można
zweryfikować niezależnie po pomiarze:

```bash
python scripts/validate_runtime_performance_v2.py \
  --artifact /tmp/polis-367-performance/runtime-performance-v2-current-default.json \
  --profile default --role current \
  --source-sha CLEAN_COMMIT_SHA --wheel-sha256 WHEEL_SHA256 \
  --protocol-sha256 PROTOCOL_FILE_SHA256 --worker-sha256 WORKER_FILE_SHA256
```

Artefakt performance zawiera
ścieżkę i digest pliku, dataset/manifest/source/wheel/profile/provider, protokół
i workera, środowisko, pięć repetytcji, p95, throughput oraz przyrostowy RSS
workera. Proposal i comparison sprawdzają te pola oraz osobne artefakty
`reference` i `current` dla obu profili. `--protocol-overlay` jest niedozwolone
dla v4.

Comparison ponownie sprawdza digest zbioru i manifestu, ordered-59 source
snapshot, profil/provider, arithmetic countów, finite derived metrics,
category/shape floors, deterministyczną remeasurement oraz izolowany
performance v2 (p95, throughput i incremental RSS).
Wynik `pass` nie oznacza zgody na zmianę reguł. Po walidacji usuń tymczasowe
venv i pliki; nie publikuj prywatnego tekstu ani danych środowiska.
