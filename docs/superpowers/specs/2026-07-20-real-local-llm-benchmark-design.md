# Benchmark rzeczywistych lokalnych modeli dla polskiej korekty

## Cel

Wybrać lub odrzucić rzeczywisty lokalny model dla konserwatywnej korekty
polskiej fleksji, składni i interpunkcji na podstawie powtarzalnego benchmarku,
bez dodawania modelu jako zależności pakietu.

## Zakres

Pierwszy pomiar porównuje model polski
`speakleash/Bielik-4.5B-v3.0-Instruct` z `qwen3:4b-instruct`. Każdy kandydat
działa przez lokalną Ollamę, po uprzednim świadomym pobraniu przez użytkownika.
Wagi, cache i wyniki robocze pozostają poza repozytorium.

Wejściem benchmarku jest korpus E2E v2. Przypadki `llm_planned` są pozytywne,
a `negative` mierzą fałszywe poprawki. Model otrzymuje istniejący wersjonowany
prompt i zwraca jedynie istniejący JSON. Wyniki przechodzą tę samą walidację
offsetów, kategorii i minimalnej sugestii co backend pakietu.

## Metryki i decyzja

Raport zapisuje per kandydat i per kategorię: precision, recall, F1, dokładność
pełnej korekty, odsetek poprawnego JSON, medianę/p95 czasu odpowiedzi, pamięć
procesu runtime oraz wynik testu offline po pobraniu. Raport zawiera dokładny
identyfikator modelu, kwantyzację, wersję Ollamy, platformę i parametry
generowania.

Wybór wymaga braku zmiany dowolnego negatywu, poprawnego JSON dla wszystkich
próbek oraz lepszego lub równego wyniku F1 względem alternatywy przy zasobach
obsługiwanych przez M4/16 GB. Gdy żaden kandydat nie spełni warunków, ADR
zapisze brak wyboru; nie wprowadzamy zastępczego modelu do runtime’u.

## Granice odpowiedzialności

Issue #42 tworzy wyłącznie runner eksperymentu, artefakty pomiarowe i decyzję.
Nie zmienia `Analyzer` ani domyślnego backendu. Issue #43 może dodać adapter
produkcyjny dopiero po zaakceptowanym wyniku #42; adapter nie pobiera modelu i
zachowuje awarię backendu jako kontrolowaną, bezpieczną degradację.

## Ryzyka

Ollama nie udostępnia obecnie oficjalnego tagu Bielika w swojej bibliotece,
więc kandydat Bielik może wymagać lokalnego pliku GGUF i jawnego Modelfile.
Jeśli nie będzie dostępny w poprawnej, licencjonowanej i mierzalnej postaci,
raport odnotuje go jako niedostępnego zamiast podstawiać inny wariant.
