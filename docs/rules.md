# Reguły deterministyczne v1

`Analyzer` rejestruje dokładnie następujące źródła w stałej kolejności:

| Źródło | Kategoria | Zakres |
| --- | --- | --- |
| `rule:agreement.copula` | `agreement` | lokalna niezgodność łącznika w ograniczonych wzorcach zaimka i czasownika |
| `rule:agreement.te_zdanie` | `agreement` | zamknięty wzorzec `Te zdanie` → `To zdanie`, z zachowaniem wielkości liter |
| `rule:agreement.nominal_group_te_duze_okno` | `agreement` | opcjonalna zamknięta konstrukcja `Te duże okno jest otwarte.` → `To duże okno jest otwarte.`, wyłącznie do przeglądu |
| `rule:inflection.negated_widziec` | `inflection` | zamknięta konstrukcja `Nie widzę samochód.` → `samochodu`, wyłącznie do przeglądu |
| `rule:inflection.negated_widziec_nominal_group` | `inflection` | opcjonalna zamknięta konstrukcja `Nie widzę czerwony samochód.` → `czerwonego samochodu`, wyłącznie do przeglądu |
| `rule:spelling.jestes` | `spelling` | `jestes` → `jesteś` |
| `rule:spelling.napewno` | `spelling` | `napewno` → `na pewno` |
| `rule:spelling.wlasnie` | `spelling` | `wlasnie` → `właśnie` |
| `rule:spelling.zeby` | `spelling` | `zeby` → `żeby` |
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
`rule:inflection.negated_widziec`,
`rule:inflection.negated_widziec_nominal_group`,
`rule:syntax.initial_conditional_comma`, `rule:syntax.missing_correlative`,
`rule:syntax.missing_destination_preposition` i
`rule:syntax.missing_reflexive` działają tylko dla pojedynczego zdania i
pozostają do przeglądu. Reguła zgody grupy nominalnej i druga z reguł
fleksyjnych działają wyłącznie po lokalnym załadowaniu dokładnie Morfeusz2
1.99.15 ze słownikiem
`pl.sgjp.sgjp-2026.06.01` i zakwalifikowaną notą; brak, dryft albo
niejednoznaczność kończy się abstencją. `rule:spelling.napewno` również pozostaje
wyłącznie do przeglądu, dopóki osobne issue nie zakwalifikuje jego dokładnego
klucza polityki `(source, category, operation, behavior_version,
source_policy_version)`. Pozostałe źródła mogą zostać zastosowane automatycznie
tylko po sprawdzeniu pełnej tożsamości przez politykę `1.2`.
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
