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

## LocalGenerationBackend

`LocalGenerationBackend` jest asynchroniczny, ponieważ przyszła granica analizy
musi móc oczekiwać na lokalne generowanie bez posiadania pętli zdarzeń. Przyjmuje
jeden już skonstruowany prompt i zwraca surowy tekst odpowiedzi. Nazwa backendu
jest bezpiecznym stabilnym identyfikatorem kontekstu kontrolowanego błędu; nie
jest wymaganiem dotyczącym nazwy modelu.

Anulowanie i termin wykonania należą do orkiestratora. Backend nie tworzy
timeoutu, ponowienia, walidatora odpowiedzi, znaleziska ani wyniku analizy.
Pozostaje lokalną granicą implementacji: ten protokół nie zezwala na wywołanie
sieciowe, zależność od serwera modeli ani pobranie modelu.

Starsza ścieżka znalezisk przekazuje przez ten protokół jeden płaski prompt dla
zachowania zgodności. Ścieżka specjalistyczna z #59 udostępnia niezależny od
modelu `PromptRequest` w `polis.llm`: dwie uporządkowane wiadomości ról,
zamknięty schemat odpowiedzi, wersje protokołu i schematu, deterministyczne
ustawienia generowania oraz jawne limity. Przyszły adapter runtime'u musi
zastosować do tych wiadomości własny natywny szablon czatu zamiast je spłaszczać.
Żaden z kształtów żądania nie zawiera nazwy runtime'u ani modelu, a dodanie
orkiestracji specjalistycznej nie reinterpretuje po cichu istniejącego kontraktu
płaskiego znaleziska.

Issue #60 dodaje `HybridSuggestionEngine` w `polis.analysis.hybrid`. Silnik
korzysta z wstrzykniętego deterministycznego routera zadań i backendu
specjalistycznego, nigdy z nazwy modelu ani serwera. Zadania używają offsetów
lokalnych dla zdania; zaakceptowane edycje są raz tłumaczone na offsety
oryginalnego akapitu. Niezmieniony wynik kończy się po jednym wywołaniu,
zmieniony wynik otrzymuje jedno wywołanie weryfikatora accept/reject, a każde
wynikowe znalezisko pozostaje wyłącznie sugestią. Opcjonalne awarie zwracają
jawny bezpieczny status, podczas gdy analizator zachowuje znaleziska
deterministyczne i poprawki objęte source-policy.

## LocalFindingBackend

`LocalFindingBackend` jest osobną złożoną granicą lokalną używaną przez pipeline
analizy. Przyjmuje fragment tekstu i zwraca zwalidowane znaleziska lokalne dla
fragmentu. Jego implementacja odpowiada za budowę promptu, walidację surowej
odpowiedzi i walidację polityki ponowień właściwej dla implementacji. Pipeline
odpowiada za iterację fragmentów, przekazywanie wstrzykniętego zegara i funkcji
sleep, tłumaczenie na offsety oryginalnego tekstu oraz kanoniczny publiczny
kontekst błędu.

Nie zastępuje `LocalGenerationBackend`: tamten protokół pozostaje surową granicą
prompt-to-response. Rozdzielenie obu kontraktów pozwala adapterom udostępniać
wyłącznie operację potrzebną ich odbiorcy bez wiązania core z konkretnym
serwerem modeli ani implementacją retry policy.

## MonotonicClock

`MonotonicClock` jest jedyną zależnością czasu wymaganą na tym etapie. Przyszły
orkiestrator wstrzykuje go, aby spójnie obliczyć jeden termin analizy i testować
deterministycznie. Reguły i lokalne backendy nie mają własnych niezależnych
zegarów ani polityk terminów.

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
