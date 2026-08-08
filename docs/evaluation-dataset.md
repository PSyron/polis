# Zbiory ewaluacyjne i aktywny protokół jakości

Polis rozdziela trzy zbiory o różnych rolach. Nie wolno ich łączyć ani
reinterpretować jako kolejnych wersji jednego korpusu.

## Niezmienne granice zgodności

`src/polis/evaluation/datasets/v1/cases.json` jest historycznym,
17-przypadkowym zbiorem zgodności. Utrzymuje importy `load_dataset` i
`validate_dataset` oraz dokładną powierzchnię `polis.evaluation.__all__` opisaną
w [ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md)
i [ADR-0023](architecture/decisions/0023-evaluation-namespace-1-0.md). Issue #229
nie zmienia jego treści, znaczenia ani roli.

`tests/fixtures/v1/conservative_corrections.json` jest niezależnym,
25-przypadkowym testem konserwatywnego zachowania runtime'u: obejmuje 12
przypadków `error`, 10 przypadków `correct` i 3 przypadki `abstain`. Fixture
pozostaje niezmienione i nie jest źródłem danych dla aktywnego protokołu ani
wejściem do wyznaczania jego progów.

Korpusy, wyniki i metodologia historycznych badań również pozostają
niezmienne. Ich lokalizacje opisuje
[manifest archiwum v2](project/v2-research-archive-manifest.md). Nie uruchamiaj
ponownie zużytych holdoutów i nie dostrajaj na podstawie zamrożonych dowodów.

## Kandydat do aktywnego zbioru jakości

Issue #229 wprowadziło osobny, edytowalny zbiór przypadków autorskich na
licencji `CC0-1.0`:

- dane: `src/polis/evaluation/datasets/quality/v1/cases.json`;
- manifest tożsamości i przeglądu:
  `src/polis/evaluation/datasets/quality/v1/manifest.json`.

Plik danych używa `schema_id` równemu
`polis.quality-development-dataset`, `schema_version` i `dataset_version`
równych `1`, identyfikatora `polis_v1_quality_development`, a także pól
`license`, `source` i `cases`. Każdy przypadek ma rolę w `kind`, jawne
`features`, opcjonalne `phenomenon` i `pair_id` oraz oczekiwane minimalne
znaleziska z półotwartymi zakresami `[start, end)`. Pary obejmują fleksję,
w tym zamkniętą konstrukcję rekcji po zaprzeczonym `widzieć`, rekcję, zgodę,
pisownię, składnię, w tym zamknięte konstrukcje celu podróży i początkowego
zdania warunkowego, oraz interpunkcję;
osobne rekordy opisują
konflikt nakładających się poprawek i sytuacje wymagające wstrzymania sugestii.

Manifest wiąże `dataset_id`, `dataset_version` i kanoniczny
`canonical_sha256` z kontraktem `polis.quality-development-manifest` w wersji
`1`. Sekcja `review` zapisuje `status`, `reviewer_role`, `checklist_version`,
`reviewed_case_ids` oraz ten sam `canonical_sha256`. Bieżący status to
`maintainer-reviewed`, a `reviewed_case_ids` zawiera wszystkie przypadki w
kolejności datasetu. Maintainer zatwierdził dokładnie ten 28-przypadkowy zestaw;
jego bieżący hash kanoniczny to
`152f7e23e5e56f299fc35e5acbb515515a855ee5925664e6b0a5179380984a2e`
i jest zapisany jednocześnie w danych i manifeście.
Rejestracja baseline'u może teraz rozpocząć się dla tego niezmienionego
zbioru.

## Definicje pomiarów

Protokół ocenia tylko niezmieniony `Analyzer(AnalyzerConfig())`. Dopasowanie
`true_positive` wymaga zgodności kategorii, zakresu, tekstu oryginalnego i
proponowanej korekty z jednym niewykorzystanym oczekiwanym znaleziskiem.
Niedopasowana predykcja jest `false_positive`, a niedopasowane oczekiwane
znalezisko — `false_negative`.

Metryki agregowane mają następujące definicje i mianowniki:

- `precision = TP / (TP + FP)`; bez predykcji wynik jest niezdefiniowany;
- `recall = TP / (TP + FN)`; bez oczekiwanych znalezisk wynik jest
  niezdefiniowany;
- `f1 = 2TP / (2TP + FP + FN)`; bez ocenianych edycji wynik jest
  niezdefiniowany;
- `span_accuracy = span_matches / expected_findings`, gdzie dopasowanie zakresu
  wymaga tej samej kategorii oraz dokładnego `[start, end)`; bez oczekiwanych
  znalezisk wynik jest niezdefiniowany;
- `correction_accuracy = correction_matches / span_matches`, gdzie licznik
  obejmuje dokładne dopasowania korekty; bez dopasowanego zakresu wynik jest
  niezdefiniowany;
- `false_alarm_rate = alarmed_correct_cases / correct_cases`; przypadek bez
  oczekiwanych znalezisk, w tym `correct` lub `abstain`, jest alarmowany, gdy
  analizator zwróci co najmniej jedno znalezisko. Bez takich przypadków wynik
  jest niezdefiniowany.

Raport zapisuje również czasy pojedynczych wywołań w nanosekundach
(`min`, całkowitą średnią, `p50`, `p95`, `max`) oraz przepustowość przypadków i
punktów kodowych Unicode na sekundę, wyliczoną z sumy zmierzonych czasów.
`peak_rss_bytes` pochodzi z `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`
w świeżym procesie: Darwin raportuje bajty bez przeliczenia, a Linux KiB,
które protokół mnoży przez 1024. Inna platforma kończy pomiar błędem zamiast
zgadywać jednostkę.

## Metoda baseline'u z zainstalowanego artefaktu

Baseline powstaje dopiero po przeglądzie danych i zamrożeniu zmian źródłowych.
Należy zbudować wheel do świeżego katalogu, obliczyć SHA-256 jego surowych
bajtów, zainstalować go bez indeksu w świeżym środowisku i uruchomić moduł ze
świeżego pustego katalogu roboczego. Aktywny zbiór zawierający przypadki
`rule:inflection.negated_widziec_nominal_group` i
`rule:agreement.nominal_group_te_duze_okno` oraz
`rule:agreement.subject_verb_oni_czyta` oraz
`rule:inflection.government_potrzebowac_pomoc` mierzy finalny wheel wraz z dokładnym
extra `morphology`; wheelhouse musi więc zawierać zarówno finalny wheel Polis,
jak i przypięte koło `morfeusz2==1.99.15`. Instalacja domyślna bez tego extra
pozostaje wspierana, lecz zgodnie z kontraktem tych reguł abstenuje i nie jest
środowiskiem pomiaru tego aktywnego baseline'u.

Przed pomiarem wyeksportuj z `uv.lock` wymagania dostawcy wraz z hashami:

```console
uv export --locked --extra morphology --no-dev --no-emit-project \
  --format requirements-txt \
  --output-file <morphology-requirements>
```

Następnie utwórz świeże środowisko i z pustego katalogu sprawdź, że Polis jest
ładowany z jego `site-packages`. Koło Polis instaluj osobno bez zależności, a
koło dostawcy wyłącznie z wheelhouse'u i z obowiązkową weryfikacją hashy z
wyeksportowanego pliku:

```console
python -m pip install --no-index --no-deps <wheelhouse>/<polis-wheel>
python -m pip install --no-index --find-links <wheelhouse> --require-hashes \
  --requirement <morphology-requirements>
```

Po instalacji uruchom runner tym samym interpreterem:

```console
python -m polis.evaluation.quality_runner baseline \
  --warmup 1 \
  --repetitions 5 \
  --artifact-sha256 <wheel-sha256> \
  --output <baseline-path>
```

Runner nie przyjmuje alternatywnego analizatora, konfiguracji, zbioru, reguły
ani progu. Każde powtórzenie przetwarza przypadki w stabilnej kolejności.
Raport przechowuje identyfikator i wersję pakietu, Pythona i platformy, hash
wheel, tożsamość zbioru i manifestu, `warmup_repetitions`,
`measured_repetitions`, `stable_repetitions` oraz `repetition_hashes`.
Wszystkie zmierzone powtórzenia muszą mieć ten sam hash tożsamości znalezisk.

Raport nie może zawierać analizowanego tekstu ani progów. Zapisuje tylko dane
potrzebne do audytu pomiaru, agregaty, liczniki, identyfikatory i hashe.

## Zarządzanie baseline'em i progami

Po prawdziwym przeglądzie maintainera obowiązuje sekwencja:

1. zarejestrowanie baseline'u z finalnego, zainstalowanego wheel;
2. utworzenie oczekującej propozycji związanej z SHA-256 surowych bajtów tego
   baseline'u i z hashem zbioru;
3. późniejsze zatwierdzenie przez maintainera w osobnej, jawnie autoryzowanej
   zmianie;
4. dopiero potem włączenie egzekwowania w kolejnej osobnej, autoryzowanej
   zmianie.

Aktualny baseline z issue #242 zachowuje niezmienione 28 przypadków i ich hashe,
mierzy 140 przypadków po jednym rozgrzewkowym i pięciu mierzonych przebiegach
oraz uzyskuje 10 TP, 4 FN i 0 FP. Precyzja i accuracy korekty wynoszą `1.0`,
recall oraz span accuracy `0.7142857142857143`, a F1 `0.8333333333333334`.
Oczekująca propozycja w `docs/quality-threshold-proposal-v1.json` pozostaje
związana byte-for-byte z tym baseline'em, ma
`status: pending_maintainer_approval` i `enforced: false`; nie jest bramką
jakości ani dowodem zatwierdzenia przypadków.
