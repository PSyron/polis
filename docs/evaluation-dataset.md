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

## Zbiór deweloperski jakości v2

Issue #303 dodaje odrębny, nadal edytowalny zbiór CC0 służący wyłącznie do
rozwoju ośmiu planowanych źródeł:

- dane: `src/polis/evaluation/datasets/quality/v2/cases.json`;
- manifest: `src/polis/evaluation/datasets/quality/v2/manifest.json`.

Pierwsze 28 obiektów przypadków stanowi dokładne przeniesienie zatwierdzonych
przypadków v1. Manifest wiąże ich identyfikatory, tożsamość
`polis_v1_quality_development@1`, licencję `CC0-1.0` oraz kanoniczny SHA-256
v1. Pliki v1 nie są zmieniane ani reinterpretowane.

Zbiór v2 dodaje po osiem ręcznie przejrzanych przypadków dla każdego źródła
zaplanowanego w ADR-0025: błąd, poprawioną parę, wzmiankę w cytacie, wzmiankę
podobną do kodu, negatywny podciąg lub leksem, negatywny tekst wielozdaniowy,
powtórzone wystąpienie oraz przypadek Unicode z kontrolą wielkości liter i
offsetu. Razem daje to 64 nowe przypadki i 92 przypadki ogółem. Manifest v2
wiąże każdą klasę dowodu z jednym stabilnym identyfikatorem, dokładną planowaną
tożsamością źródła, kohortą `polis-runtime-source-cohort-28-v1`, ADR-0025 i
stanem `review-only`. Nie jest to holdout, kwalifikacja automatyczna ani dowód,
że planowane źródła są już obecne w runtime.

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

Po instalacji uruchom runner tym samym interpreterem. Historyczny pomiar v1
wybiera zbiór jawnie:

```console
python -m polis.evaluation.quality_runner baseline \
  --dataset-version v1 \
  --warmup 1 \
  --repetitions 5 \
  --artifact-sha256 <wheel-sha256> \
  --output <baseline-path>
```

Baseline v2 mierzy bieżący snapshot repozytorium, który wprowadza zbiór v2 i
obsługę jego wyboru w runnerze, przed implementacją któregokolwiek z ośmiu
źródeł runtime'u zaplanowanych w ADR-0025. Nie jest to pomiar commita
`0840e1e432f4962f74b2535fc00fa84553617131`, ponieważ nie zawiera on tych
źródeł pomiaru.

Gdy zmiany issue nie są jeszcze commitowane, snapshot pomiarowy należy zapisać
jako efemeryczny obiekt commit utworzony przez `git commit-tree` z tymczasowego
indeksu obejmującego dokładne mierzone pliki. Operacja nie może aktualizować
gałęzi, tagu ani innej referencji. Wheel buduje się z czystego drzewa
wyeksportowanego z tego obiektu, a jego 40-znakowy SHA zapisuje się jako
`source.git_sha`. Tożsamość można sprawdzić przez `git show <source-git-sha>` i
odtworzyć wheel z tego samego drzewa.

Z jednego tak zbudowanego koła baseline powstaje dwukrotnie: raz w środowisku
instalacji domyślnej bez `morfeusz2`, a raz w osobnym środowisku `morphology` z
`morfeusz2==1.99.15`. Oba pomiary wykonują jedno rozgrzanie i pięć powtórzeń:

```console
python -m polis.evaluation.quality_runner baseline \
  --dataset-version v2 \
  --profile <default|morphology> \
  --source-sha <source-git-sha> \
  --warmup 1 \
  --repetitions 5 \
  --artifact-sha256 <wheel-sha256> \
  --output <baseline-v2-path>
```

Profil `default` odrzuca środowisko, w którym znajduje się `morfeusz2`, i
zapisuje oczekiwane wstrzymanie dla czterech planowanych źródeł
morfologicznych. Profil `morphology` wymaga dokładnie zakwalifikowanej
tożsamości dostawcy: pakietu `1.99.15`, słownika
`pl.sgjp.sgjp-2026.06.01` i SHA-256 noty
`84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`.
Istniejący runtime rzeczywiście używa tego dostawcy przy swoich czterech
obecnych źródłach morfologicznych, ale osiem źródeł zaplanowanych przez
ADR-0025 nadal jest nieobecnych. Ich brak nie może zostać policzony jako
fikcyjny `true_positive`.

Raport v2 zapisuje SHA źródła, SHA koła, profil i ewentualną dokładną tożsamość
dostawcy, środowisko, hashe datasetu i manifestu, agregaty jakości, wydajność,
RSS oraz pięć stabilnych hashy powtórzeń. Nie przechowuje tekstów przypadków,
goldów, oryginałów, sugestii, danych osobowych ani prywatnych ścieżek. Progi i
reguły porównania należą dopiero do #304.

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

## Syntetyczny kontrakt kalibracji per dokładny klucz

Issue #267 dodaje powtarzalny, działający offline kontrakt kalibracji dla 20
dokładnych tożsamości polityki. Narzędzie wykonuje jedno powtórzenie
rozgrzewkowe i pięć mierzonych, wymaga identycznych skrótów znalezisk oraz
oblicza wynik niezależnie dla każdego klucza. Jedynym kandydatem jest jego
emitowana wartość `minimum_confidence`; brak pełnych dowodów daje `none`.

Ta powierzchnia jest wyłącznie repozytoryjna i nie należy do wheel ani sdist.
W checkout źródłowym ma postać:

```console
python -m polis.evaluation run-calibration \
  --config experiments/a-b-qualification-v2/config.json
```

Polecenie przyjmuje tylko `--config` i wymaga dokładnie pokazanej ścieżki
względnej oraz uruchomienia z katalogu głównego repozytorium. Nie pozwala
zastąpić datasetu, źródła, progu, liczby powtórzeń ani ścieżek wynikowych przez
argumenty CLI. Issue #269 zmaterializowało i zamroziło niezależny zbiór
kalibracyjny CC0 `polis-a-b-calibration-v2-v1` oraz rozłączny holdout CC0
`polis-a-b-holdout-v2-v1`. Kalibracja ma 1073 przypadki, w tym 273 błędne
i 800 poprawnych; holdout ma 530 przypadków, w tym 130 błędnych i 400
poprawnych. Odrębni autorzy, kustosze i recenzenci sprawdzili ręcznie 1073/1073
oraz 530/530 przypadków. Deterministyczny skan PII nie wykrył danych osobowych.

Siedem skończonych kluczy pełnego dopasowania ma po 1 albo 3 możliwe
powierzchnie błędne i pozostaje strukturalnie `insufficient_evidence`, bez
możliwości promocji. Pozostałe 13 kluczy zachowuje mianowniki 20+40
w kalibracji oraz 10+20 w holdoucie. Keyed overlap oracle sklasyfikował osobno
dokładnie 78 prerejestrowanych dopasowań exact skończonych powierzchni
kalibracji; wszystkie inne exact i wszystkie near wynoszą zero, a holdout nie
ma wyjątku.

Śledzone metadane w `experiments/a-b-qualification-v2/` wiążą skróty zbiorów,
pełne przeglądy, manifesty, raport overlap i dwie niezależne weryfikacje freeze.
Nie zawierają tekstu przypadków, goldów, sugestii, HMAC-ów ani klucza. Samo
zamrożenie nie uruchomiło kalibracji ani holdoutu, nie wybrało progów i nie
autoryzuje otwarcia holdoutu. Kalibracyjny plaintext jest przeznaczony wyłącznie
do późniejszej powtarzalnej kalibracji po osobnej autoryzacji; holdout pozostaje
zapieczętowany do odrębnego prerejestrowanego one-shotu.

Wynik `threshold-selection` jest jawnie niepodpisany i nieautoryzujący. Nie
promuje klucza do automatycznej korekty, nie zmienia polityki i nie dopuszcza
holdoutu. Podpisany wybór progów, prerejestracja i osobny one-shot wymagają
kolejnych, odrębnych issues.

## Prerejestracja jednorazowego holdoutu A+B

Eksperyment `polis-a-b-one-shot-v1` został dostarczony w trzech append-only pull
requestach. PR1 zamroził kod wykonawczy, konfigurację i metadane niezależnie
sprawdzonego zbioru CC0. PR1.1, przed ujawnieniem zbioru, skorygował wyłącznie
wiązanie autoryzacji do nowego, podpisanego komentarza o identyfikatorze
większym niż prerejestrowany watermark. Dopiero podpisane przez GitHub scalenie
PR1.1, odtwarzalny preflight i osobna zgoda powiązana z SHA dopuściły jedną
próbę. PR2 publikuje wyłącznie niezmienne dowody konsumpcji i agregatowy wynik.

Nowy runner nie zmienia zgodności publicznego modułu `polis.evaluation`,
opisanej przez ADR-0019, ani granic zapisanych w manifeście archiwum v2.
Funkcje `load_dataset` i `validate_dataset` zachowują dotychczasowe znaczenie.

Runner sprawdza konfigurację, dokładne 20 tożsamości źródeł, skróty datasetu i
status podpisu przed utworzeniem markera. Marker powstaje wyłącznie i trwale
przed pierwszym dostępem do datasetu; plik oraz katalog nadrzędny są
synchronizowane. Istniejący, częściowy albo niezgodny marker zawsze blokuje
ponowienie.

Zewnętrzne, nieśledzone dowody wejściowe mają zamrożone ścieżki
`.omo/sealed/a-b-one-shot-v1/merge-verification.json` i
`.omo/sealed/a-b-one-shot-v1/run-authorization.json`. Pierwszy wiąże bieżący
commit i tree z surowym payloadem GitHub `verified=true`, `reason=valid`,
podpisem, payloadem oraz jego kanonicznym SHA-256. Runner dodatkowo wykonuje
offline `git verify-commit` dla dokładnego SHA. Ten plik jest atestacją
zmaterializowaną przez zaufanego operatora po sprawdzeniu live API GitHub, a
nie samodzielnym dowodem kryptograficznym.

Drugi plik utrwala pełną tożsamość nowego komentarza: repozytorium
`PSyron/polis`, issue 243, całkowity identyfikator ściśle większy niż
`5228447541`, skonstruowany z niego dokładny URL, autora `PSyron`, czas
późniejszy od pełnego preflightu oraz ciało z dokładnymi tokenami SHA źródła,
konfiguracji i datasetu. Kanoniczny digest atestacji operatora obejmuje cały
ten zapis. Zaufane materializowanie obu plików po weryfikacji live przez
operatora stanowi granicę zaufania; runner podczas wykonania nie używa sieci.
Prerejestracja celowo nie zapisuje przyszłych wartości tych pól.

Raport surowy dopuszcza jedynie agregaty jakości, wydajności, środowiska i
wyniki per źródło. Raport znormalizowany pomija dane czasowe, RSS i dane hosta,
dzięki czemu rebuild ma kanoniczne, stabilne bajty. Oba schematy odrzucają pola
z tekstem przypadku, goldem, sugestią lub prywatną ścieżką.

### Wynik `polis-a-b-one-shot-v1`

Jedyna autoryzowana próba dla merge
`b22e389cb5309ee17f35f1884b90b4cbaa7efd34` została zużyta i zakończyła się
globalnym werdyktem `fail_threshold`. Precision, recall, F1 i exact-span
accuracy wyniosły `0.9473684210526315`, exact-correction accuracy `1.0`, a
correct-sentence false-alarm rate `0.037037037037037035`.

Raport per dokładna tożsamość zawiera 12 wyników `pass`, jeden
`fail_threshold` i siedem `insufficient_evidence`. Globalny failure i każdy
wynik różny od `pass` pozostają wiążące: nie wolno uruchamiać eksperymentu
ponownie ani stroić zachowania na tym holdoucie. Osobna decyzja o promocji może
dotyczyć wyłącznie pełnego klucza tożsamości z wynikiem `pass`; nie może objąć
źródła niezaliczonego, niejednoznacznego ani całej kategorii.

Marker i raporty są niezmiennym dowodem konsumpcji. Odbudowa raportu
znormalizowanego z raportu surowego daje identyczne bajty, a skan prywatności
nie wykazuje tekstu przypadków, goldów, sugestii ani prywatnych ścieżek.
