# Reguły deterministyczne v1

Definicję tego, co wolno twierdzić o pokryciu kategorii, profilach i dowodach,
opisują [kontrakt pokrycia reguł v1](project/rule-coverage.md) oraz
[ADR-0028](architecture/decisions/0028-conservative-v1-rule-coverage-contract.md).
Liczba źródeł w poniższej tabeli jest snapshotem composition root, a nie miarą
kompletności języka.

`Analyzer` rejestruje dokładnie następujące źródła w stałej kolejności:

| Źródło | Kategoria | Zakres |
| --- | --- | --- |
| `rule:agreement.copula` | `agreement` | lokalna niezgodność łącznika w ograniczonych wzorcach zaimka i czasownika |
| `rule:agreement.copula_ja` | `agreement` | zamknięta konstrukcja `Ja jest` → `jestem`, wyłącznie do przeglądu |
| `rule:agreement.te_zdanie` | `agreement` | zamknięty wzorzec `Te zdanie` → `To zdanie`, z zachowaniem wielkości liter |
| `rule:agreement.te_neuter_noun` | `agreement` | zamknięty wzorzec `Te` + rzeczownik nijaki (bez `zdanie`/`miasto`) → `To`, z abstencją przed przecinkiem wołacza, wyłącznie do przeglądu |
| `rule:agreement.nominal_group_te_duze_okno` | `agreement` | opcjonalna zamknięta konstrukcja `Te duże okno jest otwarte.` → `To duże okno jest otwarte.`, wyłącznie do przeglądu |
| `rule:agreement.nominal_group_ta_nowy_ksiazka` | `agreement` | opcjonalne lokalne grupy `przymiotnik + rzeczownik`, a przy jednoznacznym demonstratywie także `demonstratyw + przymiotnik + rzeczownik`; minimalna korekta przymiotnika, wyłącznie do przeglądu |
| `rule:agreement.subject_verb_oni_czyta` | `agreement` | opcjonalna zamknięta konstrukcja `Oni czyta książkę.` → `Oni czytają książkę.`, wyłącznie do przeglądu |
| `rule:agreement.subject_verb_my_czyta` | `agreement` | opcjonalna zamknięta konstrukcja `My czyta książkę.` → `My czytamy książkę.`, wyłącznie do przeglądu |
| `rule:inflection.negated_widziec` | `inflection` | zamknięta konstrukcja `Nie widzę samochód.` → `samochodu`, wyłącznie do przeglądu |
| `rule:inflection.negated_widziec_nominal_group` | `inflection` | opcjonalna zamknięta konstrukcja `Nie widzę czerwony samochód.` → `czerwonego samochodu`, wyłącznie do przeglądu |
| `rule:inflection.negated_miec_czas` | `inflection` | zamknięta konstrukcja `Nie mam czas.` → `czasu`, wyłącznie do przeglądu (bez morfologii) |
| `rule:inflection.negated_lubic_kawe` | `inflection` | opcjonalna zamknięta konstrukcja `Nie lubię kawę.` → `kawy`, wyłącznie do przeglądu (wymaga morfologii) |
| `rule:inflection.przygladac_sie_nowy_budynek` | `inflection` | opcjonalna zamknięta konstrukcja `Przyglądam się nowy budynek.` → `Przyglądam się nowemu budynkowi.`, wyłącznie do przeglądu |
| `rule:inflection.government_potrzebowac_pomoc` | `inflection` | opcjonalna zamknięta konstrukcja `Potrzebuję pomoc.` → `Potrzebuję pomocy.`, wyłącznie do przeglądu |
| `rule:inflection.government_szukac_klucz` | `inflection` | opcjonalna zamknięta konstrukcja `Szukam klucz.` → `Szukam klucza.`, wyłącznie do przeglądu |
| `rule:inflection.government_sluchac_radio` | `inflection` | opcjonalna zamknięta konstrukcja `Słucham radio.` → `radia`, wyłącznie do przeglądu |
| `rule:inflection.government_uzywac_telefon` | `inflection` | opcjonalna zamknięta konstrukcja `Używam telefon.` → `telefonu`, wyłącznie do przeglądu |
| `rule:inflection.government_interesowac_sie_historia` | `inflection` | opcjonalna zamknięta konstrukcja `Interesuję się historia.` → `historią`, wyłącznie do przeglądu |
| `rule:inflection.government_byc_nauczyciel` | `inflection` | opcjonalna zamknięta konstrukcja `Jestem nauczyciel.` → `nauczycielem`, wyłącznie do przeglądu |
| `rule:inflection.government_do_sklep` | `inflection` | opcjonalna zamknięta konstrukcja `Idę do sklep.` → `sklepu`, wyłącznie do przeglądu |
| `rule:inflection.government_ufac_lekarz` | `inflection` | opcjonalna zamknięta konstrukcja `Ufam lekarz.` → `lekarzowi`, wyłącznie do przeglądu |
| `rule:inflection.numeral_five_genitive_plural` | `inflection` | zamknięta, zakotwiczona konstrukcja `Pięć książki` → `książek`, wyłącznie do przeglądu |
| `rule:spelling.jestes` | `spelling` | `jestes` → `jesteś` |
| `rule:spelling.napewno` | `spelling` | `napewno` → `na pewno` |
| `rule:spelling.wlasnie` | `spelling` | `wlasnie` → `właśnie` |
| `rule:spelling.zeby` | `spelling` | `zeby` → `żeby` |
| `rule:spelling.wogole` | `spelling` | `wogole` → `w ogóle`, z pominięciem samodzielnych wzmianek w cudzysłowie i kodzie |
| `rule:spelling.wogole_diacritic` | `spelling` | `wogóle` → `w ogóle`, z guardami kontekstu z #338, wyłącznie do przeglądu |
| `rule:spelling.narazie` | `spelling` | `narazie` → `na razie`, z pominięciem samodzielnych wzmianek w cudzysłowie i kodzie |
| `rule:spelling.wziasc` | `spelling` | `wziasc` → `wziąć`, z pominięciem samodzielnych wzmianek w cudzysłowie i kodzie |
| `rule:spelling.wziasc_diacritic` | `spelling` | `wziąść` → `wziąć` (bez mieszanych `wziąśc`/`wziasć`), wyłącznie do przeglądu |
| `rule:spelling.conajmniej` | `spelling` | `conajmniej` → `co najmniej`, wyłącznie do przeglądu |
| `rule:spelling.poprostu` | `spelling` | `poprostu` → `po prostu`, wyłącznie do przeglądu |
| `rule:spelling.pozatym` | `spelling` | `pozatym` → `poza tym`, wyłącznie do przeglądu |
| `rule:spelling.przedewszystkim` | `spelling` | `przedewszystkim` → `przede wszystkim`, wyłącznie do przeglądu |
| `rule:spelling.wkoncu` | `spelling` | `wkońcu`/`wkoncu` → `w końcu`, wyłącznie do przeglądu |
| `rule:spelling.spowrotem` | `spelling` | `spowrotem` → `z powrotem`, wyłącznie do przeglądu |
| `rule:spelling.tymbardziej` | `spelling` | `tymbardziej` → `tym bardziej`, wyłącznie do przeglądu |
| `rule:spelling.naprawde` | `spelling` | `naprawde` → `naprawdę`, wyłącznie do przeglądu |
| `rule:spelling.nie_byc_joint` | `spelling` | zamknięte formy łączne `być` (`niejestem`, `niebędzie`, `niebył`; bez `niejestes`), wyłącznie do przeglądu |
| `rule:spelling.poszlem` | `spelling` | `poszłem` → `poszedłem` (bez `przeszłem`/`przyszłem`), wyłącznie do przeglądu |
| `rule:spelling.wlanczac` | `spelling` | dosłowna mapa `włanczać`/`wyłanczać` → `włączać`/`wyłączać`, wyłącznie do przeglądu |
| `rule:spelling.month_weekday_lowercase` | `spelling` | `w`/`we` + zamknięta forma kalendarzowa z wielkiej litery → mała; abstencja gdy następny token wielką literą (święta), wyłącznie do przeglądu |
| `rule:spelling.proper_adjective_lowercase` | `spelling` | zamknięty przymiotnik narodowościowy po zamkniętym rzeczowniku pospolitym → mała litera, wyłącznie do przeglądu |
| `rule:spelling.sentence_initial_capital` | `spelling` | zamknięty otwieracz zdania po kropce → wielka litera, wyłącznie do przeglądu |
| `rule:syntax.comma_space` | `punctuation` | brakująca spacja po przecinku |
| `rule:syntax.duplicate_comma` | `punctuation` | usuwa drugi przecinek wyłącznie z bezpiecznej pary `,,` |
| `rule:syntax.initial_conditional_comma` | `syntax` | zamknięta konstrukcja `Jeśli pada zostaję w domu.` → `Jeśli pada, zostaję w domu.`, wyłącznie do przeglądu |
| `rule:syntax.initial_temporal_comma` | `syntax` | zamknięte konstrukcje `Gdy/Kiedy …` z brakującym przecinkiem po początkowym zdaniu czasowym, wyłącznie do przeglądu |
| `rule:syntax.comma_before_ze_reporting` | `syntax` | przecinek po zamkniętym czasowniku raportującym/kognitywnym przed `że`, wyłącznie do przeglądu |
| `rule:syntax.comma_before_zeby_purpose` | `syntax` | przecinek po zamkniętym czasowniku wolicjonalnym przed `żeby`/`żebyś`, wyłącznie do przeglądu |
| `rule:syntax.comma_before_bo` | `syntax` | przecinek przed `bo`/`ponieważ`/`gdyż` z zamkniętym zbiorem wykluczeń prekursora, wyłącznie do przeglądu |
| `rule:syntax.list_space` | `syntax` | brakująca spacja po znaczniku listy |
| `rule:syntax.missing_correlative` | `syntax` | lokalna konstrukcja `Im …, bardziej …` z brakującym `tym` |
| `rule:syntax.missing_destination_preposition` | `syntax` | zamknięta konstrukcja `Pojechałem Warszawy.` → `Pojechałem do Warszawy.`, wyłącznie do przeglądu |
| `rule:syntax.missing_reflexive` | `syntax` | trzy lokalne konstrukcje z brakującym `się` |
| `rule:syntax.quote_space` | `punctuation` | brakująca spacja po otwierającym cudzysłowie |
| `rule:syntax.sentence_space` | `punctuation` | brakująca spacja po kropce na granicy zdania |
| `rule:punctuation.abbreviation_dot` | `punctuation` | kropka po zamkniętych skrótach `{itp, itd, tzn}` (`np` trwale wykluczone), wyłącznie do przeglądu |

Reguły `rule:agreement.nominal_group_te_duze_okno`,
`rule:agreement.nominal_group_ta_nowy_ksiazka`,
`rule:agreement.subject_verb_oni_czyta`,
`rule:agreement.subject_verb_my_czyta`,
`rule:inflection.negated_widziec`,
`rule:inflection.negated_widziec_nominal_group`,
`rule:inflection.przygladac_sie_nowy_budynek`,
`rule:inflection.government_potrzebowac_pomoc`,
`rule:inflection.government_szukac_klucz`,
`rule:syntax.initial_conditional_comma`, `rule:syntax.initial_temporal_comma`,
`rule:syntax.missing_correlative`,
`rule:syntax.missing_destination_preposition` i
`rule:syntax.missing_reflexive` działają tylko dla pojedynczego zdania i
pozostają do przeglądu. Reguła `rule:agreement.nominal_group_ta_nowy_ksiazka`
korzysta z Morfeusza również dla lokalnych grup przymiotnik–rzeczownik; zachowuje
minimalny span przymiotnika i abstenuje przy niejednoznaczności, wołaczu,
koordynacji, cytacie, przerwanym demonstratywie przed interpunkcją, nazwie
własnej albo niepełnych danych. Reguły zgody grupy nominalnej i podmiotu z czasownikiem
oraz druga i trzecia z reguł fleksyjnych działają wyłącznie po lokalnym załadowaniu dokładnie Morfeusz2
1.99.15 ze słownikiem
`pl.sgjp.sgjp-2026.06.01` i zakwalifikowaną notą; brak, dryft albo
niejednoznaczność kończy się abstencją. `rule:spelling.napewno`,
`rule:spelling.wogole`, `rule:spelling.narazie`, `rule:spelling.wziasc`
oraz źródła orthography/inflection z #340
również pozostają wyłącznie do przeglądu, dopóki osobne issue nie
zakwalifikują ich dokładnych kluczy polityki
`(source, category, operation, behavior_version, source_policy_version)`. Pozostałe źródła mogą zostać zastosowane automatycznie
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
issue z kryteriami akceptacji.
