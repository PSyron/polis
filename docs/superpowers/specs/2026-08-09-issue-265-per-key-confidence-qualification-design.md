# Projekt ponownej kwalifikacji progów pewności dla 20 kluczy polityki

**Issue:** #265

**Status:** zatwierdzony projekt, oczekuje na przegląd zapisanej specyfikacji

**Data:** 2026-08-09

**Właściciel:** Paweł Cyroń

## Cel

Polis przeprowadzi nową, niezależną kwalifikację wszystkich 20 dokładnych
kluczy polityki korekty automatycznej. Kwalifikacja ma wyznaczyć dla każdego
klucza jeden próg `minimum_confidence` związany z jego obecnym zachowaniem albo
jednoznacznie stwierdzić brak podstaw do automatyzacji.

Projekt nie otwiera ponownie eksperymentu `polis-a-b-one-shot-v1`. Jego marker,
raporty i wynik `fail_threshold` pozostają niezmienne, a zużyty holdout nigdy
nie jest ponownie odczytywany, uruchamiany ani używany do strojenia. Nowa praca
otrzymuje nowe zbiory, manifesty, konfiguracje, podpisy, marker i tożsamość
eksperymentu.

## Kontekst decyzji

Issue #243 wykonało dokładnie jedną prerejestrowaną próbę. Wynik zawierał 12
źródeł z werdyktem `pass`, jedno `fail_threshold` i siedem
`insufficient_evidence`, lecz nie mierzył ani nie publikował progów
`minimum_confidence`. Nie daje więc podstaw do zmiany polityki #244.

Maintainer zatwierdził następujące decyzje dla nowej kwalifikacji:

1. kwalifikacja obejmuje ponownie wszystkie 20 dokładnych kluczy;
2. obecne wartości `Finding.confidence` i `behavior_version` pozostają bez
   zmian;
3. dla każdego klucza jedynym kandydatem jest
   `minimum_confidence = emitted_confidence` albo brak progu;
4. kalibracja wymaga co najmniej 20 przypadków błędnych i 40 poprawnych na
   każdy klucz;
5. niezależny holdout wymaga co najmniej 10 przypadków błędnych i 20 poprawnych
   na każdy klucz;
6. obowiązuje profil jakości `active-baseline-v1`;
7. wynik jakości jest rozstrzygany osobno dla każdego dokładnego klucza, o ile
   integralność całego eksperymentu jest prawidłowa.

## Granice

### W zakresie

- nowy, powtarzalny etap kalibracji na autorskim zbiorze CC0;
- osobny, niezależny i jednorazowy holdout;
- ścisłe schematy manifestów, konfiguracji, raportów i podpisów;
- pomiar jakości i deterministyczności osobno dla 20 kluczy;
- wybór dokładnego progu albo `none` przed ujawnieniem holdoutu;
- późniejsza zmiana polityki wyłącznie w osobnym issue i dla pełnych kluczy,
  które uzyskały kompletny `pass`;
- jawne wycofanie istniejącego uprawnienia, jeżeli obecnie automatyczny klucz
  nie przejdzie nowej kwalifikacji.

### Poza zakresem

- zmiana reguł, ich `confidence`, operacji albo wersji zachowania;
- dodawanie nowych źródeł, kategorii lub ogólnego silnika morfologicznego;
- strojenie na holdoucie, dobieranie niższego progu po wyniku albo retry;
- ponowne wykorzystanie przypadków, autorów lub plaintextu z #243;
- model, Java, pełny LanguageTool, sieć podczas analizy albo wnioskowanie
  semantyczne;
- włączenie danych lub narzędzi badawczych do wheel albo sdist;
- automatyczna promocja jako efekt samego raportu kwalifikacyjnego.

## Tożsamości

Nowe publiczne identyfikatory są następujące:

- zbiór kalibracyjny: `polis-a-b-calibration-v2-v1`;
- niezależny holdout: `polis-a-b-holdout-v2-v1`;
- eksperyment: `polis-a-b-qualification-v2-v1`.

Każdy raport i manifest wiąże pełną krotkę:

`(source, category, operation, behavior_version, source_policy_version)`.

Kolejność, pełna tożsamość, emitowana pewność i stan 20 źródeł są zamrożone
poniżej. Każdy wiersz ma dokładnie pola:

`[source, category, operation, behavior_version, source_policy_version, emitted_confidence, current_policy_state]`.

```json
[
  ["rule:agreement.copula", "agreement", "replace.copula_form", "agreement-copula/1.0", "1.2", 0.93, "automatic"],
  ["rule:agreement.te_zdanie", "agreement", "replace.demonstrative_neuter_phrase", "agreement-te-zdanie/1.0", "1.2", 0.98, "review-only"],
  ["rule:agreement.nominal_group_te_duze_okno", "agreement", "replace.demonstrative_neuter_form", "agreement-nominal-group-te-duze-okno/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393", "1.2", 0.9, "review-only"],
  ["rule:agreement.subject_verb_oni_czyta", "agreement", "replace.subject_verb_number", "agreement-subject-verb-oni-czyta/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393", "1.2", 0.9, "review-only"],
  ["rule:inflection.negated_widziec", "inflection", "replace.negated_government_form", "inflection-negated-widziec/1.0", "1.2", 0.9, "review-only"],
  ["rule:inflection.negated_widziec_nominal_group", "inflection", "replace.negated_government_nominal_group", "inflection-negated-widziec-nominal-group/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393", "1.2", 0.9, "review-only"],
  ["rule:inflection.government_potrzebowac_pomoc", "inflection", "replace.governed_form", "inflection-government-potrzebowac-pomoc/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393", "1.2", 0.9, "review-only"],
  ["rule:spelling.jestes", "spelling", "replace.common_typo", "spelling-jestes/1.0", "1.2", 0.96, "automatic"],
  ["rule:spelling.napewno", "spelling", "replace.common_typo", "spelling-napewno/1.0", "1.2", 0.98, "review-only"],
  ["rule:spelling.wlasnie", "spelling", "replace.common_typo", "spelling-wlasnie/1.0", "1.2", 0.97, "automatic"],
  ["rule:spelling.zeby", "spelling", "replace.common_typo", "spelling-zeby/1.0", "1.2", 0.98, "automatic"],
  ["rule:syntax.comma_space", "punctuation", "normalize.comma_spacing", "syntax-comma-space/1.0", "1.2", 0.9, "automatic"],
  ["rule:syntax.duplicate_comma", "punctuation", "remove.duplicate_comma", "syntax-duplicate-comma/1.0", "1.2", 0.9, "review-only"],
  ["rule:syntax.initial_conditional_comma", "syntax", "insert.conditional_clause_comma", "syntax-initial-conditional-comma/1.0", "1.2", 0.9, "review-only"],
  ["rule:syntax.list_space", "syntax", "normalize.list_marker_spacing", "syntax-list-space/1.0", "1.2", 0.9, "automatic"],
  ["rule:syntax.missing_correlative", "syntax", "insert.correlative", "syntax-missing-correlative/1.0", "1.2", 0.9, "review-only"],
  ["rule:syntax.missing_destination_preposition", "syntax", "insert.destination_preposition", "syntax-missing-destination-preposition/1.0", "1.2", 0.9, "review-only"],
  ["rule:syntax.missing_reflexive", "syntax", "insert.reflexive_pronoun", "syntax-missing-reflexive/1.0", "1.2", 0.9, "review-only"],
  ["rule:syntax.quote_space", "punctuation", "normalize.quote_spacing", "syntax-quote-space/1.0", "1.2", 0.9, "automatic"],
  ["rule:syntax.sentence_space", "punctuation", "normalize.sentence_spacing", "syntax-sentence-space/1.0", "1.2", 0.9, "automatic"]
]
```

Kanoniczne bajty snapshotu powstają przez serializację tej tablicy jako JSON
UTF-8 z `ensure_ascii=false`, `sort_keys=true`, separatorami `(',', ':')`,
zakazem `NaN` oraz dokładnie jednym końcowym LF. Ich zamrożony SHA-256 to
`92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`.

Konfiguracja kalibracji musi zawierać tę samą tablicę i ten sam digest. Runner
wylicza snapshot z publicznego rejestru runtime'u i wymaga identycznych bajtów;
pominięcie, duplikat, zmiana kolejności lub drift dowolnego z siedmiu pól kończy
etap jako `inconclusive`. Snapshot nie jest importowany z raportu ani danych
holdoutu #243.

## Niezmienna reguła progu

Dla każdego klucza konfiguracja zapisuje dokładnie jedną deklarowaną wartość
`emitted_confidence`. Runner dodatkowo obserwuje `confidence` wszystkich
znalezisk przypisanych do tego klucza.

Kandydat jest dopuszczalny wyłącznie wtedy, gdy:

- wszystkie znalezione wartości są identyczne;
- wartość jest skończoną liczbą w zakresie `[0, 1]` i nie jest `bool`;
- wartość jest dokładnie równa prerejestrowanej `emitted_confidence`;
- pełna tożsamość klucza nie uległa zmianie.

Kalibracja może wybrać wyłącznie:

- `minimum_confidence = emitted_confidence`, albo
- `minimum_confidence = none`.

Nie wolno testować siatki progów, wybierać niższej wartości, zaokrąglać progu,
zmieniać `Finding.confidence` ani uznawać braku znalezisk za dowód bezpieczeństwa.
Zmiana emitowanej wartości lub któregokolwiek elementu klucza wymaga nowej
tożsamości i pełnej kwalifikacji od początku.

## Zbiory danych

### Kalibracja

Kalibracja jest powtarzalna, nie daje prawa do automatycznej korekty i może być
uruchamiana wyłącznie przed zamrożeniem decyzji progowej. Dla każdego z 20
kluczy zawiera co najmniej:

- 20 przypadków błędnych z jedną oczekiwaną minimalną poprawką;
- 40 poprawnych kontroli, dla których źródło nie może zwrócić znaleziska.

Minimalny rdzeń kalibracji obejmuje zatem 1200 przypadków. Jeden przypadek ma
jedno pole `primary_source_identity` i liczy się do mianownika tylko jednego
klucza. Nie wolno sztucznie powiększać pokrycia przez wielokrotne zaliczanie
tego samego zdania. Przypadki abstencji, nieznanej morfologii i konfliktu mogą
uzupełniać rdzeń, ale nie zastępują zatwierdzonych mianowników.

### Holdout

Holdout jest tworzony i recenzowany niezależnie od kalibracji. Dla każdego
klucza zawiera co najmniej:

- 10 przypadków błędnych;
- 20 poprawnych kontroli.

Minimalny rdzeń holdoutu obejmuje 600 przypadków. Plaintext i gold pozostają
zapieczętowane do chwili trwałej rezerwacji jedynego przebiegu. Raporty nie
zawierają tekstu, oryginału, sugestii ani prywatnej ścieżki.

### Pochodzenie, licencja i niezależność

Oba zbiory są autorskie, objęte `CC0-1.0` i mają pełny przegląd wszystkich
przypadków. Autorzy przypadków holdoutu nie czytają zbioru kalibracyjnego,
wyników kalibracji ani zużytego datasetu #243. Reviewer holdoutu jest niezależny
od implementacji runnera i reguł.

Manifest zapisuje co najmniej: identyfikator i wersję schematu, licencję,
proweniencję, role autorów i reviewerów, liczbę przypadków per klucz i rola,
status przeglądu, hash kanonicznych bajtów, rozmiar oraz brak PII.

Kontrolę dokładnych i przybliżonych duplikatów wykonuje niezależny opiekun przez
metadane i kluczowany oracle podobieństwa. Runner ani autor implementacji nie
otrzymuje plaintextu drugiego zbioru. Oracle ujawnia tylko identyfikatory
kolizji, klasy podobieństwa i werdykt; nie ujawnia zdań. Wykryta kolizja blokuje
zamrożenie zbioru, zamiast prowadzić do cichej zamiany przypadku po pomiarze.

## Architektura i przepływ

### 1. Kontrakt i snapshot źródeł

Repozytoryjny moduł badawczy zapisuje ścisły, prywatny dla `evaluation`
snapshot 20 pełnych kluczy, ich `emitted_confidence`, stan bieżącej polityki,
tożsamość analizatora, wheel i opcjonalnego Morfeusz2. Snapshot jest
kanoniczny i wersjonowany. Każdy drift kończy etap jako `inconclusive`.

### 2. Runner kalibracji

Runner ładuje wyłącznie zatwierdzony manifest i zewnętrznie zmaterializowany
zbiór kalibracyjny. Uruchamia finalny zainstalowany wheel lokalnie, bez sieci,
po jednym rozgrzewkowym i pięciu mierzonych powtórzeniach. Wyniki per klucz,
offsety `[start, end)`, poprawki, abstencje i fałszywe alarmy są porównywane z
goldem. Pięć hashy wyników musi być identyczne.

### 3. Wybór progów

Z wyniku kalibracji powstaje kanoniczny `threshold-selection.json`. Dla każdego
z 20 kluczy zawiera on pełną tożsamość, obserwowaną
`emitted_confidence`, mianowniki, metryki i dokładnie jeden wynik:
`candidate`, `fail_threshold` albo `insufficient_evidence`. Wartość dla
`candidate` jest zawsze równa `emitted_confidence`.

Dokument wyboru zostaje niezależnie przejrzany, podpisany i scalony przed
ujawnieniem holdoutu. Późniejsza zmiana progów, przypadków kalibracyjnych,
runtime'u lub konfiguracji unieważnia prerejestrację.

### 4. Prerejestracja one-shot

Prerejestracja wiąże dokładny merge i tree, wheel, konfigurację, snapshot 20
kluczy, wybór progów, oba manifesty, profil metryk, platformę, komendę,
schematy raportów i politykę błędów. Holdout nadal nie jest czytany.

### 5. Jednorazowe wykonanie

Po GitHub-verified merge, niezależnym preflighcie i osobnej autoryzacji runner
tworzy trwały marker przed pierwszym odczytem holdoutu. Marker oraz katalog
nadrzędny są synchronizowane. Istniejący, częściowy lub niezgodny marker
bezwarunkowo blokuje próbę. Awaria po rezerwacji zużywa eksperyment i nie daje
prawa do retry.

### 6. Raport i przekazanie do polityki

Raport surowy zawiera tylko dozwolone agregaty i wyniki per dokładny klucz.
Raport znormalizowany usuwa czas, RSS i dane hosta, dzięki czemu jego odbudowa
ma identyczne bajty. Osobny manifest wiąże hashe markera, raportów,
prerejestracji i autoryzacji.

Wynik kwalifikacyjny nie modyfikuje polityki. Jest wyłącznie wejściem do
osobnego issue uzgadniającego exact keys.

## Profil jakości i werdykty

Dla każdego klucza obowiązują wartości profilu `active-baseline-v1`:

- `precision >= 1.0`;
- `recall >= 0.7142857142857143`;
- `f1 >= 0.8333333333333334`;
- `exact_span_accuracy >= 0.7142857142857143`;
- `exact_correction_accuracy >= 1.0`;
- `correct_sentence_false_alarm_rate <= 0.0`.

Każdy licznik i mianownik jest raportowany per klucz. Agregaty dla całego
eksperymentu są informacyjne i nie mogą ukryć słabego źródła ani unieważnić
niezależnego wyniku innego źródła.

Możliwe wyniki per klucz:

- `pass`: wszystkie mianowniki, progi, deterministyczność i tożsamość są
  kompletne;
- `fail_threshold`: dane są kompletne, lecz co najmniej jeden próg nie został
  spełniony;
- `insufficient_evidence`: brakuje mianownika, unikalnej wartości confidence,
  obsługi środowiska albo zgodnej tożsamości.

`pass` review-only oznacza jedynie możliwość rozpatrzenia dokładnego wpisu w
#244. `fail_threshold` i `insufficient_evidence` pozostają review-only. Jeśli
klucz mający już automatyczne uprawnienie uzyska wynik inny niż `pass`, osobny
fail-closed policy reconciliation usuwa jego wpis przed dodaniem jakiegokolwiek
nowego uprawnienia. Nie wolno pozostawić znanego niezakwalifikowanego klucza
automatycznego tylko dlatego, że jego wpis powstał wcześniej.

## Błędy i unieważnienie

### Globalne błędy integralności

Następujące zdarzenia unieważniają cały przebieg:

- błędny podpis, commit, tree, SHA-256 albo niezgodna kanoniczność;
- odczyt danych przed rezerwacją;
- istniejący lub częściowy marker;
- niezgodna liczba albo kolejność 20 kluczy;
- niedeterministyczne hashe powtórzeń;
- próba sieciowa, wyciek prywatnego tekstu albo PII;
- niezgodna platforma, executable albo środowisko;
- nieznane pole, niepoprawny typ, `NaN`, nieskończoność lub `bool` jako liczba;
- przerwanie po rezerwacji.

Po takim błędzie żaden klucz nie otrzymuje `pass`. Próba pozostaje zużyta, gdy
marker już powstał.

### Lokalne wyniki klucza

Kompletny i prawidłowy eksperyment rozstrzyga jakość niezależnie per klucz.
Brak mianownika, drift confidence lub identity, alternatywna uzasadniona
poprawka, niejednoznaczna morfologia albo nieobsługiwany provider daje
`insufficient_evidence` tylko dla danego klucza. Przekroczenie progu jakości
daje `fail_threshold` dla tego klucza. Wynik jednego klucza nie zmienia wyniku
innego, jeśli nie narusza globalnej integralności.

## Bezpieczeństwo one-shot

Nowe wykonanie używa osobnej autoryzacji, namespace i ścieżek. Nie kopiuje
autoryzacji ani markera #243. Prerejestracja zamraża:

- `host_system=Darwin` i `host_machine=arm64`;
- dokładną bezwzględną ścieżkę `/usr/bin/ssh-keygen` i jej SHA-256;
- metodę `ssh-ed25519-detached`;
- zaufany fingerprint klucza maintainera
  `SHA256:JvdjEgHYEQPsrsthSO5GnrM7saNvsanY5uJl89B0lQk`;
- nowy namespace `polis-holdout-authorization-v2`;
- GitHub-verified merge z `verified=true` i `reason=valid`;
- dynamiczny, przyszły komentarz autoryzacyjny związany z merge, konfiguracją,
  datasetami, wyborem progów i dokładną komendą.

Prerejestracja zamraża również schemat
`polis.a-b-qualification-v2.run-authorization` w wersji `1`, numer issue
wykonawczego oraz dolną, wyłączną granicę identyfikatora komentarza. Obiekt
autoryzacji ma dokładnie następujące pola; brak, pole dodatkowe albo zmiana typu
jest błędem admission:

`schema_id`, `schema_version`, `run_authorization`, `repository`,
`issue_number`, `comment_id`, `comment_url`, `author`, `created_at`,
`preflight_completed_at`, `body`, `evaluated_merge_sha`, `evaluated_tree_sha`,
`source_snapshot_sha256`, `config_sha256`, `calibration_manifest_sha256`,
`holdout_manifest_sha256`, `threshold_selection_sha256`, `wheel_sha256`,
`sdist_sha256`, `lockfile_sha256`, `exact_command`, `exact_command_sha256`,
`github_merge_verified`, `github_merge_verification_reason`,
`github_merge_verification_payload_sha256`, `authorization_method`,
`signer_fingerprint`, `namespace`, `ssh_keygen_path`, `ssh_keygen_sha256` oraz
`operator_attestation_sha256`.

Stałe wartości to `run_authorization=approved`, `author=PSyron`,
`github_merge_verified=true`, `github_merge_verification_reason=valid`,
`authorization_method=ssh-ed25519-detached`, zamrożony fingerprint, namespace,
repozytorium, numer issue oraz ścieżka executable. Prerejestracja zapisuje
oczekiwane wartości wszystkich pozostałych bindingów poza dynamiczną
tożsamością i czasem przyszłego komentarza.

`comment_id` ma typ dokładnie `int`, nie `bool`, i jest większy od zamrożonej
granicy. URL jest konstruowany wyłącznie z zamrożonego repozytorium, numeru
issue i tego identyfikatora. Autor musi być dokładnie `PSyron`, a
`created_at > preflight_completed_at`. Ciało nie zawiera rekurencyjnie pola
`body` ani `operator_attestation_sha256`. Ma dokładnie jedną linię
`field=<kanoniczna wartość>`, bez pustych, dodatkowych albo powtórzonych linii,
dla następujących pól i w dokładnie tej kolejności:

`schema_id`, `schema_version`, `run_authorization`, `repository`,
`issue_number`, `comment_id`, `comment_url`, `author`, `created_at`,
`preflight_completed_at`, `evaluated_merge_sha`, `evaluated_tree_sha`,
`source_snapshot_sha256`, `config_sha256`, `calibration_manifest_sha256`,
`holdout_manifest_sha256`, `threshold_selection_sha256`, `wheel_sha256`,
`sdist_sha256`, `lockfile_sha256`, `exact_command`, `exact_command_sha256`,
`github_merge_verified`, `github_merge_verification_reason`,
`github_merge_verification_payload_sha256`, `authorization_method`,
`signer_fingerprint`, `namespace`, `ssh_keygen_path` i `ssh_keygen_sha256`.

Taki niecykliczny body wiąże token zatwierdzenia, pełną provenance, wszystkie
SHA, dokładną komendę i ścieżkę executable. Nie wolno ufać samemu lokalnemu
opisowi komentarza.

Kanoniczny payload podpisu to cały obiekt autoryzacji serializowany jako JSON
UTF-8 z `ensure_ascii=false`, `sort_keys=true`, separatorami `(',', ':')`,
zakazem `NaN` i jednym końcowym LF. `operator_attestation_sha256` jest SHA-256
kanonicznego obiektu po usunięciu wyłącznie pola
`operator_attestation_sha256`; obiekt nadal zawiera gotowe, niecykliczne
`body`. Odłączony podpis
`ssh-ed25519` obejmuje dokładne kanoniczne bajty, a nie ich luźną rekonstrukcję.

Admission działa w niezmiennej kolejności, przed jakąkolwiek rezerwacją albo
próbą odczytu datasetu:

1. sprawdza zamrożony host, platformę i wymagania executable;
2. otwiera autoryzację i podpis deskryptorowo, z `O_NOFOLLOW`, oraz potwierdza
   stabilność bajtów i inode;
3. sprawdza ścisły schemat, typy, kanoniczność, provenance komentarza, czas,
   ciało, wszystkie bindingi i self-digest;
4. sprawdza stałą ścieżkę i hash executable, po czym wewnętrznie konstruuje
   konkretny verifier z zamrożonego klucza i namespace;
5. weryfikuje odłączony podpis;
6. atomowo tworzy i synchronizuje marker oraz katalog nadrzędny;
7. dopiero wtedy pozwala loaderowi odczytać holdout.

Każdy błąd kroków 1-5 kończy się bez wywołania verifiera, rezerwacji i loadera
odpowiednio do etapu, na którym wystąpił. Publiczne API produkcyjne nie może
przyjmować ani podmieniać verifiera, komendy, ścieżki, klucza, fingerprintu,
namespace, platformy ani implementacji systemowej. Runner tworzy konkretny
prywatny verifier wyłącznie z prerejestrowanych stałych, nie używa `PATH` ani
fallbacku. Testy mogą zastępować tylko prywatne adaptery procesu i platformy.

Ścieżki są otwierane deskryptorowo i bez podążania za symlinkami. Runner
sprawdza stabilność inode, właściciela, tryb, hash i executable bez używania
`PATH`. Weryfikacja i rezerwacja działają offline. Prywatny klucz nie trafia do
repozytorium, logów ani raportów.

## Granica pakowania i prywatności

Kod runnerów, ich `__main__`, konfiguracje wykonawcze, datasety i katalogi
eksperymentów pozostają repository-only. Wheel i sdist nie zawierają nowych
modułów one-shot ani żadnego pliku `cases.json`. Zainstalowany produkt nadal
udostępnia wyłącznie wspierane API i CLI runtime'u.

Raporty dopuszczają identyfikatory, liczniki, metryki, hashe, wersje i werdykty.
Schematy odrzucają tekst przypadku, gold, original, suggestion, prywatną
ścieżkę, dane osobowe i dowolne pola dodatkowe. Skan prywatności jest bramką,
nie informacyjnym ostrzeżeniem.

## Strategia testów

Każde issue implementacyjne zaczyna się od RED, który zawodzi wyłącznie przez
brak zatwierdzonego zachowania. Łączny kontrakt obejmuje:

1. dokładne 20 pełnych kluczy, kolejność, duplikaty i digest snapshotu;
2. mianowniki `20+40` oraz `10+20`, granice o jeden przypadek poniżej i zakaz
   wielokrotnego zaliczania;
3. regułę `emitted_confidence` albo `none`, w tym drift, wiele wartości,
   `bool`, `NaN` i nieskończoność;
4. metryki i niezależne werdykty per klucz oraz globalne błędy integralności;
5. nieznane pola, błędne typy, niekanoniczny JSON, SHA drift i niepełny review;
6. niezależność i wykrywanie dokładnych oraz przybliżonych duplikatów;
7. brak odczytu holdoutu przed markerem, trwałość markera, przerwanie i zakaz
   retry;
8. podpis, GitHub verification, host, executable, symlinki, inode i tryby;
9. blokadę sieci i brak plaintextu w stdout, stderr, markerze oraz raportach;
10. identyczne hashe pięciu powtórzeń i byte-identical rebuild raportu;
11. brak modułów i danych badawczych w wheel oraz sdist;
12. review-only przed osobnym policy reconciliation i pełne exact-key
    fail-closed po driftach.

Manual QA używa syntetycznych danych oraz tymczasowego klucza. Przed
autoryzowanym one-shot nie uruchamia prawdziwego holdoutu. Po konsumpcji QA
sprawdza wyłącznie markery, schematy, agregaty, hashe i rebuild; nie otwiera
plaintextu ani nie uruchamia analizy ponownie.

## Sekwencja dostarczania

Realizacja nie mieści się w jednym issue. Po zatwierdzeniu tej specyfikacji
powstają kolejno:

1. issue kontraktu i repository-only runnera kalibracji;
2. issue niezależnego wygenerowania, przeglądu i zamrożenia manifestów obu
   nowych zbiorów;
3. issue wykonania powtarzalnej kalibracji i publikacji podpisanego wyboru
   progów;
4. issue prerejestracji osobnego one-shot na finalnym merge;
5. append-only issue autoryzacji, pojedynczego wykonania i publikacji wyniku;
6. #244 jako osobne policy reconciliation dla każdego kompletnego exact key;
7. końcowy audyt i zamknięcie #236 wyłącznie po prawdziwym spełnieniu jego
   kryteriów.

Każdy krok ma własną gałąź, jeden skupiony commit, pull request, niezależny
review, zielone CI i post-merge binding. Dane nie są generowane przed
zatwierdzeniem kontraktu, a holdout nie jest ujawniany przed scaleniem
prerejestracji.

## Rozważone alternatywy

### Zakwalifikować tylko pięć review-only wyników `pass` z #243

Odrzucono. Eksperyment nie mierzył `minimum_confidence`, a maintainer wybrał
ponowną kwalifikację wszystkich 20 kluczy. Wybór pięciu po ujawnieniu wyniku
byłby strojenem zakresu na zużytym holdoucie.

### Obniżać próg confidence na siatce

Odrzucono. Wartość `confidence` nie jest samodzielnym dowodem bezpieczeństwa,
a wybór najniższego przechodzącego progu zwiększa przestrzeń strojenia. Wariant
1 dopuszcza wyłącznie obecną emitowaną wartość albo brak progu.

### Zmienić confidence reguł i behavior versions

Odrzucono. Łączyłoby zmianę zachowania produktu z kwalifikacją i wymagałoby
nowych testów każdej reguły. Nowy eksperyment ma mierzyć bieżące zachowanie,
nie tworzyć inne.

### Jedna globalna bramka zamiast wyników per klucz

Odrzucono. Agregat pozwala dobrym źródłom ukryć fałszywy alarm innego źródła i
nie odpowiada dokładnej tożsamości polityki ADR-0024. Globalne pozostają tylko
bramki integralności, prywatności, bezpieczeństwa i deterministyczności.

## Definicja ukończenia projektu

Projekt jest gotowy do planowania implementacji, gdy:

- dokument jest kompletny i nie pozostawia otwartej decyzji;
- pełna uporządkowana lista 20 siedmiopolowych kluczy ma zamrożony kanoniczny
  digest `92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`;
- autoryzacja one-shot ma zamknięty kanoniczny payload, dynamiczne provenance
  komentarza, ścisłą kolejność admission i prywatny konkretny verifier;
- maintainer zaakceptuje zapisany dokument;
- issue #265 ma pełne kryteria, ownership i odnośnik do commita;
- diff obejmuje wyłącznie tę specyfikację i jej wymagany dokładny wpis
  `retain_historical_evidence` w inwentarzu dokumentacji;
- testy dokumentacji, formatowania i integralności repozytorium przechodzą;
- nie powstał żaden dataset, runner, marker, raport ani wpis polityki.
