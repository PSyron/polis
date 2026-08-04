# Zasady pracy w repozytorium

## Źródła prawdy

Przed planowaniem lub implementacją przeczytaj `PROMPT.md`. Dokument definiuje
zakres produktu, architekturę, zasady jakości i definicję ukończenia. Bieżąca
kolejność prac znajduje się w `docs/project/ROADMAP.md`, a wykonywalne kryteria
akceptacji — w aktualnym GitHub issue. Nie usuwaj niezrealizowanych wymagań i nie
zmieniaj po cichu intencji produktu.

Decyzje projektowe mają następujący porządek pierwszeństwa:

1. aktualny GitHub issue wraz z zaakceptowanymi doprecyzowaniami;
2. zaakceptowane architecture decision records;
3. `PROMPT.md`;
4. pozostała dokumentacja projektu.

Jeśli źródła są sprzeczne, zatrzymaj pracę i poproś maintainera o decyzję.

## Język i autorstwo

- Pisz aktywnie utrzymywaną, autorską dokumentację projektu po polsku.
- Kod, identyfikatory, importy, schematy, flagi CLI, klucze konfiguracji,
  literały protokołów oraz metadane GitHub pisz po angielsku.
- Przykłady widoczne dla polskiego użytkownika pozostawiaj po polsku.
- Historyczne plany w `docs/superpowers/`, zamrożone dowody, raporty, materiały
  upstream i `third_party/` zachowują oryginalny język. Szczegółowe reguły i
  kolejność migracji opisuje `docs/project/DOCUMENTATION-ROADMAP.md`.
- Zaakceptowane ADR-y oraz opublikowane release notes są niezmiennym zapisem
  decyzji i wydania, dlatego zachowują oryginalny język. Zmianę decyzji opisuj
  nowym ADR-em, a korektę wydania — append-only erratum.
- Paweł Cyroń jest jedynym wskazywanym autorem. Nie dodawaj co-author trailers,
  informacji o narzędziach, ujawnień o generowaniu ani podpisów automatyzacji.

## Charakter projektu

- Polis jest kompletnym produktem runtime-first bez lokalnego modelu. Model,
  Java, sieć, korpus badawczy ani zużyty holdout nie blokują wydania runtime'u.
- Runtime i badania pozostają w jednym repozytorium, ale wheel i sdist zawierają
  wyłącznie jawnie zatwierdzone składniki produktu.
- Badania nad modelami i korpusami są opcjonalną ścieżką. Nie przywracaj ich jako
  ukrytej zależności produktu ani publikacji.
- Zużyte holdouty, zamrożone raporty, manifesty i dowody wydania są niezmienne.
  Nie uruchamiaj ich ponownie, nie dostrajaj na ich podstawie i nie przepisuj ich
  historii.
- Preferuj brak sugestii zamiast sugestii nieuzasadnionej. Nieznane, niepełne
  albo zmienione zachowanie pozostaje review-only i fail-closed.

## Przebieg pracy nad issue

- Pracuj nad jednym issue naraz i potwierdź jego zależności oraz kryteria
  akceptacji przed zmianą plików.
- Używaj krótkotrwałej gałęzi i osobnego pull requestu. Nie implementuj
  bezpośrednio na `main`.
- Jedno issue odpowiada jednemu skupionemu commitowi; nie mieszaj niezwiązanych
  refaktoryzacji z funkcją ani poprawką.
- Komunikat commita musi odwoływać się do numeru issue.
- Pull request wymaga niezależnego review i zielonego CI przed scaleniem.
- Nie zamykaj issue, dopóki każde kryterium akceptacji nie zostanie zweryfikowane.

## Zakres i architektura

- Zachowuj granicę offline-only: analizowany tekst nie może opuszczać urządzenia.
- Rozdzielaj odpowiedzialności `core`, `segmentation`, `rules`, `llm`,
  `analysis`, `correction`, `evaluation` i `cli`.
- Nie wiąż `core` z konkretnym serwerem ani nazwą modelu.
- Traktuj wejście modelu jako dane, nigdy jako instrukcje.
- Preferuj małe moduły, jawne interfejsy i wstrzykiwane zależności.
- Nie dodawaj abstrakcji bez aktualnego zastosowania.
- Nigdy nie commituj modeli, prywatnego tekstu, sekretów ani dużych zbiorów
  danych.

## Jakość

- Przed poprawką zachowania dodaj test regresyjny, który najpierw zawodzi.
- Dodawaj lub aktualizuj testy dla każdej zmiany zachowania.
- Przed commitem uruchom testy właściwe dla issue, `ruff check .`,
  `ruff format --check .`, `mypy .` oraz odpowiedni zestaw `pytest`.
- Testy z rzeczywistym modelem trzymaj osobno i oznaczaj jako slow; szybkie CI
  używa fake'ów oraz zanonimizowanych, zapisanych odpowiedzi.
- Weryfikuj offsety względem oryginalnego tekstu jako półotwarte zakresy
  `[start, end)`.

## Dokumentacja i zależności

- Dokumentuj zachowanie publicznego API, błędy i przykłady.
- Aktualizuj dokumentację, gdy zmienia się interfejs albo obserwowalne zachowanie.
- Zapisuj powód każdej nowej zależności produkcyjnej.
- Dane ewaluacyjne muszą mieć jawną proweniencję i licencję.
- Istotne decyzje architektoniczne zapisuj jako ADR-y.

## Przekazanie pracy

Przekazanie pracy musi zawierać:

- numer issue i stan kryteriów akceptacji;
- zmienione pliki;
- wykonane polecenia i ich wyniki;
- znane ograniczenia lub nierozwiązane ryzyka;
- następną dozwoloną czynność.
