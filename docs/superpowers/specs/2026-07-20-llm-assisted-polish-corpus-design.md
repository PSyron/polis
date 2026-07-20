# Korpus E2E dla korekty polskiej wspieranej przez LLM

## Cel

Zastąpić demonstracyjny korpus E2E wersjonowanym zestawem jakościowym dla minimalnej korekty polskiej. Zestaw rozróżnia zachowania dostępne dziś od oczekiwań dla przyszłego lokalnego LLM oraz chroni poprawne nazwy własne i poprawny, choć nacechowany, szyk zdania.

## Kontekst

Aktualny analizator ma reguły dla kilku literówek, wybranych niezgodności formy czasownika `być` oraz odstępów interpunkcyjnych. Opcjonalny backend `mock-heu` nie jest modelem językowym i nie analizuje fleksji ani składni.

Dokładnym kandydatem do benchmarku jest `speakleash/Bielik-4.5B-v3.0-Instruct`. Przydatność, kwantyzacja i runtime zostaną ocenione w #42. Adapter wybranego rozwiązania jest zakresem #43. Bielik nie jest domyślną zależnością.

## Projekt korpusu

JSON i XML są równoważnymi, ręcznie utrzymywanymi reprezentacjami zestawu `v2`. Każdy przypadek zawiera identyfikator, zdanie wejściowe, minimalne zdanie oczekiwane, opis, tagi, pole `verification` oraz opcjonalny numer `tracking_issue`.

- `rules`: bieżący analizator bez backendu musi dać dokładną korektę.
- `llm_planned`: jest złoty wynik, ale test nie udaje obecnej obsługi; przypadek wskazuje #42 albo #43.
- `negative`: zdanie jest poprawne i nie może dać sugestii.

## Pokrycie i bramki

Przykłady są autorskie i obejmują fleksję imion i nazwisk, zgodę rodzaju i liczby, zdania podrzędne, wtrącenia, wołacz, odstępy przy interpunkcji oraz dopuszczalny nacechowany szyk. Nie normalizujemy zwykłego stylu; korekta zachowuje znaczenie i jest minimalna.

Test porównuje JSON z XML. Przypadki `rules` są testowane end-to-end, `negative` wymagają braku znalezisk, a `llm_planned` wymagają złotego wyniku, kategorii i śledzenia w GitHubie. Prawdziwe wykonanie przypadków przez model nastąpi po #42 i #43.

## Poza zakresem

Ten etap nie pobiera wag modelu, nie wybiera Bielika bez porównania, nie dodaje adaptera sieciowego i nie zmienia publicznego API.
