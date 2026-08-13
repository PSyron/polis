# ADR-0025: Ewolucja kohorty źródeł runtime'u

- Status: Accepted
- Data: 2026-08-13
- Właściciel: Paweł Cyroń
- Issue: #302

## Kontekst

Kwalifikacja zaprojektowana w #265 i wdrożona przez #267 oraz #269 zamroziła
dokładnie 20 uporządkowanych tożsamości źródeł. Jej zbiory, manifesty,
walidatory i późniejsze dowody odnoszą się do tej jednej kohorty. SHA-256
kanonicznych bajtów jej 20 wierszy wynosi
`92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`.

Runtime ma rozwijać się o osiem kolejnych deterministycznych źródeł. Samo
dodanie źródła do composition root nie może jednak zmieniać znaczenia
historycznej kwalifikacji, rozszerzać jej mianowników ani nadawać nowemu
źródłu prawa do automatycznej korekty. Potrzebne są zatem dwie niezależne,
obserwowalne tożsamości kohort: niezmienna kohorta kwalifikacji oraz rozwijana
kohorta runtime'u i jego bieżącej dokumentacji. Tożsamość kohorty runtime'u
nie jest kluczem polityki automatycznej z ADR-0024.

## Decyzja

### Obserwowalny kontrakt kohort

Poniższe literały są stabilnymi elementami tej decyzji. Nie są konfiguracją
runtime'u ani nowym formatem artefaktu badawczego.

| Klucz kontraktu | Wartość |
| --- | --- |
| `qualification_cohort_id` | `polis-a-b-qualification-v2-source-cohort-v1` |
| `qualification_ordered_rows` | `20` |
| `qualification_source_snapshot_sha256` | `92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92` |
| `qualification_extra_source_handling` | `reject` |
| `runtime_source_cohort_id` | `polis-runtime-source-cohort-28-v1` |
| `runtime_ordered_sources` | `28` |
| `runtime_target_validation` | `exact-ordered-28` |
| `additions_policy_state` | `review-only` |
| `additions_identity_kind` | `planned-runtime-source-identity` |
| `additions_source_policy_version` | `absent` |
| `additions_policy_entry` | `none` |
| `automatic_policy_identity_created` | `false` |
| `qualification_scope_inheritance` | `forbidden` |
| `automatic_requalification` | `new-dataset-and-experiment-identity` |
| `automatic_requalification_exact_key` | `(source, category, operation, behavior_version, source_policy_version)` |
| `source_policy_version_inheritance` | `forbidden` |

### Niezmienna kohorta kwalifikacji

`polis-a-b-qualification-v2-source-cohort-v1` oznacza wyłącznie pierwotną,
uporządkowaną krotkę 20 wierszy z
`src/polis/evaluation/calibration_source_rows.py`. Każdy wiersz zachowuje siedem
pól w kolejności:

`(source, category, operation, behavior_version, source_policy_version, emitted_confidence, current_policy_state)`.

Kanoniczne bajty wytwarzane przez `canonical_source_bytes()` oraz ich digest
`92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`
jednoznacznie identyfikują całą zawartość i kolejność kohorty. Ten kontrakt nie
jest zbiorem pierwszych 20 pozycji przyszłego runtime'u ani filtrem kategorii.
Brak wiersza, dodatkowy wiersz, duplikat, zmiana kolejności albo drift dowolnego
z siedmiu pól oznacza inną kohortę i musi zostać odrzucony.

Wszystkie walidatory kalibracji i holdoutu wynikające z #265, zamrożone zbiory,
manifesty, przeglądy, raporty, zobowiązania i inne dowody pozostają związane
z tymi dokładnymi 20 wierszami oraz tym digestem. Pierwotne bajty wierszy i
każdy zamrożony artefakt pozostają byte-identical. Nie wolno przepisywać ich
na 28 pozycji, rozszerzać mianowników, dopisywać nowych źródeł ani interpretować
braku błędu walidacji jako kwalifikacji źródła spoza kohorty.

Istniejące walidatory zachowują semantykę exact-match. Gdy composition root
zawiera dodatkowe źródło, walidator starej kohorty ma odrzucić taki bieżący
snapshot jako drift, zamiast zignorować nadmiar. Jest to oczekiwane zachowanie
fail-closed, a nie powód do zmiany `SOURCE_ROWS`, digestu, datasetu albo
historycznego raportu. Zużytych holdoutów i zamrożonych eksperymentów nie
uruchamia się ponownie przeciw rozwiniętemu runtime'owi.

### Rozwijana kohorta runtime'u i dokumentacji

`polis-runtime-source-cohort-28-v1` jest odrębną tożsamością docelowego
composition root i utrzymywanego wykazu źródeł. W chwili przyjęcia ADR osiem
dodatków jest wyłącznie zamrożonym celem kolejnych issue; niniejsza decyzja nie
rejestruje reguł w runtime i nie aktualizuje `docs/rules.md` przed ich dostawą.

Po dostarczeniu wszystkich ośmiu źródeł przyszły kontrakt runtime'u ma
porównywać uporządkowany snapshot composition root oraz uporządkowaną tabelę w
`docs/rules.md` z dokładną listą 28 pozycji poniżej. Kontrola ma odrzucać brak,
nadmiar, duplikat, zmianę kolejności oraz drift planowanej tożsamości źródła.
Dla ośmiu dodatków sprawdza również dokładne `category`, `operation`,
`behavior_version`, emitowane `confidence` i stan `review-only` z tabeli
tożsamości. Musi to być osobny kontrakt runtime'u, a nie rozszerzenie ani
ponowne użycie walidatora kohorty kwalifikacji.

Tabela ośmiu dodatków zamraża wyłącznie `source`, `category`, `operation`,
`behavior_version`, emitowane `confidence`, pozycję/kolejność oraz stan
`review-only`. Jest to planowana tożsamość źródła runtime'u, nie pełny klucz
polityki automatycznej opisany przez ADR-0024. Tabela celowo nie zawiera
`source_policy_version`; niniejsze issue nie tworzy ani nie zmienia wpisu
polityki, więc nie powstaje tu żadna tożsamość polityki automatycznej.

W trakcie ośmiu osobnych dostaw composition root i `docs/rules.md` pozostają
ze sobą zsynchronizowane. Bramka `exact-ordered-28` staje się spełniona dopiero
po dostarczeniu pełnego celu; nie zmienia to zakresu żadnego historycznego
eksperymentu.

### Docelowa kolejność kohorty runtime'u

| Pozycja | Source |
| ---: | --- |
| 1 | `rule:agreement.copula` |
| 2 | `rule:agreement.te_zdanie` |
| 3 | `rule:agreement.nominal_group_te_duze_okno` |
| 4 | `rule:agreement.nominal_group_ta_nowy_ksiazka` |
| 5 | `rule:agreement.subject_verb_oni_czyta` |
| 6 | `rule:agreement.subject_verb_my_czyta` |
| 7 | `rule:inflection.negated_widziec` |
| 8 | `rule:inflection.negated_widziec_nominal_group` |
| 9 | `rule:inflection.przygladac_sie_nowy_budynek` |
| 10 | `rule:inflection.government_potrzebowac_pomoc` |
| 11 | `rule:inflection.government_szukac_klucz` |
| 12 | `rule:spelling.jestes` |
| 13 | `rule:spelling.napewno` |
| 14 | `rule:spelling.wlasnie` |
| 15 | `rule:spelling.zeby` |
| 16 | `rule:spelling.wogole` |
| 17 | `rule:spelling.narazie` |
| 18 | `rule:spelling.wziasc` |
| 19 | `rule:syntax.comma_space` |
| 20 | `rule:syntax.duplicate_comma` |
| 21 | `rule:syntax.initial_conditional_comma` |
| 22 | `rule:syntax.initial_temporal_comma` |
| 23 | `rule:syntax.list_space` |
| 24 | `rule:syntax.missing_correlative` |
| 25 | `rule:syntax.missing_destination_preposition` |
| 26 | `rule:syntax.missing_reflexive` |
| 27 | `rule:syntax.quote_space` |
| 28 | `rule:syntax.sentence_space` |

Kolejność względna pierwotnych 20 źródeł pozostaje bez zmian. Nowe źródła są
wstawione w pozycjach zgodnych z ich kategoriami.

### Planowane tożsamości ośmiu źródeł runtime'u

| Pozycja | Source | Category | Operation | Behavior version | Confidence | Stan polityki |
| ---: | --- | --- | --- | --- | ---: | --- |
| 4 | `rule:agreement.nominal_group_ta_nowy_ksiazka` | `agreement` | `replace.adjective_gender` | `agreement-nominal-group-ta-nowy-ksiazka/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 6 | `rule:agreement.subject_verb_my_czyta` | `agreement` | `replace.subject_verb_number` | `agreement-subject-verb-my-czyta/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 9 | `rule:inflection.przygladac_sie_nowy_budynek` | `inflection` | `replace.governed_nominal_group` | `inflection-przygladac-sie-nowy-budynek/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 11 | `rule:inflection.government_szukac_klucz` | `inflection` | `replace.governed_form` | `inflection-government-szukac-klucz/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 16 | `rule:spelling.wogole` | `spelling` | `replace.common_typo` | `spelling-wogole/1.0` | `0.98` | `review-only` |
| 17 | `rule:spelling.narazie` | `spelling` | `replace.common_typo` | `spelling-narazie/1.0` | `0.98` | `review-only` |
| 18 | `rule:spelling.wziasc` | `spelling` | `replace.common_typo` | `spelling-wziasc/1.0` | `0.98` | `review-only` |
| 22 | `rule:syntax.initial_temporal_comma` | `syntax` | `insert.temporal_clause_comma` | `syntax-initial-temporal-comma/1.0` | `0.9` | `review-only` |

Każdy dodatek zaczyna jako `review-only`. Emitowane `confidence` jest częścią
zamrożonej tożsamości planowanego zachowania, lecz samo nie jest zmierzonym
progiem automatycznej korekty i nie nadaje żadnych uprawnień polityki. Użyte
w tym rozdziale określenia „tożsamość” i „dokładna tożsamość” oznaczają tylko
zamrożone pola planowanego źródła runtime'u wymienione powyżej; nie oznaczają,
że tabela zawiera pełny klucz polityki automatycznej.

### Brak dziedziczenia kwalifikacji

Żadne z ośmiu źródeł nie dziedziczy kwalifikacji na podstawie podobnego
`source`, wspólnej kategorii, operacji, dostawcy morfologii, wersji danych,
pozycji obok zakwalifikowanego wiersza ani takiej samej wartości `confidence`.
Pierwotna kwalifikacja obejmuje tylko swoje dokładne 20 wierszy.

Przyszła kwalifikacja automatyczna któregokolwiek dodatku wymaga nowego,
niezależnego datasetu oraz nowej tożsamości eksperymentu. Zgodnie z ADR-0024
nowy eksperyment musi zamrozić i porównać aktualny wtedy pełny dokładny klucz

`(source, category, operation, behavior_version, source_policy_version)`.

`source_policy_version` musi pochodzić z jawnej, aktualnej wtedy polityki; nie
wolno go dziedziczyć ani wywnioskować ze starej kohorty 20 wierszy. Nowy
eksperyment musi zmierzyć wymagany próg i przejść właściwą bramę bez ponownego
użycia zużytego holdoutu. Nie wolno rozszerzyć istniejącego datasetu,
manifestu, raportu ani commitmentu o nowy wiersz i przedstawiać wyniku jako
kontynuacji dawnego eksperymentu.

## Konsekwencje

- Historyczna kwalifikacja pozostaje audytowalna i byte-identical niezależnie
  od wzrostu runtime'u.
- Runtime i `docs/rules.md` mogą ewoluować razem do dokładnego celu 28 bez
  fałszywego rozszerzenia dawnych roszczeń jakościowych.
- Stare walidatory nadal wykrywają każdy brak, nadmiar, drift i zmianę
  kolejności względem 20 wierszy; przyszły kontrakt runtime'u ma osobną
  tożsamość i osobne oczekiwanie 28 pozycji.
- Ten ADR nie zmienia runtime'u, polityki automatycznej, zależności, publicznego
  API, datasetu, manifestu, raportu, commitmentu ani zamrożonych bajtów źródeł.
- Tabela dodatków nie tworzy wpisu polityki ani wersji polityki źródła;
  przyszła promocja nie może odziedziczyć tych danych ze starej kohorty.
- Osiem nowych reguł, aktualizacje bieżącej dokumentacji źródeł i ich testy
  należą do osobnych issue implementacyjnych.

## Rozważone alternatywy

- **Przepisać kohortę kwalifikacji z 20 na 28.** Odrzucono, ponieważ zmieniłoby
  to tożsamość zakończonego eksperymentu i przypisałoby ośmiu dodatkom dowody,
  których nie zebrano.
- **Pozwolić starym walidatorom ignorować dodatkowe źródła runtime'u.**
  Odrzucono, ponieważ nadmiar przestałby być obserwowalnym driftem, a zakres
  raportów i mianowników stałby się niejednoznaczny.
- **Użyć jednej ruchomej kohorty dla runtime'u i kwalifikacji.** Odrzucono,
  ponieważ każda dostawa reguły zmieniałaby znaczenie historycznych zobowiązań
  i uniemożliwiałaby byte-identical odtworzenie kontraktu.
- **Dziedziczyć kwalifikację przez kategorię lub dostawcę.** Odrzucono, ponieważ
  automatyczne uprawnienie jest własnością dokładnego zachowania, a nie klasy
  podobnych reguł.
