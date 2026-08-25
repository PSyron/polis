# #432 — dowód dystrybucji `polis.evaluation`

## Zakres

Ten raport jest trwałym, wersjonowanym dowodem decyzji z ADR-0031. Potwierdza,
że do wydania 1.0 `polis.evaluation` pozostaje w wheel i sdist, a obszar
badawczy pozostaje poza artefaktami runtime'u.

## Powiązane identyfikatory

- Issue: #432
- Decyzja: [ADR-0031](../architecture/decisions/0031-polis-evaluation-distribution-through-1-0.md)
- Bazowy merge #426: `e3ee9b7353b614d8aecad48b75011eb1ddaadee2`
- Commit weryfikowany przez PR #448: `c59e935c1b73423a46d919fd651c324185492a7f`
- Procedura: [weryfikacja dystrybucji runtime'u v1](../distribution-verification.md)

## Odtworzenie

W czystym checkoutcie zatwierdzonego commita wykonano:

```console
uv build --wheel --sdist
uv run --extra dev python scripts/verify_distribution_artifacts.py --dist dist
uv run --extra dev pytest tests/test_distribution_artifacts.py tests/test_release_distribution_installation.py -q
```

Wynik pomiaru:

| Artefakt | Zawartość `polis/evaluation/` | Wynik |
| --- | ---: | --- |
| wheel | 50 plików, 882178 bajtów po rozpakowaniu | metadane MIT, licencja i importy poprawne |
| sdist | 50 plików | zawartość i metadane poprawne |

Testy instalacji izolowanej potwierdziły import kontraktu, dokładne 18
eksportów `polis.evaluation.__all__` i uruchomienie CLI ewaluacji. Kontrola
zawartości potwierdziła, że kalibracja, holdout, generator syntetyczny i dane
badawcze nie trafiają do artefaktów dystrybucyjnych.

Artefakty budowania pozostają tymczasowe i są odtwarzane z commita; do repozytorium
trafiają wyłącznie ten raport, manifest decyzji i testy kontraktu. Dzięki temu
raport nie staje się kopią wheel ani sdist.
