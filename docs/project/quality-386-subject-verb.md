# Publiczny dowód #386: zgoda zaimka z czasownikiem

Ten raport opisuje bieżącą, publiczną deltę runtime'u. Nie jest holdoutem,
kalibracją ani twierdzeniem o kompletności polskiej zgody składniowej.

## Tożsamość

- źródło: `rule:agreement.subject_verb_present`;
- kategoria: `agreement`;
- operacja: `replace.subject_verb_person_number`;
- behavior version:
  `agreement-subject-verb-present/1.8+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`;
- provider: dokładnie zakwalifikowany Morfeusz2 `1.99.15`, słownik
  `pl.sgjp.sgjp-2026.06.01` i nota o powyższym SHA-256;
- polityka: `review-only`; `correct()` pomija finding bez jawnego
  `apply_suggestions()`.

Nowa tożsamość jest osobnym źródłem po dwóch istniejących literalnych
consumerach `subject_verb_oni_czyta` i `subject_verb_my_czyta`. Nie zmienia ich
źródeł, wersji ani exact findings.

## Publiczna delta

Wykonywalny dowód znajduje się w
`tests/test_morphology_subject_verb_generalized.py` i obejmuje trzynaście
różnych pozytywów oraz dwadzieścia dziewięć hard negatives. Pozytywy obejmują wszystkie
obsługiwane osoby i liczby zaimków, trzy nowe leksemy czasownikowe (`pracować`,
`pisać`, `robić`), wielkość liter, polskie znaki, negację, separator
interpunkcyjny, powtórzenie i dwa zdania. Każdy finding sprawdza oryginalny
wycinek, sugestię oraz półotwarty zakres `[start, end)` względem wejścia.

| Profil | Pozytywy exact | Hard negatives | False alarms |
| --- | ---: | ---: | ---: |
| qualified Morfeusz | 13 (+ 2 powtórzone wystąpienia) | 29 | 0 |

Hard negatives obejmują formy poprawne, elipsę, podmiot nominalny i
koordynowany, czas przeszły, tryb warunkowy i rozkazujący, cytat, literał,
koordynację predykatów oraz poprawne formy z alternatywną analizą leksykalną
`mieszka` i `lubi`.

Providerowe testy runtime sprawdzają brak providera, dryft tożsamości,
uszkodzony wiersz analizy i uszkodzoną formę generowania. Walidator generatora
obejmuje także poprawne tagi pomocnicze `aglt` i `bedzie` zwracane dla lematu
`być`, a ich niepełne lub zmienione warianty kończą się abstencją. Każdy z tych
przypadków kończy się abstencją. Casing jest odtwarzany wyłącznie na podstawie
oryginalnego tokenu; mieszany casing oraz zdekomponowane znaki Unicode pozostają
bez sugestii. Sugestia obejmuje tylko czasownik.

## Granice

Reguła wymaga jawnego zaimka osobowego, jednego jednoznacznego leksemu
czasownika i tagu `fin:<sg|pl>:<pri|sec|ter>:imperf`; nie prowadzi parsowania
składniowego ani rozstrzygania intencji. Gdy Morfeusz zwraca dodatkowy odczyt
leksykalny poza czasownikiem, reguła abstenuje; wyjątkiem jest wyłącznie lokalny
przyimek z następującym słowem, który rozstrzyga dopuszczony wzorzec typu
`Oni mieszka w Warszawie.`. Wspierane `nie` i pojedynczy lokalny separator nie
rozszerzają zakresu na koordynację. Brak, dryft lub niepełność providera pozostają
fail-closed. Nie dodano wpisu do automatic correction policy, nie zmieniono danych
chronionych ani zachowania offline.
