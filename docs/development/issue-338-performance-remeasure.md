# #338 Wave 0 — ponowny pomiar wydajności po F0.3

## Cel

Zmierzyć zainstalowany runtime po hardeningu precyzji (F0.1) i single-pass
skanerze literałów (F0.3). Wynik jest wejściem do zatwierdzenia progów v3 w
#339 (F1.3) i **nie** zastępuje zamrożonych artefaktów #317.

## Metoda

- źródło: `git rev-parse HEAD` w momencie pomiaru (commit F0.3);
- wheel z `uv build` z czystego drzewa roboczego;
- Python `3.13.12` (uv-managed), macOS arm64;
- dataset: `quality-development-v2` (SHA kanoniczny bez zmian);
- warmup 1, repetitions 5;
- profil `default`: świeże venv **bez** `morfeusz2`;
- profil `morphology`: świeże venv z `morfeusz2==1.99.15` i kwalifikowanym
  słownikiem SGJP.

## Artefakty

| Plik | Schema | Profil |
| --- | --- | --- |
| `docs/regression-result-wave0-default.json` | `polis.regression-result` v1 | default |
| `docs/regression-result-wave0-morphology.json` | `polis.regression-result` v1 | morphology |

Zamrożone aliasy `docs/quality-result-v2-*.json` oraz
`docs/quality-comparison-v2.json` z #317 pozostają bez zmian (porównanie
względem pre-change baseline'ów v2).

## Wynik jakości

Oba profile: precision `1.0`, false positives `0`.

| Profil | TP | FN | recall |
| --- | --- | --- | --- |
| default | 22 | 24 | 0.478 |
| morphology | 43 | 3 | 0.935 |

Jakość v2 nie spadła względem #317; Wave 0 nie dodaje nowych źródeł.

## Wynik wydajności (zainstalowany wheel)

| Metryka | default Wave 0 | default #317 | morphology Wave 0 | morphology #317 |
| --- | --- | --- | --- | --- |
| p95 latency (ns) | 39167 | 36167 | 197625 | 205750 |
| throughput (cases/s) | 33979 | 37554 | 18262 | 18531 |
| peak RSS (B) | 30572544 | 30425088 | 74366976 | (w limicie #317) |

Single-pass nie przywraca jeszcze absolutnych capów v2 (te i tak były czerwone
po ekspansji 28 źródeł). Pomiar jest bazą do **nowych** progów w F1.3 (#339),
a nie do cichego poluzowania v2.

## Użycie w #339

F1.3 ma wyprowadzić progi wydajności v3 z tych artefaktów wave0 (oraz z
baseline'ów v3 po F1.2), a nie z `regression-threshold-proposal-v2.json`.
