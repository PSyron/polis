# #338 F0.2 — dowód RED→GREEN dla hard-negatives literałów

## Cel

Rozszerzyć korpus hard-negative o konteksty, w których zamknięte reguły
literałowe nie wolno sugerować poprawki, oraz zapisać dowód RED→GREEN dla
trzech zmierzonych fałszywych alarmów `rule:spelling.wogole`.

## Dlaczego osobny fixture

Zamrożony `tests/fixtures/evaluation/polish_correction_corpus_v3.json` ma
kontrakt dokładnej liczby 240 przypadków (60 na warstwę, split 20/40) i nie
jest miejscem na przyrost Wave 0. F0.2 dodaje więc osobny, projektowy korpus:

`tests/fixtures/rules/literal_context_hard_negatives.json`

## RED (runtime `98190f1`, przed F0.1)

| Case id | Wejście | Znalezisko |
| --- | --- | --- |
| `literal_hn_url_wogole` | `https://example.org/wogole/index.html` | `rule:spelling.wogole` `[20, 26)` → `w ogóle` |
| `literal_hn_email_wogole` | `Napisz do mnie: wogole@example.org` | `rule:spelling.wogole` `[16, 22)` → `w ogóle` |
| `literal_hn_quoted_historical_wogole` | `Cytat: „… wogole …”` | `rule:spelling.wogole` `[23, 29)` → `w ogóle` |

## GREEN (po F0.1, commit `b8470bb` / PR #343)

Każdy z powyższych przypadków oraz rozszerzony zestaw (bare domain, query,
e-mail domain, identyfikatory, `zeby` w URL) zwraca zero znalezisk spelling.

Weryfikacja: `tests/test_literal_context_hard_negatives.py`.

## Zakres poza F0.2

- F0.3: skaner jednoprzebiegowy i równoważność findings na v2.
- Ponowny pomiar wydajności z czystego wheel jako wejście do #339.
