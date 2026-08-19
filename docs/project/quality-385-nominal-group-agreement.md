# Publiczny dowód #385: zgoda lokalnej grupy nominalnej

Ten raport opisuje bieżący, publiczny dowód zmiany runtime'u z #385. Nie jest
zamrożonym holdoutem, nie zmienia zbioru v4 i nie ustanawia progu jakości.

## Tożsamość

- źródło: `rule:agreement.nominal_group_ta_nowy_ksiazka`;
- kategoria: `agreement`;
- operacja: `replace.adjective_gender`;
- behavior version:
  `agreement-nominal-group-ta-nowy-ksiazka/2.1+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`;
- profil: dokładnie Morfeusz2 `1.99.15`, słownik
  `pl.sgjp.sgjp-2026.06.01`, zakwalifikowana nota o powyższym SHA-256;
- polityka: `review-only`; `correct()` nie stosuje findingu bez jawnego
  `apply_suggestions()`.

Źródło zachowuje istniejącą tożsamość i kolejność composition root. Zmiana
rozszerza jego lokalny zakres z jednego przykładu `Ta nowy książka` na
jednoznaczne grupy przymiotnik–rzeczownik.

## Publiczna delta

Wykonywalny dowód znajduje się w
`tests/test_morphology_agreement_public_evidence.py` i obejmuje osiem nowych
oczekiwanych findingów oraz szesnaście hard negatives. Wynik bieżącego runtime'u:

| Profil | Oczekiwane findingi | Dokładne findingi | Hard negatives | False alarms |
| --- | ---: | ---: | ---: | ---: |
| qualified-morphology | 8 | 8 | 16 | 0 |

Przykłady obejmują zgodność rodzaju, liczby i przypadku, wiele leksemów
przymiotnikowych oraz jednoznaczny demonstratyw `Ta`. Każdy pozytyw sprawdza
`original`, `suggestion` i półotwarty span `[start, end)` względem wejścia.
Kontrolowane pary obejmują poprawioną formę, zgodność bez demonstratywu,
niejednoznaczność nazwy własnej, wieloznaczny pakiet cech w `To duży okno`,
granicę cytatu/literału oraz abstencję przy przerwanym demonstratywie przed
interpunkcją. Nie jest to claim
pełnego pokrycia kategorii; minima kategorii z #364 pozostają wiązane przez
istniejący publiczny kontrakt v4.

## Abstencja i regresja

Brak providera, dryft wersji pakietu, słownika albo noty, uszkodzone wiersze,
nieznane tagi, wiele lemmas, wiele form generowanych, nazwy własne, wołacz,
koordynacja, cytaty i literały dają pusty wynik dla tego źródła. Te granice są
sprawdzone w testach consumer/runtime; osobno pozostają zielone zamknięte
consumery Morfeusza i zachowanie bez providera.

Nie dodano wpisu do automatic correction policy. Tekst testowy jest autorskim,
publicznym materiałem repozytorium i nie pochodzi z holdoutu ani z prywatnego
korpusu.
