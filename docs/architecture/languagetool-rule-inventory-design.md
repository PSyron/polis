# Projekt inwentarza polskich reguł LanguageTool

- Status: zaakceptowany dla issue #70
- Data: 2026-07-22
- Właściciel: Paweł Cyroń

## Cel

Ustalić, które dodatkowe upstreamowe polskie reguły LanguageTool 6.8 mogą
bezpiecznie poprawić korektę jednego zdania. Inspekcja nie może rozszerzać
istniejącej produkcyjnej operacji `check` ani jej allowlisty dwóch reguł.

## Alternatywy

1. **Osobna operacja inspekcji — wybrana.** Dodaje jawne żądanie `inspect` do
   lokalnego mostu stdio. Zwraca eksperymentowi wszystkie upstreamowe polskie
   dopasowania, podczas gdy `check` nadal filtruje dokładnie dwa istniejące
   identyfikatory reguł.
2. **Tymczasowe rozszerzenie `check`.** Odrzucone, ponieważ konfiguracja
   eksperymentu mogłaby przeniknąć do zachowania produkcyjnego i unieważnić
   istniejący kontrakt source-policy.
3. **Statyczne parsowanie XML polskiej gramatyki.** Odrzucone, ponieważ same
   definicje reguł nie mierzą zachowania taggera, offsetów, zamienników,
   konfliktów ani chronionych przykładów negatywnych w rzeczywistych zdaniach.

## Izolacja protokołu

`{"operation":"inspect","language":"pl-PL","text":"..."}` jest przyjmowane
wyłącznie przez dołączony proces stdio. Odpowiedź zawiera `operation=inspect`,
przypiętą tożsamość oprogramowania i nieprzefiltrowane dopasowania upstream.
Domyślną operacją pozostaje `check`, która zachowuje obecny kształt odpowiedzi
i emituje wyłącznie `BRAK_PRZECINKA_ZE` oraz `BRAK_PRZECINKA_ZEBY`. Synteza
pozostaje niezmieniona.

Most nigdy nie otrzymuje identyfikatorów korpusu, etykiet, tagów, oczekiwanego
wyniku ani zakresów gold. Python wysyła wyłącznie tekst źródłowy zdania. Surowe
odpowiedzi inspekcji pozostają w ignorowanym prywatnym katalogu roboczym; dowody
zapisane w repozytorium zawierają tylko identyfikatory reguł, liczności, hashe,
czasy i pomiary zasobów.

## Ocena i wybór

Zbiór deweloperski (`development`) zawiera 69 przypadków zdaniowych z corpus v3.
Każdy zamiennik z każdego dopasowania reguły jest normalizowany do półotwartej
edycji w punktach
kodowych Unicode. Reguła nie może wybierać najlepszego zamiennika z użyciem
gold: liczą się wszystkie odrębne proponowane edycje. Reguły bez użytecznych
zamienników trafiają do inwentarza, ale nie mogą uzyskać kwalifikacji.

Raportowane są TP, FP, FN, dokładne wyniki, zmiany chronionych przykładów
negatywnych i kategorie dla każdej reguły. Kandydujący identyfikator reguły
wymaga co najmniej jednego dokładnego TP, precision 1.00 i zera edycji
chronionych przykładów negatywnych. Połączona allowlista kandydatów musi także
zachować precision 1.00, nie mieć konfliktów ani chronionych zmian i tworzyć
wyłącznie edycje poprawne przy zastosowaniu. To badawcze issue nie wprowadza
zmian produkcyjnego kontraktu source-policy.

Allowlista jest zamrażana wraz z korpusem, mostem, konfiguracją i hashami reguł
kandydujących przed holdoutem. Holdout może zostać uruchomiony raz i tylko wtedy,
gdy zbiór deweloperski da niepustą kwalifikującą się allowlistę. W przeciwnym
razie pozostaje nieotwarty.

## Weryfikacja

Szybkie testy obejmują izolację operacji, zamknięte kształty żądań i odpowiedzi,
offsety Unicode, ocenę wszystkich zamienników, wejścia niezależne od gold,
deterministyczny wybór, prywatność raportu i jednorazową rezerwację holdoutu.
Wolne testy budują i uruchamiają rzeczywisty dołączony moduł. Nadal wymagane są
ogólnorepozytoryjne kontrole jakości, dystrybucji i integracji offline.
