# Kwalifikacja Morfeusz2 jako dostawcy morfologii offline

## Cel

Issue #238 ma rozstrzygnąć, czy dokładnie wskazane wydanie Morfeusz2 nadaje się
do późniejszego, osobnego wdrożenia pierwszej reguły review-only. Kwalifikacja
nie dodaje dostawcy do runtime'u Polis i nie nadaje żadnemu zachowaniu prawa do
automatycznej korekty.

## Granice

- kandydatem jest `morfeusz2==1.99.15` ze słownikiem
  `pl.sgjp.sgjp-2026.06.01`;
- pakiet jest zależnością wyłącznie grupy `dev`; `[project].dependencies`
  pozostaje puste;
- benchmark działa lokalnie, bez sieci, modelu, Javy i LanguageTool;
- kod benchmarku pozostaje w `scripts/`, poza `src/polis` i artefaktami
  dystrybucyjnymi;
- dane kwalifikacyjne są nowym, edytowalnym fixture autorskim CC0-1.0, a nie
  zużytym holdoutem ani chronionym wynikiem badań;
- zaakceptowane ADR-y i `experiments/nlp_dependencies/` pozostają niezmienione.

## Kontrakt danych

Fixture i manifest używają ścisłych, wersjonowanych schematów. Każdy przypadek
podaje wejściową formę, opcjonalny filtr lemmatu i części mowy, dokładne cechy
celu oraz oczekiwany wynik `suggest` albo `abstain`. Loader odrzuca nieznane
pola, duplikaty identyfikatorów, niezgodny hash, niepełny przegląd i inne
tożsamości danych.

Zakres obejmuje trzy pozytywy: fleksję rzeczownika `pomoc`, zamknięty przypadek
rekcji dla `samochód` i zgodę przymiotnika `nowy:A`. Negatywy obejmują formy
już poprawne, złą płeć, niezgodną część mowy, surową wieloznaczność `nowy` bez
filtra oraz nieznane `xyzzyq` raportowane przez dostawcę jako `ign`.

Odpowiedzi Morfeusz2 są niezaufanymi danymi. Adapter benchmarkowy normalizuje i
usuwa identyczne duplikaty, ale nie rozstrzyga wielu różnych analiz ani form.
Brak dokładnie jednego kandydata kończy się abstencją.

## Progi ustalone przed pomiarem

Definicje metryk pochodzą z aktywnego protokołu #229. Zgodnie z fail-closed
ADR-0024 kwalifikacja wymaga:

- `precision = 1.0`;
- `recall = 1.0` dla trzech ograniczonych pozytywów;
- `correction_accuracy = 1.0`;
- `false_alarm_rate = 0.0`;
- abstencji dla wieloznaczności i nieznanego wejścia;
- zgodności tożsamości pakietu, słownika i noty licencyjnej;
- identycznych hashy wyników wszystkich mierzonych powtórzeń.

Czas startu, p50, p95, przepustowość, peak RSS i rozmiar instalacji są
raportowane informacyjnie. Nie wolno po pomiarze zamienić ich w progi ani
dopasować do nich danych.

## Powtarzalność i raport

Dokładne polecenie z issue wykonuje rozgrzewkę i pięć mierzonych powtórzeń.
Hash powtórzenia obejmuje wyłącznie kanoniczne wyniki przypadków. Znormalizowany
digest raportu obejmuje tożsamość dostawcy i danych, wyniki jakości, bramki i
werdykt, lecz pomija czas, RSS, środowisko, kolejność surowych odpowiedzi i
ścieżkę wyjścia. Dwa osobne wykonania muszą dać ten sam digest.

Zakończony `PASS` lub `FAIL` zwraca kod 0 i atomowo zapisuje raport. `FAIL`
jest pełnoprawnym wynikiem kwalifikacji, ale blokuje dalszą integrację.
`INCONCLUSIVE` zwraca kod 3. Błąd wejścia lub kontraktu CLI zwraca kod 2 i nie
narusza istniejącego pliku wyjściowego.

Raport nie zawiera analizowanego tekstu. Zapisuje identyfikatory przypadków,
oczekiwany i rzeczywisty rodzaj wyniku, proponowaną formę, uzasadnienie,
agregaty, hashe i metadane potrzebne do audytu.

## Tożsamość i zgodność

Kwalifikacja jest ważna wyłącznie dla `morfeusz2==1.99.15`, słownika
`pl.sgjp.sgjp-2026.06.01` i SHA-256 noty słownika
`84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`.
Zmiana któregokolwiek elementu kończy się `INCONCLUSIVE`, a przyszły runtime
musi abstainować do czasu nowej kwalifikacji.

PyPI publikuje koła CPython `abi3` dla macOS universal2, Linux manylinux
x86_64 i Windows amd64, bez sdistu. Brak koła Linux arm64/musl oraz brak
udokumentowanej ścieżki budowania ze źródeł ograniczają przenośność i muszą
pozostać widoczne w decyzji. Kod oraz dołączone dane fleksyjne SGJP/Polimorf są
objęte BSD-2-Clause; nie oznacza to objęcia tą licencją całego słownika SGJP.

## Interpretacja werdyktu

`PASS` potwierdza jedynie zdolność kandydata do bounded candidate generation i
pozwala rozpocząć osobne issue pierwszego konsumenta review-only. `FAIL` albo
`INCONCLUSIVE` zatrzymuje ścieżkę B z #236. Żaden wynik #238 nie dodaje reguły,
adaptera produkcyjnego ani uprawnienia automatycznej korekty.
