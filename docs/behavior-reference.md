# Referencja zachowania runtime'u

Ten plik jest krótką, utrzymywaną referencją obserwowalnego zachowania
publicznego API Polis. Każdy wiersz pokazuje rzeczywiste wejście do
`Analyzer.analyze(...)`, finding oraz wynik po jawnym zastosowaniu jego
identyfikatora przez `AnalysisResult.apply(...)`.

`Analyzer.correct(...)` automatycznie stosuje tylko wpisy dopuszczone przez
politykę korekty. Findingi `review-only`, w tym wszystkie nowe reguły, pozostają
bez zmiany do chwili jawnego zastosowania. Zakresy w kolumnie `Finding` są
półotwarte `[start, end)` i odnoszą się do oryginalnego tekstu.

Wiersze oznaczone `†` wymagają dokładnie zakwalifikowanego lokalnego Morfeusza.
Przy braku providera, jego dryfcie, niepełnych danych albo niejednoznaczności
runtime abstenuje: nie zwraca findingu, a wynik pozostaje równy wejściu.

## Zgoda

| Źródło | Wejście | Finding `[start, end)` | Wyjście po jawnym zastosowaniu |
| --- | --- | --- | --- |
| `rule:agreement.copula` | `Ty jest gotowy.` | `jest` → `jesteś` `[3, 7)` | `Ty jesteś gotowy.` |
| `rule:agreement.copula_ja` | `Ja jest gotowy.` | `jest` → `jestem` `[3, 7)` | `Ja jestem gotowy.` |
| `rule:agreement.te_zdanie` | `Te zdanie jest krótkie.` | `Te zdanie` → `To zdanie` `[0, 9)` | `To zdanie jest krótkie.` |
| `rule:agreement.te_neuter_noun` | `Te okno jest otwarte.` | `Te` → `To` `[0, 2)` | `To okno jest otwarte.` |
| `rule:agreement.nominal_group_te_duze_okno` † | `Te duże okno jest otwarte.` | `Te` → `To` `[0, 2)` | `To duże okno jest otwarte.` |
| `rule:agreement.nominal_group_ta_nowy_ksiazka` † | `Ta nowy książka.` | `nowy` → `nowa` `[3, 7)` | `Ta nowa książka.` |
| `rule:agreement.subject_verb_oni_czyta` † | `Oni czyta książkę.` | `czyta` → `czytają` `[4, 9)` | `Oni czytają książkę.` |
| `rule:agreement.subject_verb_my_czyta` † | `My czyta książkę.` | `czyta` → `czytamy` `[3, 8)` | `My czytamy książkę.` |
| `rule:agreement.subject_verb_present` † | `Oni mieszka w Warszawie.` | `mieszka` → `mieszkają` `[4, 11)` | `Oni mieszkają w Warszawie.` |

## Fleksja i rekcja

| Źródło | Wejście | Finding `[start, end)` | Wyjście po jawnym zastosowaniu |
| --- | --- | --- | --- |
| `rule:inflection.negated_widziec` | `Nie widzę samochód.` | `samochód` → `samochodu` `[10, 18)` | `Nie widzę samochodu.` |
| `rule:inflection.negated_widziec_nominal_group` † | `Nie widzę czerwony samochód.` | `czerwony samochód` → `czerwonego samochodu` `[10, 27)` | `Nie widzę czerwonego samochodu.` |
| `rule:inflection.negated_miec_czas` | `Nie mam czas.` | `czas` → `czasu` `[8, 12)` | `Nie mam czasu.` |
| `rule:inflection.negated_lubic_kawe` † | `Nie lubię kawę.` | `kawę` → `kawy` `[10, 14)` | `Nie lubię kawy.` |
| `rule:inflection.przygladac_sie_nowy_budynek` † | `Przyglądam się nowy budynek.` | `nowy budynek` → `nowemu budynkowi` `[15, 27)` | `Przyglądam się nowemu budynkowi.` |
| `rule:inflection.government_potrzebowac_pomoc` † | `Potrzebuję pomoc.` | `pomoc` → `pomocy` `[11, 16)` | `Potrzebuję pomocy.` |
| `rule:inflection.government_szukac_klucz` † | `Szukam samochód.` | `samochód` → `samochodu` `[7, 15)` | `Szukam samochodu.` |
| `rule:inflection.government_sluchac_radio` † | `Słucham radio.` | `radio` → `radia` `[8, 13)` | `Słucham radia.` |
| `rule:inflection.government_uzywac_telefon` † | `Używam nowy telefon.` | `nowy telefon` → `nowego telefonu` `[7, 19)` | `Używam nowego telefonu.` |
| `rule:inflection.government_interesowac_sie_historia` † | `Interesuję się polska historia.` | `polska historia` → `polską historią` `[15, 30)` | `Interesuję się polską historią.` |
| `rule:inflection.government_byc_nauczyciel` † | `Jestem nauczyciel.` | `nauczyciel` → `nauczycielem` `[7, 17)` | `Jestem nauczycielem.` |
| `rule:inflection.government_do_sklep` † | `Idę do duży sklep.` | `duży sklep` → `dużego sklepu` `[7, 17)` | `Idę do dużego sklepu.` |
| `rule:inflection.government_ufac_lekarz` † | `Ufam nowy lekarz.` | `nowy lekarz` → `nowemu lekarzowi` `[5, 16)` | `Ufam nowemu lekarzowi.` |
| `rule:inflection.numeral_five_genitive_plural` | `Pięć książki leży na stole.` | `książki` → `książek` `[5, 12)` | `Pięć książek leży na stole.` |

## Pisownia

| Źródło | Wejście | Finding `[start, end)` | Wyjście po jawnym zastosowaniu |
| --- | --- | --- | --- |
| `rule:spelling.jestes` | `Jestes gotowy.` | `Jestes` → `Jesteś` `[0, 6)` | `Jesteś gotowy.` |
| `rule:spelling.czyby` | `Czyby to prawda?` | `Czyby` → `Czy by` `[0, 5)` | `Czy by to prawda?` |
| `rule:spelling.arcy_prefix` | `To jest arcy Europa.` | `arcy Europa` → `arcy-Europa` `[8, 19)` | `To jest arcy-Europa.` |
| `rule:spelling.co_niemiara` | `Mamy problemów coniemiara.` | `coniemiara` → `co niemiara` `[15, 25)` | `Mamy problemów co niemiara.` |
| `rule:spelling.napewno` | `Napewno przyjdę.` | `Napewno` → `Na pewno` `[0, 7)` | `Na pewno przyjdę.` |
| `rule:spelling.wlasnie` | `Wlasnie wróciłem.` | `Wlasnie` → `Właśnie` `[0, 7)` | `Właśnie wróciłem.` |
| `rule:spelling.zeby` | `Zeby zdążyć, wyjdę wcześniej.` | `Zeby` → `Żeby` `[0, 4)` | `Żeby zdążyć, wyjdę wcześniej.` |
| `rule:spelling.wogole` | `Wogole tego nie pamiętam.` | `Wogole` → `W ogóle` `[0, 6)` | `W ogóle tego nie pamiętam.` |
| `rule:spelling.wogole_diacritic` | `Wogóle tego nie pamiętam.` | `Wogóle` → `W ogóle` `[0, 6)` | `W ogóle tego nie pamiętam.` |
| `rule:spelling.narazie` | `Narazie zostaję w domu.` | `Narazie` → `Na razie` `[0, 7)` | `Na razie zostaję w domu.` |
| `rule:spelling.wziasc` | `Chcę wziasc parasol.` | `wziasc` → `wziąć` `[5, 11)` | `Chcę wziąć parasol.` |
| `rule:spelling.wziasc_diacritic` | `Chcę wziąść parasol.` | `wziąść` → `wziąć` `[5, 11)` | `Chcę wziąć parasol.` |
| `rule:spelling.conajmniej` | `To potrwa conajmniej godzinę.` | `conajmniej` → `co najmniej` `[10, 20)` | `To potrwa co najmniej godzinę.` |
| `rule:spelling.poprostu` | `Poprostu nie wiem.` | `Poprostu` → `Po prostu` `[0, 8)` | `Po prostu nie wiem.` |
| `rule:spelling.pozatym` | `Pozatym mam czas.` | `Pozatym` → `Poza tym` `[0, 7)` | `Poza tym mam czas.` |
| `rule:spelling.przedewszystkim` | `Przedewszystkim odpocznij.` | `Przedewszystkim` → `Przede wszystkim` `[0, 15)` | `Przede wszystkim odpocznij.` |
| `rule:spelling.wkoncu` | `Wkońcu wróciłem.` | `Wkońcu` → `W końcu` `[0, 6)` | `W końcu wróciłem.` |
| `rule:spelling.spowrotem` | `Wrócę spowrotem jutro.` | `spowrotem` → `z powrotem` `[6, 15)` | `Wrócę z powrotem jutro.` |
| `rule:spelling.tymbardziej` | `Tymbardziej że pada.` | `Tymbardziej` → `Tym bardziej` `[0, 11)` | `Tym bardziej że pada.` |
| `rule:spelling.naprawde` | `Naprawde tak było.` | `Naprawde` → `Naprawdę` `[0, 8)` | `Naprawdę tak było.` |
| `rule:spelling.nie_byc_joint` | `Niejestes gotowy.` | `Niejestes` → `Nie jesteś` `[0, 9)` | `Nie jesteś gotowy.` |
| `rule:spelling.poszlem` | `Poszłem do sklepu.` | `Poszłem` → `Poszedłem` `[0, 7)` | `Poszedłem do sklepu.` |
| `rule:spelling.wlanczac` | `Włanczać światło.` | `Włanczać` → `Włączać` `[0, 8)` | `Włączać światło.` |
| `rule:spelling.month_weekday_lowercase` | `Spotkamy się w Poniedziałek.` | `Poniedziałek` → `poniedziałek` `[15, 27)` | `Spotkamy się w poniedziałek.` |
| `rule:spelling.proper_adjective_lowercase` | `Uczę się języka Polskiego.` | `Polskiego` → `polskiego` `[16, 25)` | `Uczę się języka polskiego.` |
| `rule:spelling.sentence_initial_capital` | `To działa. potem wróciłem.` | `potem` → `Potem` `[11, 16)` | `To działa. Potem wróciłem.` |

## Składnia i interpunkcja

| Źródło | Wejście | Finding `[start, end)` | Wyjście po jawnym zastosowaniu |
| --- | --- | --- | --- |
| `rule:syntax.comma_space` | `Dzień dobry,wszystko dobrze.` | `,` → `, ` `[11, 12)` | `Dzień dobry, wszystko dobrze.` |
| `rule:syntax.duplicate_comma` | `Dzień dobry,, wszystko dobrze.` | `,` → `""` `[12, 13)` | `Dzień dobry, wszystko dobrze.` |
| `rule:syntax.initial_conditional_comma` | `Jeśli pada zostaję w domu.` | `""` → `,` `[10, 10)` | `Jeśli pada, zostaję w domu.` |
| `rule:syntax.initial_temporal_comma` | `Gdy pada zostaję w domu.` | `""` → `,` `[8, 8)` | `Gdy pada, zostaję w domu.` |
| `rule:syntax.comma_before_ze_reporting` | `Wiem że przyjdziesz.` | `""` → `,` `[4, 4)` | `Wiem, że przyjdziesz.` |
| `rule:syntax.comma_before_zeby_purpose` | `Chcę żebyś przyszedł.` | `""` → `,` `[4, 4)` | `Chcę, żebyś przyszedł.` |
| `rule:syntax.comma_before_bo` | `Zostaję bo pada.` | `""` → `,` `[7, 7)` | `Zostaję, bo pada.` |
| `rule:syntax.list_space` | `-pierwszy` + newline + `-drugi` | `""` → ` ` `[1, 1)` oraz `[11, 11)` | `- pierwszy` + newline + `- drugi` |
| `rule:syntax.missing_correlative` | `Im więcej ćwiczę, bardziej rozumiem.` | `""` → `tym ` `[18, 18)` | `Im więcej ćwiczę, tym bardziej rozumiem.` |
| `rule:syntax.missing_destination_preposition` | `Pojechałem Warszawy.` | `""` → `do ` `[11, 11)` | `Pojechałem do Warszawy.` |
| `rule:syntax.missing_reflexive` | `On boi hałasu.` | `""` → ` się` `[6, 6)` | `On boi się hałasu.` |
| `rule:syntax.quote_space` | `On powiedział"zatem."` | `"` → `" ` `[13, 14)` | `On powiedział" zatem."` |
| `rule:syntax.sentence_space` | `Pierwsze zdanie.Drugie zdanie.` | `.` → `. ` `[15, 16)` | `Pierwsze zdanie. Drugie zdanie.` |
| `rule:punctuation.abbreviation_dot` | `Mam np książkę i itp rzeczy.` | `""` → `.` `[20, 20)` | `Mam np książkę i itp. rzeczy.` |

Ta tabela opisuje przykłady, nie pełną gramatykę języka polskiego. Nowe
zachowanie powinno być dopisywane tutaj razem z testem publicznego API, a nie
przez zmianę znaczenia istniejącego wiersza. Reguły pozostają minimalne,
lokalne i fail-closed.
