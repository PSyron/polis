# ADR-0021: Ustanowienie własności katalogu reguł

- Status: Accepted
- Date: 2026-08-04
- Owner: Paweł Cyroń
- Issue: #149

## Kontekst

[Inwentarz źródeł z #148](../rule-catalog-inventory.md) zapisuje 10 domyślnych
i 2 opcjonalne źródła standardowego analizatora. Obecnie composition root
analizatora jednocześnie tworzy ich implementacje, ustala kolejność rejestracji
i buduje efektywny rejestr. Inwentarz wykazał też, że zakres kategorii zapisany
w `RuleRegistration` nie zawsze opisuje kategorię emitowaną przez regułę.

Potrzebna jest jedna granica własności dla przyszłego wyboru źródeł i inspekcji,
która zachowa protokół wykonania z [ADR-0018](0018-runtime-composition-protocols.md),
kartę produktu runtime-first z
[ADR-0020](0020-runtime-first-product-charter.md) oraz niezależną, dokładnie
wersjonowaną politykę automatycznych poprawek z
[ADR-0008](0008-hybrid-correction-policy.md). Ta decyzja nie zmienia zachowania
runtime'u ani publicznego API.

## Decyzja

### Własność i składanie

Warstwa `polis.rules` posiada kuratorowany katalog dokładnie 12 standardowych
źródeł ujętych w inwentarzu #148. Katalog jest źródłem prawdy o ich metadanych
i deterministycznej kolejności. Composition root `Analyzer` posiada wyłącznie
składanie katalogu z konfiguracją i zależnościami wykonawczymi w efektywny
rejestr. Nie jest drugim właścicielem metadanych katalogu.

Niestandardowe wartości `RuleRegistration` pozostają wspieranym mechanizmem
rozszerzeń w linii 0.x, ale nie stają się przez rejestrację wpisami
kuratorowanego katalogu. Dynamiczne źródła `llm:`, transporty, procesy i reguły
testowe pozostają poza katalogiem zgodnie z inwentarzem #148.

### Metadane, tożsamość i kolejność

Każdy wpis katalogu zawiera co najmniej:

- stabilny klucz `source`;
- `operation` i `behavior_version` wykonywanego zachowania;
- zbiór kategorii, które źródło może emitować;
- informację, czy źródło jest domyślnie włączone;
- dostępność źródła;
- opis przeznaczony do inspekcji przez człowieka.

Kategorie emitowane są metadanymi katalogu. Zakres kategorii w
`RuleRegistration` pozostaje mechanizmem wykonawczym i nie zastępuje tej
informacji. `source` jest stabilnym kluczem źródła, a obserwowalna zmiana
zachowania wymaga nowego `behavior_version`. Opis może być doprecyzowywany bez
zmiany tożsamości zgodności.

Klucze `source` są unikalne w całym katalogu: jedno źródło może wystąpić
dokładnie w jednym wpisie. Przed utworzeniem efektywnego rejestru konstrukcja
waliduje atomowo cały katalog. Zduplikowany wpis albo niepoprawne metadane — w
tym brak lub niepoprawna wartość `source`, `operation`, `behavior_version`,
kategorii emitowanych, stanu domyślnego włączenia, dostępności lub opisu, a
także niejednoznaczna bądź niedeterministyczna kolejność — kończą konstrukcję
deterministycznym błędem. Błąd zawiera wyłącznie bezpieczne identyfikatory
źródła i pól metadanych, nigdy analizowany tekst. Nie powstaje częściowy katalog
ani częściowy efektywny rejestr.

Ten kontrakt dotyczy integralności definicji katalogu i pozostaje odrębny od
opisanej niżej walidacji konfiguracji wyboru źródeł.

Kolejność wpisów katalogu jest deterministyczną kolejnością rejestracji i
gwarancją zgodności całej linii 0.x. Zmiana kolejności wymaga osobnej decyzji o
zgodności, ponieważ może zmienić kolejność znalezisk i rozstrzyganie konfliktów.

Opcjonalne źródło zachowuje jedną tożsamość niezależnie od transportu
wstrzykniętego, HTTP lub stdio. Dostępność implementacji, włączenie domyślne,
obecność konfiguracji i bieżące zdrowie transportu są odrębnymi stanami.
Transport nie tworzy nowego wpisu ani nowego `source`.

### Wybór źródeł i zgodność konfiguracji

Przyszły wybór źródeł ma następujące deterministyczne pierwszeństwo:

1. pominięte `enabled_sources` wybiera zestaw źródeł domyślnie włączonych;
2. jawne `enabled_sources` zastępuje ten zestaw;
3. `disabled_sources` zawsze odejmuje źródła od wyniku wcześniejszego kroku;
4. filtr kategorii ogranicza wynik do źródeł emitujących żądane kategorie.

Nieznane, zduplikowane lub niepoprawne wartości oraz jawnie wybrane źródło
niedostępne w danej instalacji kończą się deterministycznym błędem konfiguracji.
Błąd wskazuje wyłącznie bezpieczne metadane konfiguracji i nigdy nie zawiera
analizowanego tekstu.

Konfiguracja zawierająca wyłącznie dotychczasowy filtr kategorii zachowuje
obecne zachowanie: składany jest obecny zestaw domyślny, a kategorie ograniczają
wykonanie tak jak `AnalysisOptions.categories`. Migracja do wyboru źródeł jest
zatem opcjonalna; brak nowych kluczy nie zmienia wyniku ani kolejności.

### Granica polityki automatycznych poprawek

Katalog nie zawiera dyspozycji, progów pewności ani allowlisty automatycznych
poprawek. Włączenie lub dostępność źródła pozwala jedynie uruchomić analizę i nie
nadaje uprawnienia do automatycznej korekty.

Uprawnienie nadal wymaga osobnego dokładnego wpisu polityki o tożsamości
`(source, category, operation, behavior_version, source_policy_version)`.
Brak wpisu albo drift któregokolwiek elementu pozostawia znalezisko wyłącznie
do przeglądu. Metadane katalogu nie mogą tworzyć, rozszerzać ani zastępować
takiego wpisu.

### Inspekcja

Przyszły interfejs inspekcji rozróżnia dwa widoki: pełny kuratorowany katalog
standardowych źródeł oraz efektywny rejestr po uwzględnieniu konfiguracji,
dostępności i filtrów. Żaden z tych widoków nie deklaruje uprawnień polityki
automatycznych poprawek.

## Konsekwencje

- Dzieci implementacyjne #150-#155 mogą wprowadzać typy, wybór, migrację i
  inspekcję bez ponownego rozstrzygania własności.
- Katalog może pozostać stabilny, gdy zmienia się transport źródła opcjonalnego.
- Dotychczasowe konfiguracje category-only oraz niestandardowe rejestracje
  zachowują zgodność w linii 0.x.
- Snapshot JSON z #148 pozostaje niezmiennym dowodem stanu sprzed implementacji
  katalogu, a nie przyszłym plikiem konfiguracyjnym runtime'u.
- To issue nie dodaje typów, konfiguracji, zależności ani zachowania runtime'u.

## Odrzucone alternatywy

- **Własność katalogu w composition root.** Odrzucona, ponieważ miesza składanie
  zależności z własnością metadanych reguł i tworzy drugie źródło prawdy poza
  `polis.rules`.
- **Automatyczne dołączanie niestandardowych rejestracji do katalogu.**
  Odrzucone, ponieważ katalog standardowy nie może deklarować stabilności ani
  dostępności kodu dostarczonego przez użytkownika.
- **Dynamiczny loader pluginów.** Odrzucony jako rozszerzenie zakresu, które
  wymaga osobnych decyzji o odkrywaniu, zaufaniu, błędach i pakowaniu.
- **Spekulacyjne profile źródeł.** Odrzucone do czasu pojawienia się konkretnego
  odbiorcy i osobnych kryteriów zgodności.
- **Przeniesienie dyspozycji automatycznej korekty do katalogu.** Odrzucone,
  ponieważ wybór wykonania nie jest dowodem bezpieczeństwa zachowania.
