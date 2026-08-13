# Reguły deterministyczne v1

`Analyzer` rejestruje dokładnie następujące źródła w stałej kolejności:

| Źródło | Kategoria | Zakres |
| --- | --- | --- |
| `rule:agreement.copula` | `agreement` | lokalna niezgodność łącznika w ograniczonych wzorcach zaimka i czasownika |
| `rule:agreement.te_zdanie` | `agreement` | zamknięty wzorzec `Te zdanie` → `To zdanie`, z zachowaniem wielkości liter |
| `rule:agreement.nominal_group_te_duze_okno` | `agreement` | opcjonalna zamknięta konstrukcja `Te duże okno jest otwarte.` → `To duże okno jest otwarte.`, wyłącznie do przeglądu |
| `rule:agreement.subject_verb_oni_czyta` | `agreement` | opcjonalna zamknięta konstrukcja `Oni czyta książkę.` → `Oni czytają książkę.`, wyłącznie do przeglądu |
| `rule:inflection.negated_widziec` | `inflection` | zamknięta konstrukcja `Nie widzę samochód.` → `samochodu`, wyłącznie do przeglądu |
| `rule:inflection.negated_widziec_nominal_group` | `inflection` | opcjonalna zamknięta konstrukcja `Nie widzę czerwony samochód.` → `czerwonego samochodu`, wyłącznie do przeglądu |
| `rule:inflection.government_potrzebowac_pomoc` | `inflection` | opcjonalna zamknięta konstrukcja `Potrzebuję pomoc.` → `Potrzebuję pomocy.`, wyłącznie do przeglądu |
| `rule:spelling.jestes` | `spelling` | `jestes` → `jesteś` |
| `rule:spelling.napewno` | `spelling` | `napewno` → `na pewno` |
| `rule:spelling.wlasnie` | `spelling` | `wlasnie` → `właśnie` |
| `rule:spelling.zeby` | `spelling` | `zeby` → `żeby` |
| `rule:spelling.wogole` | `spelling` | `wogole` → `w ogóle`, z pominięciem samodzielnych wzmianek w cudzysłowie i kodzie |
| `rule:syntax.comma_space` | `punctuation` | brakująca spacja po przecinku |
| `rule:syntax.duplicate_comma` | `punctuation` | usuwa drugi przecinek wyłącznie z bezpiecznej pary `,,` |
| `rule:syntax.initial_conditional_comma` | `syntax` | zamknięta konstrukcja `Jeśli pada zostaję w domu.` → `Jeśli pada, zostaję w domu.`, wyłącznie do przeglądu |
| `rule:syntax.list_space` | `syntax` | brakująca spacja po znaczniku listy |
| `rule:syntax.missing_correlative` | `syntax` | lokalna konstrukcja `Im …, bardziej …` z brakującym `tym` |
| `rule:syntax.missing_destination_preposition` | `syntax` | zamknięta konstrukcja `Pojechałem Warszawy.` → `Pojechałem do Warszawy.`, wyłącznie do przeglądu |
| `rule:syntax.missing_reflexive` | `syntax` | trzy lokalne konstrukcje z brakującym `się` |
| `rule:syntax.quote_space` | `punctuation` | brakująca spacja po otwierającym cudzysłowie |
| `rule:syntax.sentence_space` | `punctuation` | brakująca spacja po kropce na granicy zdania |

Reguły `rule:agreement.nominal_group_te_duze_okno`,
`rule:agreement.subject_verb_oni_czyta`,
`rule:inflection.negated_widziec`,
`rule:inflection.negated_widziec_nominal_group`,
`rule:inflection.government_potrzebowac_pomoc`,
`rule:syntax.initial_conditional_comma`, `rule:syntax.missing_correlative`,
`rule:syntax.missing_destination_preposition` i
`rule:syntax.missing_reflexive` działają tylko dla pojedynczego zdania i
pozostają do przeglądu. Reguły zgody grupy nominalnej i podmiotu z czasownikiem
oraz druga i trzecia z reguł fleksyjnych działają wyłącznie po lokalnym załadowaniu dokładnie Morfeusz2
1.99.15 ze słownikiem
`pl.sgjp.sgjp-2026.06.01` i zakwalifikowaną notą; brak, dryft albo
niejednoznaczność kończy się abstencją. `rule:spelling.napewno` i
`rule:spelling.wogole` również pozostają wyłącznie do przeglądu, dopóki osobne
issue nie zakwalifikują ich dokładnych kluczy polityki `(source, category,
operation, behavior_version, source_policy_version)`. Pozostałe źródła mogą zostać zastosowane automatycznie
tylko po sprawdzeniu pełnej tożsamości przez politykę `1.2`.
Reguła `rule:inflection.government_potrzebowac_pomoc` ma dokładną tożsamość
zachowania `inflection-government-potrzebowac-pomoc/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`
i nie rozszerza rekcji na negację, przyimek, inne leksemy ani zdanie dłuższe od
zatwierdzonej konstrukcji.
`rule:syntax.duplicate_comma` również pozostaje
wyłącznie do przeglądu, dopóki osobne issue nie zakwalifikuje dokładnego klucza
polityki `(rule:syntax.duplicate_comma, punctuation, remove.duplicate_comma,
syntax-duplicate-comma/1.0, 1.2)`. Sama kategoria ani pewność nie nadaje
uprawnienia.
`rule:agreement.te_zdanie` także pozostaje wyłącznie do przeglądu, dopóki
osobna polityka nie zakwalifikuje jej dokładnego klucza `(source, category,
operation, behavior_version, source_policy_version)`.

## Zasady bezpieczeństwa

Reguła zwraca `Finding` ze stabilnym źródłem i minimalną zmianą w zakresie
`[start, end)`. Rejestr waliduje kategorie, źródła, kolejność oraz duplikaty
identyfikatorów. Reguła musi wstrzymać się, gdy potrzebuje interpretacji
znaczenia, kontekstu wykraczającego poza lokalny zapis albo nie ma uzasadnionej
poprawki.

Nowa reguła wymaga bieżącego konsumenta v1, testów regresyjnych i osobnego
issue. Nie dodawaj katalogu ani abstrakcji bez takiego zastosowania.
