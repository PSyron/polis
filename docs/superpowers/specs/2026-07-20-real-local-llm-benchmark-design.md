# Benchmark rzeczywistych lokalnych modeli dla polskiej korekty

## Cel

Wybrać lub odrzucić rzeczywisty lokalny model dla konserwatywnej korekty
polskiej fleksji, składni i interpunkcji na podstawie powtarzalnego benchmarku,
bez dodawania modelu jako zależności pakietu.

## Zakres

Benchmark jest dwustopniowy. Etap szybkościowy mierzy małe kandydaty:
`speakleash/Bielik-1.5B-v3.0-Instruct-GGUF`, `qwen3:0.6b` i `qwen3:1.7b`.
Etap jakościowy porównuje najlepszy mały model z
`speakleash/Bielik-4.5B-v3.0-Instruct-GGUF` i `qwen3:4b-instruct`. Każdy
kandydat działa przez lokalną Ollamę albo `llama-server`, po uprzednim
świadomym pobraniu przez użytkownika. Wagi, cache i wyniki robocze pozostają
poza repozytorium.

Wejściem benchmarku jest korpus E2E v2. Przypadki `llm_planned` są pozytywne,
a `negative` mierzą fałszywe poprawki. Model otrzymuje istniejący wersjonowany
prompt i zwraca jedynie istniejący JSON. Wyniki przechodzą tę samą walidację
offsetów, kategorii i minimalnej sugestii co backend pakietu.

## Metryki i decyzja

Raport zapisuje per kandydat i per kategorię: precision, recall, F1, dokładność
pełnej korekty, odsetek poprawnego JSON, czas do pierwszego tokenu, medianę/p95
czasu odpowiedzi, tokeny na sekundę, pamięć procesu runtime oraz wynik testu
offline po pobraniu. Raport zawiera dokładny identyfikator modelu, kwantyzację,
rozmiar pobranych wag, wersję runtime, platformę i parametry generowania.

Wybór wymaga braku zmiany dowolnego negatywu i poprawnego JSON dla wszystkich
próbek. Spośród modeli spełniających te warunki wybieramy punkt na granicy
Pareto jakość–p95–pamięć–rozmiar; przy porównywalnej jakości preferowany jest
mniejszy i szybszy model. Model 4.5B jest uzasadniony tylko, gdy daje istotnie
lepszy wynik na fleksji lub składni od kandydata 1.5B. Gdy żaden kandydat nie
spełni warunków, ADR zapisze brak wyboru; nie wprowadzamy zastępczego modelu do
runtime’u.

## Granice odpowiedzialności

Issue #42 tworzy wyłącznie runner eksperymentu, artefakty pomiarowe i decyzję.
Nie zmienia `Analyzer` ani domyślnego backendu. Issue #43 może dodać adapter
produkcyjny dopiero po zaakceptowanym wyniku #42; adapter nie pobiera modelu i
zachowuje awarię backendu jako kontrolowaną, bezpieczną degradację.

## Ryzyka

Ollama nie udostępnia obecnie oficjalnego tagu Bielika w swojej bibliotece,
więc kandydaci Bielik wymagają lokalnego pliku GGUF i jawnego Modelfile.
Repozytorium Bielika wymaga też zaakceptowania warunków dostępu przed pobraniem
wag. Jeśli wariant nie będzie dostępny w poprawnej, licencjonowanej i
mierzalnej postaci, raport odnotuje go jako niedostępnego zamiast podstawiać
inny wariant.
