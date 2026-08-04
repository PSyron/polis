# Weryfikacja dystrybucji runtime-first

Ten dokument zapisuje odtwarzalne polecenia służące do tworzenia i walidacji
artefaktów dystrybucji gotowych do publikacji w PyPI.

## Tworzenie artefaktów wydania

Z czystego checkoutu gałęzi `main` uruchom:

```console
python -m build --no-isolation --outdir dist
python scripts/verify_distribution_artifacts.py --dist dist
```

`python -m build` musi utworzyć dokładnie jeden plik wheel i jedno archiwum
źródłowe.

Po zbudowaniu, ale przed jakimkolwiek wysłaniem artefaktów, utwórz jeden
niezmienny manifest z dokładnie tych dwóch plików:

```console
python scripts/release_identity.py manifest \
  --source-commit "$(git rev-parse HEAD)" --dist dist \
  --output dist/release-manifest.json
```

Polecenie odrzuca artefakty, których nazwa pliku lub osadzone metadane pakietu
nie odpowiadają kanonicznej wersji z `pyproject.toml`. Zapisuje w manifeście
SHA-256 każdego pliku; przed wysłaniem nie uruchamiaj kolejnego budowania.

## Kontrole metadanych i zawartości artefaktów

- Sprawdź klucze metadanych:
  - wartością `License-Expression` jest `MIT`;
  - wartością `License-File` jest `LICENSE`.
- Sprawdź, czy długi opis pakietu używa Markdown i czy zawiera tekst pakietu.
- Sprawdź zawartość artefaktów:
  - `LICENSE` znajduje się w wheel i sdist;
  - obecne są `PKG-INFO` w sdist oraz `METADATA` w wheel;
  - obecny jest runtime `src/polis` i wyłącznie jawnie dozwolone dane pakietu;
  - zawartość sdist ogranicza się do wspieranego źródła runtime'u, metadanych
    pakowania, README, licencji, dołączanych przez Hatch metadanych wykluczeń
    VCS, przykładowej konfiguracji TOML, informacji o wydaniu i wybranej
    dokumentacji produktu: publicznego API, szybkiego startu, prywatności i pracy
    offline, zgodności, weryfikacji dystrybucji i kandydata do wydania,
    ograniczeń, personalizacji, kontraktów reguł i segmentacji, kontraktów i
    bramek jakości LLM, przeglądu licencji zależności oraz zaakceptowanych ADR-ów
    runtime'u i pakowania;
  - wykluczone są repozytoryjne testy, eksperymenty, dane do fine-tuningu,
    dostarczony LanguageTool i wynik jego budowania, zapisy planowania SDD,
    skrypty badawcze, raporty benchmarków, listy kontrolne korpusów ewaluacyjnych
    oraz historyczne zapisy planowania projektu;
  - wykluczone są `.jar`, repozytoria Maven, `target/` oraz rozszerzenia
    artefaktów wag modeli.

Wheel i dystrybucja źródłowa zawierają wspierany runtime offline, a nie
przestrzeń roboczą badań. Lekkie moduły `polis.evaluation` pozostają dostępne ze
względu na gwarancję zgodności importów w bieżącej linii 0.x, natomiast duże
korpusy, holdouty, raporty, eksperymenty, zasoby treningowe, testy i dostarczone
artefakty Java nie są dystrybuowane. LanguageTool jest zatem opcjonalnym
komponentem budowanym lokalnie albo usługą na interfejsie loopback dostarczaną
przez wywołującego, nigdy domyślną zależnością Pythona.

## Test dymny czystej instalacji

Zainstalowany interfejs CLI kontroluje granicę procesu UTF-8 dla stdin, stdout i
stderr. Automatyczny test dymny uruchamia go z `PYTHONIOENCODING=cp1252`,
przekazuje polski tekst, dekoduje wyjście jako UTF-8 i sprawdza tekst znak w
znak. Odtwarza to starsze środowisko Windows z odziedziczonym kodekiem,
jednocześnie pozostawiając odpowiedzialność za bezpośrednie wywołania Pythona do
`run()` po stronie wywołującego. Wiersze tekstu zachowują natywne dla platformy
zakończenia (`LF` w systemach POSIX i `CRLF` w Windows); międzyplatformowy
kontrakt procesu ustala ich kodowanie, a nie systemową konwencję końca wiersza.

Uruchom przenośny walidator z katalogu głównego repozytorium:

```console
python scripts/verify_distribution_install.py --dist dist
```

Skrypt sprawdza zarówno wheel, jak i sdist. Tworzy środowiska tymczasowe z
właściwym dla platformy układem `bin` albo `Scripts` oraz ustawia odziedziczone
środowisko CP1252 przez Pythona, dlatego to samo polecenie działa w powłokach
POSIX, Windows PowerShell i `cmd.exe`.

## Kontrole objęte testami

- `tests/test_distribution_artifacts.py` sprawdza metadane i zawartość plików z
  listy dozwolonej w zbudowanych artefaktach, w tym brak wyniku budowania Java i
  dostarczonych komponentów w wheel i sdist.
- `tests/test_release_distribution_installation.py` sprawdza izolowaną
  instalację wheel i sdist oraz zachowanie testów dymnych importu i CLI, w tym
  granicę procesu UTF-8 przy odziedziczonym CP1252.
- `tests/test_privacy_dependency_audit.py` i `tests/test_dependency_licenses.py`
  walidują ograniczenia audytu wydania wymagane przed publikacją.

Domyślna analiza Polis pozostaje oddzielona od opcjonalnego lokalnego wsparcia
LanguageTool: artefakty dystrybucji Pythona nie zawierają OpenJDK, plików
wykonywalnych LanguageTool, pamięci podręcznych Maven ani wygenerowanych plików
JAR.

## Uwagi o wspieranej macierzy

Issue #31 wymaga czystej instalacji i weryfikacji testem dymnym dla wspieranych
konfiguracji wydania. Bieżąca wspierana macierz jest zapisana w
`docs/architecture/decisions/0001-python-platform-licensing-policy.md`; ta
kontrola jest wykonywana dla każdego środowiska w CI i procesie wydania
milestone'u.

## Dane wyjściowe listy kontrolnej publikacji

Zachowaj wraz z informacjami o wydaniu dane wyjściowe poleceń, nazwy wheel i
sdist oraz sumy kontrolne SHA-256. Użyj:

```console
python - <<'PY'
import hashlib
from pathlib import Path

for name in sorted(Path('dist').glob('*')):
    digest = hashlib.sha256(name.read_bytes()).hexdigest()
    print(f"{name.name} {digest}")
PY
```

Wyślij wyłącznie dwa pliki wymienione w `dist/release-manifest.json`. Po
publikacji GitHub Release oraz publikacji w indeksie pakietów pobierz zgłoszone
skróty artefaktów jako obiekt JSON mapujący nazwy plików na zapisane małymi
literami SHA-256, a następnie porównaj je z tym samym manifestem:

```console
python scripts/release_identity.py verify-published \
  --manifest dist/release-manifest.json \
  --published-digests published-digests.json
```

Porównanie wymaga dokładnie tego samego zbioru nazw plików i skrótów.
Niezgodność jest incydentem wydania korygowanym wyłącznie przez dopisanie:
nie przenoś tagu ani nie zastępuj opublikowanego artefaktu. Zapisz erratum, które
wskazuje niezmienny tag i opublikowane skróty.
`docs/release-notes/0.1.0-erratum.md` stanowi precedens dla tej procedury.
