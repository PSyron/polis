# Weryfikacja kandydata do wydania

Użyj tej listy kontrolnej, aby utworzyć i zweryfikować możliwego do
zainstalowania kandydata do wydania w ramach `M3-06`. Weryfikacja kandydata
runtime'u obejmuje wspierany runtime offline i nie uruchamia badań nad modelem,
opcjonalnej kwalifikacji modelu, korpusów badawczych ani zużytych holdoutów oraz
od nich nie zależy; opcjonalne badania nad modelem nigdy nie blokują wydania
runtime'u. Ścieżka wydania runtime'u nie wymaga modelu, procesu Java, usługi
sieciowej, korpusu badawczego ani zużytego holdoutu.

## 1) Przygotowanie artefaktu

```console
uv run --locked --extra dev python scripts/verify_prerelease_candidate.py \
  --source-commit "$(git rev-parse HEAD)"
```

Polecenie wykonuje:

- szybkie testy jakości;
- kontrole ruff;
- rygorystyczne mypy;
- budowanie wheel i sdist;
- kontrole metadanych artefaktów;
- test dymny offline;
- jeden manifest wydania dla dokładnie tych plików wheel i sdist, które właśnie
  zbudowało.

Skrypt wypisuje skróty obu artefaktów i zapisuje
`dist/release-manifest.json`. Zanim kandydat zostanie opublikowany, zachowaj ten
jednokrotnie zbudowany, dokładny zestaw artefaktów wraz z jego commitem
źródłowym.

Manifest wiąże autorytatywną wersję z `pyproject.toml`, zgodne nazwy artefaktów i
osadzone metadane oraz skróty SHA-256. Po tym kroku nie buduj artefaktów
ponownie: wyślij wyłącznie pliki nazwane w `dist/release-manifest.json`.

Nadanie nazwy kandydatowi jest jawną operacją wykonywaną wyłącznie podczas
wydania. Przekaż zaobserwowane tagi lokalne i zdalne, tagi wydań GitHub oraz
wersje z indeksu pakietów do kolektora przeznaczonego wyłącznie dla wydania.
Jego szybkie testy używają wstrzykniętych atrap i nie łączą się z siecią:

```console
uv run --locked --extra dev python scripts/release_identity.py candidate \
  --version 0.2.0rc1 --source-commit "$(git rev-parse HEAD)" \
  --latest-published 0.1.0 --release-only --remote origin \
  --github-repo PSyron/polis \
  --package-index-url https://pypi.org/pypi/polis-nlp/json
```

Istniejący tag lokalny lub zdalny, wydanie GitHub, wersja w indeksie pakietów
albo wersja nie większa od najwyższej zaobserwowanej publikacji GitHub lub w
indeksie pakietów blokuje wydanie. Podana wartość `--latest-published` jest
sprawdzana względem tych obserwacji i nie może obniżyć tej granicy.

Aby przeprowadzić kontrole dystrybucji milestone'u M4-03 — czystą instalację
wheel i sdist oraz listę kontrolną publikacji wydania — przejdź do
`docs/distribution-verification.md`.

## 2) Ręczna instalacja artefaktów w czystej lokalizacji testowej

```console
python -m build --no-isolation
python -m pip install --no-deps --target /tmp/polis-candidate dist/*.whl
PYTHONPATH=/tmp/polis-candidate python - <<'PY'
import polis
print(polis.__version__)
print(polis.AnalyzerConfig())
PY
```

## 3) Zapis dowodów

Zapisz dane wyjściowe poleceń, manifest jednokrotnie zbudowanych artefaktów,
nazwy artefaktów i skróty w notatkach milestone'u. Uwzględnij:

- dane wyjściowe polecenia `python -m build`;
- wynik `scripts/verify_distribution_artifacts.py`;
- wynik weryfikacji offline (`tests/test_offline_verification.py`);
- odwołania do publicznych issue.

Dla każdego istniejącego tagu, przed przygotowaniem nowego wydania, uruchom
kontrolę historycznych dowodów porównującą dokładne bajty:

```console
uv run --locked --extra dev python scripts/release_identity.py verify-history \
  --tag v0.1.0 --version 0.1.0
```

Szybkie CI uruchamia równoważną kontrolę wszystkich tagów przez testy tożsamości
wydania; podczas ręcznego sprawdzania użyj `verify-all-history`.

## Znane ograniczenia

- Ta lista kontrolna ogranicza się do kontroli lokalnych i bieżących założeń
  repozytorium.
- Publikacja wydania i wysyłanie do usług zewnętrznych pozostają poza zakresem
  `M3-06`.
