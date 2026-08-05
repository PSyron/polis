# Protokoły analizatora i lokalnego backendu

Protokoły runtime'u w `polis.core.protocols` definiują granice implementacji;
nie implementują analizy. Używają istniejących niezmiennych modeli
`AnalysisOptions`, `AnalysisResult`, `Finding` i `Source`, dzięki czemu przyszłe
implementacje nie mogą wprowadzić konkurencyjnego formatu wyniku ani znaleziska.

## DeterministicAnalyzer

`DeterministicAnalyzer` jest właścicielem jednego źródła deterministycznego i
synchronicznie zwraca krotkę zwalidowanych wartości `Finding` dla jednego wejścia
i efektywnych opcji. Tworzy go przyszły composition root; nie ma współdzielonego
mutowalnego stanu wywołania i zwraca znaleziska we własnej deterministycznej
kolejności. Nie wywołuje lokalnego generowania, nie scala innych wyników, nie
stosuje poprawek ani nie ponawia pracy. Nie jest zwracany częściowy
`AnalysisResult`. Przyszły
orkiestrator odpowiada za przekształcanie awarii operacyjnych w kontrolowane
błędy z ADR-0003.

## Rule

`Rule` jest osobno rejestrowanym synchronicznym wpisem analizatora
deterministycznego. Jego stabilne źródło musi identyfikować regułę, a sam wpis
zwraca wyłącznie własne zwalidowane znaleziska. Rejestr odpowiada za tworzenie,
cykl życia i kolejność reguł; reguła nie wybiera innych reguł ani nie podejmuje
decyzji o awariach między regułami.

## RuleRegistry

`RuleRegistry` wykonuje skonfigurowane reguły w deterministycznej kolejności dla
jednego wywołania analizy. Jego cykl życia obejmuje konfigurację przed wywołaniem
analizy i użycie tylko do odczytu w trakcie wywołania. Odpowiada za wybór
kategorii i waliduje wyniki zarejestrowanych reguł; nie wywołuje lokalnego
generowania ani nie scala znalezisk lokalnego backendu.

Zastosowanie poprawki automatycznej pozostaje oddzielną decyzją: wynik może ją
otrzymać wyłącznie po spełnieniu przypisanej polityki `source-policy`.

## AnalysisOrchestrator

`AnalysisOrchestrator` opisuje przyszłe synchroniczne i bezpieczne dla pętli
zdarzeń punkty wejścia. Oba przyjmują tekst `str` i efektywne `AnalysisOptions`
oraz zwracają istniejący typ `AnalysisResult`. Orkiestrator odpowiada za cykl
życia zależności, przekazywanie opcji, kanoniczną kolejność, walidację wyniku,
filtrowanie, egzekwowanie terminu, anulowanie i tłumaczenie na kontrolowaną
hierarchię błędów z ADR-0003.

Nie jest zwracany częściowy `AnalysisResult`. Gdy dowolny skonfigurowany
komponent deterministyczny lub lokalny backend ulegnie awarii, przyszła
implementacja zgłasza odpowiedni kontrolowany błąd zamiast zwracać wynik
ukrywający brakującą pracę.

Polityka ponowień celowo nie jest jeszcze protokołem. Nie istnieje zaimplementowane
zachowanie ponowień ani kompletna hierarchia wyjątków runtime'u, którą można by
sparametryzować, a przedwczesna abstrakcja ponowień przypisałaby politykę
klasyfikacji błędów, zanim istnieje jej właściciel. Gdy zachowanie ponowień
zostanie wprowadzone, dedykowane issue musi zdefiniować jego deterministyczne
wejścia, zachowanie anulowania, interakcję z terminem i tłumaczenie błędów
ADR-0003.
