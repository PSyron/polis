# Projekt routingu kategorii zdaniowych

- Status: zaakceptowany dla issue #69
- Data: 2026-07-22
- Właściciel: Paweł Cyroń

## Cel

Zakwalifikować albo odrzucić ścieżkę korekty offline typu rules-first dla jednego
polskiego zdania. Komponenty deterministyczne obsługują pracę nad interpunkcją i
fleksją, którą mogą uzasadnić dowodami źródłowymi. Kompaktowy model lokalny
otrzymuje wyłącznie wstępnie zakwalifikowane zadanie składni szczątkowej. Routing
akapitów i korekta na poziomie akapitu nie należą do tego eksperymentu.

## Rozważane podejścia

### 1. Kategorie deterministyczne z modelem wyłącznie składniowym

Uruchomić przypięty podzbiór reguł LanguageTool dla zakwalifikowanej
interpunkcji, użyć jego taggera i syntezatora jako dowodów dla skończonych form
fleksyjnych oraz wywołać kompaktowy model wyłącznie dla zdania z niezależnie
wykrytym warunkiem składni szczątkowej. To podejście usuwa klasyfikację kategorii
z modelu i zostało wybrane.

### 2. Stworzone w projekcie heurystyki interpunkcji i morfologii

Ponownie zaimplementować w Pythonie więcej wykrywania polskiej gramatyki,
używając LanguageTool wyłącznie jako słownika. Mogłoby to ograniczyć integrację
z Java, lecz powiela sprawdzone zasoby językowe i wymagałoby znacznie
większego korpusu negatywnego do wykazania tej samej precision. Podejście zostało
odrzucone dla issue #69.

### 3. Jedno żądanie modelu właściwe dla każdej kategorii

Wysyłać osobne prompty modelu dotyczące interpunkcji, fleksji i składni.
Podejście odrzucono, ponieważ zużywa wywołania na kategorie obsługiwane przez
dowody deterministyczne, zwiększa opóźnienie i przekracza budżet dwóch wywołań
na zdanie, gdy podejrzewana jest więcej niż jedna kategoria.

## Przepływ danych wyłącznie dla zdań

1. Odrzuć z kwalifikującego się zbioru eksperymentu puste wejście i wejście
   zawierające więcej niż jedno posegmentowane zdanie.
2. Uruchom deterministyczne reguły Polis i przypiętą operację check LanguageTool
   6.8 bez odczytu metadanych korpusu, etykiet focus ani oczekiwanego wyniku.
3. Znormalizuj znaleziska deterministyczne i zastosuj tylko źródła już dozwolone
   przez politykę automatycznych poprawek. Zmierz niezależnie ścieżki
   interpunkcji i fleksji.
4. Wyprowadź jedno okno dowodowe składni szczątkowej z tekstu źródłowego i
   znalezisk deterministycznych. Adresy URL, liczby, tekst cytowany i zakresy
   nazwanych encji są chronione.
5. Jeśli nie istnieje dowód składni szczątkowej, zwróć wynik deterministyczny bez
   wywołania modelu.
6. W przeciwnym razie wyślij jedno żądanie wyłącznie składniowe zawierające
   zdanie, dokładne okno dowodowe, znaleziska deterministyczne i chronione
   zakresy.
7. Zwaliduj zamknięty schemat odpowiedzi i wymagaj niezmienionego tekstu albo
   jednej minimalnej propozycji mieszczącej się w całości wewnątrz okna
   dowodowego i poza chronionymi zakresami.
8. Jeśli istnieje propozycja, przeznacz drugie i ostatnie wywołanie na binarny
   weryfikator. Zaakceptowane edycje modelu pozostają sugestiami do przeglądu i
   nigdy nie są stosowane automatycznie.

## Granica routingu

Router może analizować wyłącznie zdanie wejściowe, offsety segmentów,
znaleziska deterministyczne i lokalną analizę LanguageTool. Nie może analizować
identyfikatorów przypadków, warstwy korpusu, tagów, oczekiwanego wyniku, edycji
gold ani focusu benchmarku. Test musi wykazać, że zmiana etykiet ewaluacyjnych
przy zachowaniu dowodów źródłowych nie zmienia routingu.

Pierwsza implementacja jest celowo wąska. Obsługuje wyłącznie wzorce dowodowe,
które można określić przed ewaluacją i które tworzą jedno jednoznaczne okno
lokalne dla zdania. Nieobsługiwane wejście nie zwraca zadania dla modelu. Należy
preferować brak sugestii zamiast sugestii nieuzasadnionej.

## Macierz modeli

Macierz zbioru deweloperskiego (`development`) jest zamrażana przed wykonaniem i
zawiera najwyżej trzy kompaktowe konfiguracje:

1. `mlx-community/Qwen3-1.7B-4bit` przez lokalny runtime MLX;
2. `speakleash/Bielik-1.5B-v3.0-Instruct-MLX-8bit` przez lokalny runtime MLX;
3. `qwen3:0.6b` przez przypięty lokalny runtime Ollama jako kontrola szybkości.

Każda konfiguracja używa tego samego kontraktu żądania wyłącznie składniowego,
deterministycznej temperatury, limitu odpowiedzi, walidatora zastosowania i
limitu dwóch wywołań. Artefakty i cache modeli pozostają poza repozytorium. Brak
runtime'u lub artefaktu jest jawnym wynikiem unavailable, nigdy niejawnym
pobraniem.

## Scoring i wybór

Zbiór deweloperski (`development`) używa 80 sprawdzonych przypadków z corpus-v3.
Połączony pipeline raportuje deterministyczną interpunkcję, deterministyczną
fleksję i wspomaganą modelem składnię szczątkową zarówno osobno, jak i łącznie.
Routing jest wykonywany bez gold; dane wzorcowe otwiera wyłącznie moduł
oceniający po zapisaniu wyników.

Konfiguracja kwalifikuje się wyłącznie po spełnieniu wszystkich warunków:

- 100% ustrukturyzowanych wyników;
- zero sugestii dla chronionych trudnych przykładów negatywnych;
- precision dokładnej edycji co najmniej 0.90;
- recall co najmniej 0.25 dla każdej kategorii, której obsługę deklaruje
  połączony pipeline;
- warm end-to-end p95 najwyżej 2,000 ms;
- pamięć załadowanego modelu najwyżej 4 GiB;
- przyrost swapu najwyżej 64 MiB;
- nie więcej niż dwa wywołania modelu dla zdania.

Zwycięzca jest wybierany według przejścia bramek, następnie wyższego minimalnego
recall dla wspieranego focusu, niższego warm p95 i niższego zużycia pamięci po
załadowaniu. Wybrana konfiguracja i wszystkie hashe są zamrażane przed
rezerwacją holdoutu. Holdout jest uruchamiany raz i tylko wtedy, gdy każda
bramka zbioru deweloperskiego przechodzi. W przeciwnym razie issue #43 pozostaje
fail-closed.

## Zachowanie przy awarii i ochrona prywatności

Wadliwy wynik, timeout, niedostępny runtime, szerokie przepisanie, zmiana
chronionego zakresu, edycja poza oknem lub niezgodność weryfikatora powodują
odrzucenie propozycji modelu bez usuwania znalezisk deterministycznych.
Kontrolowana diagnostyka zawiera wyłącznie identyfikatory przypadków i metryki
zagregowane. Tekst źródłowy, surowe odpowiedzi modelu, wagi, cache i pliki
robocze właściwe dla maszyny nie są zapisywane w repozytorium.

## Weryfikacja

Szybkie testy obejmują kwalifikowalność zdań, routing niezależny od gold, okna
dowodowe, chronione zakresy, schematy, walidację zastosowania, kolejność wyboru,
raporty chroniące prywatność i zabezpieczenie jednorazowego holdoutu. Rzeczywisty
benchmark zbioru deweloperskiego jest oznaczony jako slow/model. Issue wymaga
także pełnego repozytoryjnego zestawu jakości, kontroli artefaktów dystrybucji i opcjonalnej
integracji dołączonego LanguageTool przed utworzeniem jednego skupionego commita.
