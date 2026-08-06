# Weryfikacja dystrybucji runtime'u v1

Ten dokument opisuje odtwarzalne tworzenie i walidację artefaktów gotowych do
publikacji. Buduj jeden wheel i jedno archiwum źródłowe z zatwierdzonego commita:

```console
uv run --locked --extra dev python scripts/prepare_build_wheelhouse.py \
  --lock uv.lock --output build-wheelhouse \
  --manifest build-wheelhouse-manifest.json
uv run --locked --extra dev python -m build --no-isolation --outdir dist
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py \
  --dist dist
mkdir build-smoke-cwd
uv run --locked --extra dev python scripts/verify_distribution_install.py \
  --dist dist --wheelhouse build-wheelhouse \
  --wheelhouse-manifest build-wheelhouse-manifest.json \
  --smoke-cwd build-smoke-cwd
```

Przed publikacją utwórz niezmienny manifest dokładnie tych artefaktów:

```console
uv run python scripts/release_identity.py manifest \
  --source-commit "$(git rev-parse HEAD)" --dist dist \
  --output dist/release-manifest.json
```

## Kontrole metadanych i zawartości

Walidacja sprawdza `License-Expression: MIT`, `License-File: LICENSE`, nazwy i
metadane artefaktów oraz dozwoloną zawartość wheel i sdist. Dystrybucja zawiera
wyłącznie runtime, metadane pakowania, README, licencję, przykład TOML i
zatwierdzoną dokumentację produktu. Nie zawiera materiałów badawczych, danych
prywatnych, korpusów, zużytych holdoutów, eksperymentów ani artefaktów poza
produktem.

Lekkie moduły `polis.evaluation` pozostają dostępne ze względu na zgodność 0.x,
ale duże dane i badania nie są częścią dystrybucji.

## Test dymny czystej instalacji

Zainstalowany CLI utrzymuje granicę procesu UTF-8 dla stdin, stdout i stderr.
Automatyczny test uruchamia go z `PYTHONIOENCODING=cp1252`, przekazuje polski
tekst, dekoduje wynik jako UTF-8 i porównuje go znak w znak. Odtwarza to starsze
środowisko Windows z odziedziczonym kodekiem. Wiersze zachowują natywne dla
platformy zakończenia (`LF` na POSIX i `CRLF` w Windows); kontrakt procesu
ustala kodowanie, a nie systemową konwencję końca wiersza.

`scripts/verify_distribution_install.py` wymaga `--smoke-cwd`: istniejącego,
pustego katalogu poza checkoutem. Sprawdza wheel i sdist, tworząc czyste
środowiska z właściwym dla platformy układem `bin` albo `Scripts`; wszystkie
podprocesy probe/API/CLI z zainstalowanego pakietu działają dokładnie w tym
katalogu. To samo polecenie działa w powłokach POSIX, Windows PowerShell i
`cmd.exe`.
Wheelhouse powstaje przed odcięciem sieci i zawiera dokładnie pięć uniwersalnych
wheelów backendu budowania wskazanych przez `uv.lock`. Instalator następnie
ustawia `PIP_NO_INDEX=1`, kieruje `PIP_FIND_LINKS` do zweryfikowanego
wheelhouse i przez `sitecustomize.py` blokuje `socket.connect`,
`socket.connect_ex` oraz `socket.create_connection`. Dopiero instalacja obu
artefaktów po aktywowaniu tej blokady stanowi dowód pracy offline. Przed
ustawieniem jedynej ścieżki `PYTHONPATH` do blokera weryfikator usuwa odziedziczoną
wartość tej zmiennej.

## Kontrole objęte testami

- `tests/test_distribution_artifacts.py` sprawdza metadane i zawartość
  zbudowanych artefaktów.
- `tests/test_release_distribution_installation.py` sprawdza izolowaną
  instalację wheel i sdist, import oraz granicę CLI UTF-8 przy CP1252.
- `tests/test_offline_verification.py`,
  `tests/test_privacy_dependency_audit.py` i
  `tests/test_dependency_licenses.py` walidują granicę offline, prywatność i
  obowiązki licencyjne przed publikacją.

Zachowaj wraz z wydaniem nazwy artefaktów i skróty SHA-256. Po publikacji
porównaj pobrane skróty z `dist/release-manifest.json` przez
`uv run python scripts/release_identity.py verify-published`. Niezgodność jest
incydentem wydania korygowanym append-only erratum; nie zastępuj opublikowanego
artefaktu ani nie przenoś tagu.

## Chroniony workflow wydania

`.github/workflows/release.yml` przyjmuje wyłącznie ręczne wywołanie. Tryb
`qualify` wiąże zdalny `main` z podanym commitem, buduje dokładnie raz poza
checkoutem i przekazuje jeden bundle zawierający tylko `dist/`, manifest
wydania, wheelhouse i jego manifest. Te same bajty są następnie deklaratywnie
sprawdzane dla CPythonów 3.12–3.14 na Linux, macOS i Windows; lokalna praca
deweloperska i QA pozostają macOS-only i nie zastępują końcowej macierzy.

Tryb `publish` ponownie wiąże repozytorium, commit, wynik oryginalnego runu,
oba manifesty, receipt oraz śledzoną politykę. Dopiero po zatwierdzeniu
środowiska `pypi` kopiuje do `publish/` dokładnie wheel i sdist, a akcja uploadu
nie widzi manifestów ani wheelhouse. Dla `publish` projektowy endpoint PyPI
musi nadal zwracać HTTP 404. Tryb `recover` wymaga natomiast HTTP 200 i dokładnie
jednego pliku wersji zgodnego z manifestem co do nazwy, rozmiaru i SHA-256.
Drugi plik musi być nieobecny oraz wskazany przez `recovery_filename`; tylko on
jest kopiowany do `publish/`. Zero, dwa lub nieznane pliki, niezgodny digest,
rozmiar albo wskazanie już istniejącego pliku zatrzymują recovery bez uploadu.
