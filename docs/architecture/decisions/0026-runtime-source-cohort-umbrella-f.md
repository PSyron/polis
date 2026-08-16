# ADR-0026: Docelowa kohorta runtime'u Umbrella F

- Status: Accepted
- Data: 2026-08-16
- Właściciel: Paweł Cyroń
- Issue: #339 (F1.1)
- Parent: #337

## Kontekst

ADR-0025 zamroził dwie niezależne tożsamości kohort: niezmienną kohortę
kwalifikacji (20 wierszy) oraz rozwijaną kohortę runtime'u z celem
`exact-ordered-28` i identyfikatorem `polis-runtime-source-cohort-28-v1`.
Runtime osiągnął ten cel po dostawie ośmiu źródeł z Umbrella E (#305–#312).

Umbrella F (#337) zamierza dodać kolejne zamknięte, review-only źródła po
Wave 0 (#338). Rejestracja 29. źródła przy bramce `exact-ordered-28` jest
odrzucana z założenia. Potrzebna jest więc nowa tożsamość docelowego
composition root obejmująca źródła zaplanowane w #340, #341 i #342, bez
zmiany zakresu historycznej kwalifikacji ani bajtów zamrożonych artefaktów.

Pomiar wydajności po Wave 0 jest zapisany w
`docs/quality-result-wave0-default.json` oraz
`docs/quality-result-wave0-morphology.json`. Progi jakości i wydajności v3
zatwierdza osobny slice F1.3; ten ADR nie ustala progów.

## Co zastępuje ADR-0025, a co pozostaje w mocy

Niniejsza decyzja **zastępuje wyłącznie** następujące elementy ADR-0025:

| Element ADR-0025 | Status po ADR-0026 |
| --- | --- |
| `runtime_source_cohort_id` = `polis-runtime-source-cohort-28-v1` | Zastąpiony |
| `runtime_ordered_sources` = `28` | Zastąpiony |
| `runtime_target_validation` = `exact-ordered-28` | Zastąpiony |
| Docelowa kolejność 28 pozycji runtime'u | Zastąpiona pełną listą 59 pozycji |
| Planowane tożsamości ośmiu dodatków E jako **docelowy** kontrakt runtime'u | Zastąpione: osiem pozycji E jest już dostarczonych i wchodzi w bazę 28; nowe dodatki F są osobną tabelą planowanych tożsamości |

Następujące elementy ADR-0025 **pozostają w mocy bez zmian**:

- cała niezmienna kohorta kwalifikacji (`qualification_cohort_id`, 20 wierszy,
  digest `92717cdeb…`, `qualification_extra_source_handling = reject`);
- zakaz dziedziczenia kwalifikacji i `source_policy_version`;
- reguła, że przyszła promocja automatyczna wymaga nowego datasetu i nowej
  tożsamości eksperymentu z pełnym kluczem ADR-0024;
- stan `review-only` dla nowych źródeł do czasu osobnej kwalifikacji;
- byte-identical zamrożone artefakty #243, #265, #267, #269 oraz dowody E.

ADR-0025 pozostaje historycznym zapisem decyzji o rozdzieleniu kohort i o celu
28. Jego literały `exact-ordered-28` nie są już aktywnym celem composition root
dla dalszej ekspansji.

## Decyzja

### Obserwowalny kontrakt kohort (aktywny)

| Klucz kontraktu | Wartość |
| --- | --- |
| `qualification_cohort_id` | `polis-a-b-qualification-v2-source-cohort-v1` |
| `qualification_ordered_rows` | `20` |
| `qualification_source_snapshot_sha256` | `92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92` |
| `qualification_extra_source_handling` | `reject` |
| `runtime_source_cohort_id` | `polis-runtime-source-cohort-59-v1` |
| `runtime_ordered_sources` | `59` |
| `runtime_target_validation` | `exact-ordered-59` |
| `runtime_base_sources` | `28` |
| `runtime_planned_additions` | `31` |
| `additions_policy_state` | `review-only` |
| `additions_identity_kind` | `planned-runtime-source-identity` |
| `additions_source_policy_version` | `absent` |
| `additions_policy_entry` | `none` |
| `automatic_policy_identity_created` | `false` |
| `qualification_scope_inheritance` | `forbidden` |
| `automatic_requalification` | `new-dataset-and-experiment-identity` |
| `automatic_requalification_exact_key` | `(source, category, operation, behavior_version, source_policy_version)` |
| `source_policy_version_inheritance` | `forbidden` |
| `umbrella_f_delivery_waves` | `340+341+342` |
| `supersedes_runtime_target_of` | `ADR-0025` |

### Niezmienna kohorta kwalifikacji

Bez zmian względem ADR-0025. Digest kanonicznych bajtów 20 wierszy pozostaje
`92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`. Walidatory
kalibracji i holdoutu nadal porównują wyłącznie tę kohortę i odrzucają nadmiar
źródeł runtime'u jako drift.

### Docelowa kohorta runtime'u Umbrella F

`polis-runtime-source-cohort-59-v1` jest tożsamością docelowego composition root
oraz utrzymywanego wykazu w `docs/rules.md` po dostawie #340, #341 i #342.

- Baza: dokładnie 28 źródeł już zarejestrowanych po Umbrella E, w dotychczasowej
  kolejności względnej.
- Dodatki: 31 planowanych źródeł z #340 (17), #341 (7) i #342 (7).
- Walidacja docelowa: `exact-ordered-59` — brak, nadmiar, duplikat, zmiana
  kolejności albo drift planowanej tożsamości źródła jest błędem.
- Do czasu pełnej dostawy composition root i `docs/rules.md` pozostają
  zsynchronizowane na bieżącym stanie częściowym; bramka 59 staje się
  spełniona dopiero po ostatnim źródle F.
- Ten ADR **nie** rejestruje reguł, **nie** zmienia `docs/rules.md` i **nie**
  tworzy wpisów polityki automatycznej.

### Docelowa kolejność kohorty runtime'u (59)

| Pozycja | Source |
| ---: | --- |
| 1 | `rule:agreement.copula` |
| 2 | `rule:agreement.copula_ja` |
| 3 | `rule:agreement.te_zdanie` |
| 4 | `rule:agreement.te_neuter_noun` |
| 5 | `rule:agreement.nominal_group_te_duze_okno` |
| 6 | `rule:agreement.nominal_group_ta_nowy_ksiazka` |
| 7 | `rule:agreement.subject_verb_oni_czyta` |
| 8 | `rule:agreement.subject_verb_my_czyta` |
| 9 | `rule:inflection.negated_widziec` |
| 10 | `rule:inflection.negated_widziec_nominal_group` |
| 11 | `rule:inflection.negated_miec_czas` |
| 12 | `rule:inflection.negated_lubic_kawe` |
| 13 | `rule:inflection.przygladac_sie_nowy_budynek` |
| 14 | `rule:inflection.government_potrzebowac_pomoc` |
| 15 | `rule:inflection.government_szukac_klucz` |
| 16 | `rule:inflection.government_sluchac_radio` |
| 17 | `rule:inflection.government_uzywac_telefon` |
| 18 | `rule:inflection.government_interesowac_sie_historia` |
| 19 | `rule:inflection.government_byc_nauczyciel` |
| 20 | `rule:inflection.government_do_sklep` |
| 21 | `rule:inflection.government_ufac_lekarz` |
| 22 | `rule:inflection.numeral_five_genitive_plural` |
| 23 | `rule:spelling.jestes` |
| 24 | `rule:spelling.napewno` |
| 25 | `rule:spelling.wlasnie` |
| 26 | `rule:spelling.zeby` |
| 27 | `rule:spelling.wogole` |
| 28 | `rule:spelling.wogole_diacritic` |
| 29 | `rule:spelling.narazie` |
| 30 | `rule:spelling.wziasc` |
| 31 | `rule:spelling.wziasc_diacritic` |
| 32 | `rule:spelling.conajmniej` |
| 33 | `rule:spelling.poprostu` |
| 34 | `rule:spelling.pozatym` |
| 35 | `rule:spelling.przedewszystkim` |
| 36 | `rule:spelling.wkoncu` |
| 37 | `rule:spelling.spowrotem` |
| 38 | `rule:spelling.tymbardziej` |
| 39 | `rule:spelling.naprawde` |
| 40 | `rule:spelling.nie_byc_joint` |
| 41 | `rule:spelling.poszlem` |
| 42 | `rule:spelling.wlanczac` |
| 43 | `rule:spelling.month_weekday_lowercase` |
| 44 | `rule:spelling.proper_adjective_lowercase` |
| 45 | `rule:spelling.sentence_initial_capital` |
| 46 | `rule:syntax.comma_space` |
| 47 | `rule:syntax.duplicate_comma` |
| 48 | `rule:syntax.initial_conditional_comma` |
| 49 | `rule:syntax.initial_temporal_comma` |
| 50 | `rule:syntax.comma_before_ze_reporting` |
| 51 | `rule:syntax.comma_before_zeby_purpose` |
| 52 | `rule:syntax.comma_before_bo` |
| 53 | `rule:syntax.list_space` |
| 54 | `rule:syntax.missing_correlative` |
| 55 | `rule:syntax.missing_destination_preposition` |
| 56 | `rule:syntax.missing_reflexive` |
| 57 | `rule:syntax.quote_space` |
| 58 | `rule:syntax.sentence_space` |
| 59 | `rule:punctuation.abbreviation_dot` |

Kolejność względna 28 dostarczonych źródeł E pozostaje zachowana; nowe źródła
są wstawione w blokach kategorii (agreement, inflection, spelling, syntax,
punctuation) zgodnie z #340–#342.

### Planowane tożsamości 31 dodatków Umbrella F

Tabela zamraża `source`, `category`, `operation`, `behavior_version`, emitowane
`confidence`, pozycję oraz stan `review-only`. Nie zawiera
`source_policy_version` i nie tworzy tożsamości polityki automatycznej.

Dostawca morfologii w `behavior_version` (gdy występuje) to dokładnie
Morfeusz2 `1.99.15` ze słownikiem `pl.sgjp.sgjp-2026.06.01` i hashem notice
`84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`, jak w
dostarczonych źródłach E. Drift dostawcy zmienia tożsamość i wymusza abstencję.

| Pozycja | Source | Category | Operation | Behavior version | Confidence | Stan polityki |
| ---: | --- | --- | --- | --- | ---: | --- |
| 2 | `rule:agreement.copula_ja` | `agreement` | `replace.copula_person` | `agreement-copula-ja/1.0` | `0.9` | `review-only` |
| 4 | `rule:agreement.te_neuter_noun` | `agreement` | `replace.pronoun_gender` | `agreement-te-neuter-noun/1.0` | `0.9` | `review-only` |
| 11 | `rule:inflection.negated_miec_czas` | `inflection` | `replace.governed_form` | `inflection-negated-miec-czas/1.0` | `0.9` | `review-only` |
| 12 | `rule:inflection.negated_lubic_kawe` | `inflection` | `replace.governed_form` | `inflection-negated-lubic-kawe/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 16 | `rule:inflection.government_sluchac_radio` | `inflection` | `replace.governed_form` | `inflection-government-sluchac-radio/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 17 | `rule:inflection.government_uzywac_telefon` | `inflection` | `replace.governed_form` | `inflection-government-uzywac-telefon/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 18 | `rule:inflection.government_interesowac_sie_historia` | `inflection` | `replace.governed_form` | `inflection-government-interesowac-sie-historia/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 19 | `rule:inflection.government_byc_nauczyciel` | `inflection` | `replace.governed_form` | `inflection-government-byc-nauczyciel/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 20 | `rule:inflection.government_do_sklep` | `inflection` | `replace.governed_form` | `inflection-government-do-sklep/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 21 | `rule:inflection.government_ufac_lekarz` | `inflection` | `replace.governed_form` | `inflection-government-ufac-lekarz/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393` | `0.9` | `review-only` |
| 22 | `rule:inflection.numeral_five_genitive_plural` | `inflection` | `replace.governed_form` | `inflection-numeral-five-genitive-plural/1.0` | `0.9` | `review-only` |
| 28 | `rule:spelling.wogole_diacritic` | `spelling` | `replace.common_typo` | `spelling-wogole-diacritic/1.0` | `0.98` | `review-only` |
| 31 | `rule:spelling.wziasc_diacritic` | `spelling` | `replace.common_typo` | `spelling-wziasc-diacritic/1.0` | `0.98` | `review-only` |
| 32 | `rule:spelling.conajmniej` | `spelling` | `replace.common_typo` | `spelling-conajmniej/1.0` | `0.98` | `review-only` |
| 33 | `rule:spelling.poprostu` | `spelling` | `replace.common_typo` | `spelling-poprostu/1.0` | `0.98` | `review-only` |
| 34 | `rule:spelling.pozatym` | `spelling` | `replace.common_typo` | `spelling-pozatym/1.0` | `0.98` | `review-only` |
| 35 | `rule:spelling.przedewszystkim` | `spelling` | `replace.common_typo` | `spelling-przedewszystkim/1.0` | `0.98` | `review-only` |
| 36 | `rule:spelling.wkoncu` | `spelling` | `replace.common_typo` | `spelling-wkoncu/1.0` | `0.98` | `review-only` |
| 37 | `rule:spelling.spowrotem` | `spelling` | `replace.common_typo` | `spelling-spowrotem/1.0` | `0.98` | `review-only` |
| 38 | `rule:spelling.tymbardziej` | `spelling` | `replace.common_typo` | `spelling-tymbardziej/1.0` | `0.98` | `review-only` |
| 39 | `rule:spelling.naprawde` | `spelling` | `replace.common_typo` | `spelling-naprawde/1.0` | `0.98` | `review-only` |
| 40 | `rule:spelling.nie_byc_joint` | `spelling` | `replace.common_typo` | `spelling-nie-byc-joint/1.0` | `0.98` | `review-only` |
| 41 | `rule:spelling.poszlem` | `spelling` | `replace.common_typo` | `spelling-poszlem/1.0` | `0.98` | `review-only` |
| 42 | `rule:spelling.wlanczac` | `spelling` | `replace.common_typo` | `spelling-wlanczac/1.0` | `0.98` | `review-only` |
| 43 | `rule:spelling.month_weekday_lowercase` | `spelling` | `replace.case` | `spelling-month-weekday-lowercase/1.0` | `0.9` | `review-only` |
| 44 | `rule:spelling.proper_adjective_lowercase` | `spelling` | `replace.case` | `spelling-proper-adjective-lowercase/1.0` | `0.9` | `review-only` |
| 45 | `rule:spelling.sentence_initial_capital` | `spelling` | `replace.case` | `spelling-sentence-initial-capital/1.0` | `0.9` | `review-only` |
| 50 | `rule:syntax.comma_before_ze_reporting` | `syntax` | `insert.reporting_clause_comma` | `syntax-comma-before-ze-reporting/1.0` | `0.9` | `review-only` |
| 51 | `rule:syntax.comma_before_zeby_purpose` | `syntax` | `insert.purpose_clause_comma` | `syntax-comma-before-zeby-purpose/1.0` | `0.9` | `review-only` |
| 52 | `rule:syntax.comma_before_bo` | `syntax` | `insert.causal_clause_comma` | `syntax-comma-before-bo/1.0` | `0.9` | `review-only` |
| 59 | `rule:punctuation.abbreviation_dot` | `punctuation` | `insert.abbreviation_dot` | `punctuation-abbreviation-dot/1.0` | `0.9` | `review-only` |

Źródła wykluczone weryfikacją adversarialną w #340–#342 (m.in. `spelling.wsumie`,
ogólne `nie_finite_verb_joint`, `syntax.comma_before_ktory`) **nie** wchodzą do
tej kohorty i nie wolno ich rejestrować pod pretekstem wypełnienia luki.

### Mapowanie fal dostawy

| Fala | Issue | Liczba planowanych źródeł | Uwagi |
| --- | --- | ---: | --- |
| Wave 2 | #340 | 17 | ortografia zamknięta + czysta fleksja bez providera |
| Wave 3 | #341 | 7 | przecinki z allowlistą + kapitalizacja/skróty |
| Wave 4 | #342 | 7 | rekcja z kwalifikowanym Morfeusz2; autorytet #236 |

### Brak dziedziczenia kwalifikacji i polityki

Bez zmian względem ADR-0025 i ADR-0024. Żadne z 31 źródeł nie dziedziczy
uprawnień automatycznych. #244 pozostaje zablokowane.

## Konsekwencje

- Composition root może rosnąć do dokładnego celu 59 bez fałszywego rozszerzenia
  kohorty kwalifikacji 20.
- Implementacje #340–#342 muszą rejestrować źródła w kolejności z tej decyzji i
  aktualizować `docs/rules.md` synchronicznie.
- F1.2 tworzy `quality-development-v3` pod ten kontrakt; F1.3 zatwierdza bramki
  z pomiaru #338, nie z progów v2.
- Ten ADR nie zmienia runtime'u, zależności, publicznego API, polityki
  automatycznej ani zamrożonych bajtów dowodów.
- Źródła morfologiczne pozostają dziećmi #236; konflikt z #236 rozstrzyga #236.

## Rozważane alternatywy

- **Pozostawić `exact-ordered-28` i rozszerzać poza kontrakt.** Odrzucono:
  testy i ADR-0025 celowo fail-closed blokują 29. źródło.
- **Przepisać kohortę kwalifikacji z 20 na 59.** Odrzucono: zniszczyłoby
  tożsamość zakończonego eksperymentu A/B.
- **Jedna ruchoma kohorta „bieżący runtime”.** Odrzucono: uniemożliwia
  byte-identical odtworzenie historycznych zobowiązań.
- **Zatwierdzać progi wydajności w tym ADR.** Odrzucono: progi wynikają z
  pomiaru (F1.3), nie z decyzji o tożsamości kohorty.
