# Dowód zachowania rekcji nominalnej z #387

Ten raport opisuje utrzymywane, publiczne minimum dla generalizacji wybranych
reguł rekcji. Nie uruchamia zużytych holdoutów i nie jest raportem kompletności
języka polskiego.

## Zakres

Zmiana zachowuje istniejące źródła runtime'u i podnosi ich wersję zachowania do
`2.0+` z dokładną tożsamością kwalifikowanego Morfeusza2 1.99.15 oraz słownika
`pl.sgjp.sgjp-2026.06.01`. Tabela jest zamknięta:

| Źródło | Rekcja | Przykład |
| --- | --- | --- |
| `rule:inflection.government_szukac_klucz` | `szukać` + dopełniacz | `Szukam samochód.` → `samochodu` |
| `rule:inflection.government_uzywac_telefon` | `używać` + dopełniacz | `Używam nowy telefon.` → `nowego telefonu` |
| `rule:inflection.government_ufac_lekarz` | `ufać` + celownik | `Ufam nowy lekarz.` → `nowemu lekarzowi` |
| `rule:inflection.government_interesowac_sie_historia` | `interesować się` + narzędnik | `Interesuję się polska historia.` → `polską historią` |
| `rule:inflection.government_do_sklep` | `do` + dopełniacz | `Idę do duży sklep.` → `dużego sklepu` |

Provider musi zwrócić dokładnie jeden leksem rzeczownika pospolitego, spójne
cechy liczby i rodzaju oraz, gdy występuje, dokładnie jeden leksem przymiotnika
o zgodnej liczbie i rodzaju.
Kwalifikowany adapter usuwa wyłącznie identyczne rekordy techniczne zwrócone
przez aktualny słownik; różne analizy, tagi lub formy nie są scalane i kończą
się abstencją.
Synkretyczne tagi jednego leksemu przymiotnika są dopuszczalne tylko wtedy, gdy
jedna cecha liczby i rodzaju rzeczownika rozstrzyga grupę, a forma docelowa jest
jednoznaczna; pozostałe wieloznaczności kończą się abstencją.
Brak providera, drift wersji lub noty, nieznane tagi, niejednoznaczny leksem,
więcej niż jedna forma docelowa, zaimek, nazwa własna, koordynacja, cytat,
brak `się` albo niepełna grupa kończą się abstencją.

## Publiczny delta

## Dowód RED-first

Przed implementacją uruchomiono ten sam publiczny probe na rodzicu
`999a980acb1af9a24a7f2252b1363cb414d41910` (#385). Wszystkie pięć nowych
leksemów miało `finding_count: 0`: `Szukam samochód.`, `Używam nowy telefon.`,
`Ufam nowy lekarz.`, `Interesuję się polska historia.` oraz `Idę do duży sklep.`.
Probe zakończył się niezerowo z raportem `missing_cases` dla tych pięciu wejść.
Po implementacji ten sam kontrakt przechodzi na finalnym SHA; testy celowane i
pełny szybki zestaw potwierdzają wszystkie pięć rodzin.

Test `tests/test_morphology_government_generalized.py` sprawdza osiem pozytywów
z różnymi leksemami, grupą jednowyrazową i `przymiotnik + rzeczownik`, Unicode,
małą i wielką literą, powtórzeniami oraz wieloma zdaniami. Każdy pozytyw ma
dokładnie jeden finding z minimalnym zakresem `[start, end)` i poprawną sugestią.

Ten sam test sprawdza trzydzieści jeden hard negatives: formy już poprawne,
koordynację, cytaty i kod, nazwy własne, brak `się`, zaimek, plik z rozszerzeniem,
wołacz, elipsę (`...` i `…`), niezgodną zgodę przymiotnika z rzeczownikiem oraz
koordynację z `i znów`/`i znowu`, provider absence i cztery warianty provider drift.
Wynik utrzymywanego
minimum to:

| Profil | Pozytywy | Exact findings | Hard negatives z findingiem |
| --- | ---: | ---: | ---: |
| qualified Morfeusz | 8 | 8 | 0 |

Wszystkie findings mają kategorię `inflection`, severity `suggestion`, stabilne
źródło, `replace.governed_form` i pozostają `review-only`. `Analyzer.correct()`
nie stosuje ich samodzielnie; `AnalysisResult.apply_suggestions()` stosuje
wybraną sugestię jawnie i zachowuje offsety względem oryginalnego tekstu.
Historyczny literalny wzorzec `Szukam klucz` zachowuje także niekońcowe użycie
przed przecinkiem; nowe, uogólnione dopełnienia w takim kontekście abstainują.

## Granice dowodu

Dowód jest lokalny i deterministyczny. Nie obejmuje pełnej walencji czasowników,
koordynacji grup, nazw własnych, zaimków, elipsy, semantyki ani innych leksemów
poza zamkniętą tabelą. Runtime pozostaje offline-only, a żadna treść analizowanego
tekstu nie jest wysyłana poza urządzenie. Nowe zachowanie nie zmienia polityki
automatycznych korekt.
