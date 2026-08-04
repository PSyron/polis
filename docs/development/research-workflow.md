# Proces badawczy

Polis zachowuje jedno repozytorium z trzema celowymi ścieżkami pytest:

- Szybka ścieżka wyłącznie dla produktu:
  `uv run --locked --extra dev pytest -m "not research and not slow and not model"`
- Ścieżka badawcza:
  `uv run --locked --extra dev pytest -m research`
- Jawna ścieżka slow/model:
  `uv run --locked --extra dev pytest -m "slow or model"`

Wyniki badań nie kwalifikują automatycznie modelu produkcyjnego. Kwalifikacja
nadal zależy od zaakceptowanych bramek, dowodów sprawdzonych przez właściciela i
osobnej decyzji wydania dotyczącej zachowania runtime'u.

Nie uruchamiaj ponownie zużytego jednorazowego holdoutu ani nie dostrajaj na jego
podstawie. Po zarezerwowaniu i ocenieniu holdoutu dalsze prace muszą używać
nowych zatwierdzonych danych albo nowego projektu ewaluacji zatwierdzonego przez
maintainera, zamiast ponownie wykorzystywać zużyty holdout.

Zachowuj proweniencję i dowody w ich właściwych miejscach w repozytorium:

- korpusy i zatwierdzone dane testowe w `tests/fixtures/evaluation/`,
  `tests/fixtures/e2e/` i `data/finetuning/`;
- raporty badawcze i zamrożone dane wejściowe benchmarków obok ich runnerów w
  `experiments/**/report.json`, `experiments/**/config.json` i powiązanych
  katalogach eksperymentów;
- opcjonalne lokalne dowody LanguageTool w
  `experiments/languagetool_stdio_session/` i `third_party/languagetool-pl/`.

Kod badawczy może używać publicznych modeli wyników z `src/polis`, ale kod
analizy runtime'u nie może importować runnerów badawczych, narzędzi składających
benchmarki ani narzędzi pomocniczych kontrolujących holdouty z `experiments/`.
