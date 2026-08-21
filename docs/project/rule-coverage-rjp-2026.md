# Audyt pokrycia reguł RJP 2026

[`rule-coverage-rjp-2026.json`](rule-coverage-rjp-2026.json) jest utrzymywanym
wykazem zgodności bieżącego runtime'u Polis z opublikowanymi zmianami pisowni i
interpunkcji obowiązującymi od 1 stycznia 2026 r. Artefakt nie jest deklaracją
pełnego pokrycia języka. Rozdziela dwa pytania: czy istniejące źródło ma
udokumentowaną relację do audytowanej normy oraz czy konkretna zmiana ma
obserwowalną, bezpieczną granicę dla v1.

## Zakres i źródła normy

Audyt wiąże dokładnie 63 tożsamości zwróconych przez
`Analyzer(AnalyzerConfig()).source_identity_snapshot`. Wykaz zachowuje
kolejność runtime'u, operację, wersję zachowania, provider, politykę korekty,
status konformancji, publiczne pozytywy, hard negatives, notatkę abstencji i
następną czynność. Bieżący podział to: agreement 9, inflection 14,
punctuation 5, spelling 26 i syntax 9.

`audited_full_sha` oznacza dokładny, rozwiązywalny commit źródłowy, którego
kohort opisuje macierz. Audytowane ścieżki tego commita muszą być identyczne z
bieżącym runtime'em. Walidator sprawdza istnienie commita, kanoniczny digest
snapshotu oraz brak zmian w audytowanej części runtime'u względem SHA:
`analysis`, `analyzer.py`, `core`, `correction`, `rules` i `segmentation`.
Publiczne artefakty ewaluacyjne w `src/polis/evaluation/` nie zmieniają
tożsamości źródeł reguł i są walidowane własnymi skrótami. Późniejsze commity
dokumentacyjne lub CI nie unieważniają audytu, ale zmiana audytowanego runtime'u
względem SHA kończy walidację fail-closed.

Rada Języka Polskiego jest normą dla jawnie wskazanych przypadków pisowni i
interpunkcji, nie dla kompletności źródeł agreement, inflection ani syntax.
Źródła sklasyfikowane jako `syntax` pozostają poza zakresem RJP, chyba że ich
konkretny lokalny wzorzec ma bezpośrednią podstawę w audytowanym przepisie
interpunkcyjnym, jak pięć zamkniętych wzorców przecinkowych wskazanych w
`Część II, pkt 12.1.1`. ADR-0030 zabrania cichego rozszerzania normatywności
RJP poza taką jawną podstawę. Każdy wiersz objęty RJP wskazuje dokładny dokument i lokalizator. Słowniki,
analizy morfologiczne, korpusy, LanguageTool i istniejące przykłady mogą być
wyłącznie dowodem wspierającym albo źródłem przykładu; nie ustanawiają normy.

Audyt uwzględnia wszystkie numerowane zmiany 01-07, 08a-08e, 09a-09b, 10 i 11.
Zmiana 8b jest oznaczona jako wycofana na podstawie komunikatu RJP z 7 listopada
2025 r. i nie może generować kandydata.

## Statusy i granica kandydata

Wiersz źródła opisuje stan istniejący, a wiersz zmiany opisuje decyzję audytową.
`conforming` oznacza zgodność w zakresie, który faktycznie jest objęty
wierszem; nie oznacza kompletności. `change_required` wskazuje udokumentowaną
rozbieżność. `unclear_fail_closed` pozostawia wynik bez sugestii, gdy dane lub
norma nie wystarczają. `not-governed-by-audited-rjp-material` jawnie oddziela
pozostałe kategorie.

Zmiana może wejść do deterministycznego kandydata tylko z dokładną parą form,
kategorią, typem edycji, półotwartym zakresem `[start, end)`, zachowaniem przy
braku providera i przy niejednoznaczności oraz publicznym pozytywem i granicą
negatywną. Wymaganie to wyklucza rozpoznawanie nazw własnych, intencji autora,
wiedzy o świecie i swobodne generowanie. Kandydat zależny od Morfeusza2 musi
wskazywać istniejącą, zakwalifikowaną granicę providera; bez niej pozostaje
abstencją.

W obecnym audycie RJP-03 ma już jedno bieżące, review-only źródło
`rule:spelling.czyby`; jego rekord kandydata zachowuje normatywną granicę i
wykluczenia. Pozostałe wiersze kandydackie dotyczą RJP-04, RJP-09a i RJP-10.
RJP-03 ogranicza zachowanie do dokładnego
zleksykalizowanego przypadku `czyby` i odrzuca pełny zestaw form wymienionych
w §4.5.1(c–d), między innymi `aby`, `ażeby`, `byleby`, `jakby`, `choćby`,
`chociażby`, `gdyby`, `czyżby`, `żeby`, `niby` i `oby`, a także już rozdzielone
`czy by`; RJP-09a ogranicza się do pary `arcy` plus niepoczątkowego celu pisanego
wielką literą i osobno odrzuca przypadek pozycji zdaniowej. RJP-11 pozostaje
niejednoznaczne, ponieważ
`nie lepiej` nie daje bez kontekstu podstawy do automatycznego wyboru
`nielepiej` albo `nienajlepiej`. Pozostałe wiersze są jawnie
`ambiguous_or_non_deterministic`, `outside_supported_categories` albo
`not_applicable_to_analyzed_prose`. To są decyzje dla kolejnych issue, nie
zmiany runtime'u wykonane przez #365. Issue #400 dodaje dla RJP-09a jedno
provider-independent źródło `rule:spelling.arcy_prefix`, ograniczone do
niepoczątkowej pary `arcy` + cel pisany wielką literą; nadal pozostaje ono
wyłącznie review-only. Issue #404 dodaje provider-independent źródło
`rule:spelling.co_niemiara` dla zamkniętej formy `coniemiara` → `co niemiara`,
również wyłącznie review-only; naturalny dialog w cytacie pozostaje analizowany,
ale cytaty metajęzykowe i kodowe, tokeny techniczne, niejednoznaczny casing
i zakresy przerwane abstynują.

## Walidacja i ograniczenia

Walidator:

```console
uv run --locked --extra dev python -m scripts.rule_coverage_rjp_2026
```

wiąże artefakt z pełnym SHA audytowanego drzewa oraz z kanonicznym SHA
uporządkowanego snapshotu runtime'u. Odrzuca brakujące, nadmiarowe i
zduplikowane źródła, drift operacji lub wersji, nieznane kategorie i
disposition, brak referencji RJP, brakujące wiersze zmian oraz niepełne
kandydatury. Testy mutacji są w
`tests/test_rule_coverage_rjp_2026.py`, a ta sama walidacja działa w fast CI.

Artefakt zachowuje również publiczny v3 baseline bez ponownej interpretacji
chronionych dowodów: profil domyślny ma TP/FN/FP `111/59/0`, profil morphology
`151/19/0`, a oba mają zero false alarms na poprawnych przypadkach. Tożsamość
porównania, datasetu i źródłowego commita jest haszowana i sprawdzana jako
regresyjna granica audytu.

Issue #365 nie rejestruje źródeł, nie zmienia zachowania analizatora, nie
promuje automatycznych korekt i nie otwiera danych chronionych ani evidence
research. Wszelkie wdrożenie kandydatów wymaga osobnych issue, testów i
niezależnej oceny granic.
