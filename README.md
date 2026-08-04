# Polis

Polis to działająca offline biblioteka Pythona do analizy tekstu w języku
polskim i proponowania minimalnych, ustrukturyzowanych poprawek. Wspieranym
produktem jest niewielki runtime: deterministyczna analiza, zachowawcza korekta,
typowane modele wyników oraz cienki interfejs CLI do użycia ręcznego lub w
skryptach.

Żaden przetestowany model lokalny nie został zakwalifikowany do poprawek ani
sugestii produkcyjnych. Dlatego domyślna instalacja nie wybiera, nie pobiera ani
nie wymaga modelu lokalnego. Prace badawcze i ewaluacyjne pozostają w
repozytorium i opisuje je [przewodnik po procesie badawczym](docs/development/research-workflow.md).
[ADR-0020](docs/architecture/decisions/0020-runtime-first-product-charter.md)
stwierdza, że Polis jest kompletny bez modelu, a opcjonalne badania nad modelem
nigdy nie blokują wydania runtime'u. Ścieżka wydania runtime'u nie wymaga
modelu, procesu Java, usługi sieciowej, korpusu badawczego ani zużytego holdoutu.

## Granica produktu

Domyślna instalacja nie ma zależności produkcyjnych i działa offline. Nie
zawiera adaptera DOCX/ODT/RTF, GUI ani rozbudowanego przepisywania stylistycznego.
`Analyzer.correct()` stosuje wyłącznie znaleziska o wysokiej pewności, bez
konfliktów i objęte bieżącą deterministyczną polityką źródeł. Pozostałe
znaleziska, w tym sugestie wygenerowane przez model i sugestie kontekstowe,
podlegają przeglądowi i wymagają jawnego wyboru przez wywołującego.

Opcjonalna integracja z LanguageTool nie jest zależnością rdzenia. Wywołujący
może jawnie udostępnić osobno uruchomioną usługę na interfejsie loopback albo
lokalnie zbudować przypięty plik wykonywalny z dostarczonych źródeł. Z punktu
widzenia Polis oba tryby działają wyłącznie offline; wspierana ścieżka z
dostarczonych źródeł obsługuje tylko pojedyncze zdania i zachowuje jedynie pięć
zakwalifikowanych reguł przecinkowych. Dostarczone źródła, artefakty Java,
dane testowe do badań, eksperymenty, dane treningowe, testy i zapisy planowania
SDD są wykluczone z artefaktów wheel i dystrybucji źródłowej.

`polis.evaluation` zachowuje zgodność importów dla istniejących narzędzi
pomocniczych ewaluatora w bieżącej linii 0.x, lecz jest repozytoryjnym narzędziem
do ewaluacji, a nie głównym API analizy tekstu. Zobacz
[ADR-0019](docs/architecture/decisions/0019-evaluation-namespace-compatibility.md).

## Zachowawcza korekta

`Analyzer.correct()` przyjmuje pojedyncze zdanie albo akapit składający się z
wielu zdań. Stosuje wyłącznie deterministyczne sugestie o wysokiej pewności i
bez konfliktów oraz zwraca tekst oryginalny i poprawiony wraz z zastosowanymi i
pominiętymi znaleziskami.

```python
from polis import Analyzer, AnalyzerConfig

result = Analyzer(AnalyzerConfig()).correct("Zeby jutro,powiem o tym.")
assert result.corrected_text == "Żeby jutro, powiem o tym."
```

Metoda nie przepisuje tekstu, nie wysyła go przez sieć ani nie stosuje
automatycznie sugestii o niskiej pewności lub wygenerowanych przez model.
`await Analyzer.correct_async(...)` zapewnia ten sam wynik i kolejność w
aplikacjach korzystających z pętli zdarzeń. Jawnie wstrzyknięte opcjonalne
sugestie specjalistyczne pozostają w `skipped_findings` i raportują
wersjonowany wynik wraz z faktycznie wykorzystanym budżetem jednego lub dwóch
wywołań; domyślnie nie jest włączony żaden rzeczywisty model specjalistyczny.

## Opcjonalna ścieżka LanguageTool dla pojedynczego zdania

Aby użyć obecnie wspieranej ścieżki LanguageTool dla pojedynczego zdania,
najpierw jawnie zbuduj przypięty polski podzbiór. Polis nie pobiera środowiska
Java, zależności ani artefaktów w czasie działania:

```console
cd third_party/languagetool-pl
./scripts/build.sh
```

Skonfiguruj bezwzględną ścieżkę do utworzonego pliku wykonywalnego:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Użyj analizatora jako menedżera kontekstu, aby jego jeden trwały lokalny proces
potomny został zakończony w sposób deterministyczny:

```python
from polis import Analyzer

with Analyzer.from_config("polis.toml") as analyzer:
    result = analyzer.correct("Wiem że wróciła.")

assert result.corrected_text == "Wiem, że wróciła."
```

`Analyzer.close()` zapewnia równoważne jawne zamknięcie. `source-policy 1.1`
automatycznie stosuje wyłącznie pięć zakwalifikowanych reguł przecinkowych.
Fleksja kontekstowa nadal podlega przeglądowi i wymaga
`apply_suggestions()`. Usunięcie `[vendored_language_tool]` całkowicie wyłącza
tę ścieżkę opartą na osobnym procesie.

## Konfiguracja środowiska programistycznego

Dystrybucja nosi nazwę `polis-nlp`, a jej przestrzeń nazw importów Pythona to
`polis`. Polis wymaga Pythona 3.12 lub nowszego i dokładnie uv 0.11.2. Na macOS
lub Linuksie zainstaluj tę wersję uv poleceniem:

```console
curl -LsSf https://astral.sh/uv/0.11.2/install.sh | sh
```

W Windows PowerShell użyj:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.11.2/install.ps1 | iex"
```

Sprawdź, czy `uv --version` zwraca `uv 0.11.2`, a następnie odtwórz zablokowane
środowisko programistyczne:

```console
uv sync --locked --extra dev
```

Wszystkie kontrole uruchamiaj w tym samym zablokowanym środowisku:

```console
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev python -m build --no-isolation
```

Jako dodatkową lokalną kontrolę zgodności, poza szybkim CI, można osobno
uruchomić runner z biblioteki standardowej:

```console
uv run --locked --extra dev python -m unittest discover -s tests -v
```

`uv.lock` przypina pełny graf zależności na potrzeby budowania i rozwoju. Użyj
`uv lock --check`, aby sprawdzić jego zgodność z `pyproject.toml`; gdy
zadeklarowane zależności zmieniają się celowo, zaktualizuj go poleceniem
`uv lock`.

## Ciągła integracja

Każdy push i pull request uruchamia szybki zestaw kontroli jakości na
reprezentatywnej macierzy z ADR-0001: Ubuntu x86_64 z CPython 3.12, 3.13 i 3.14;
macOS arm64 z wersjami 3.12 i 3.14; oraz Windows x86_64 z wersjami 3.12 i 3.14.
Odtwarza on zablokowane środowisko programistyczne. Workflow mapuje nazwę
architektury `x86_64` na wartość `x64` wejścia `setup-python`, a `arm64`
przekazuje bez zmian. Uruchamia pytest z wyborem szybkich markerów, kontrolę
lintingu i formatowania Ruff oraz rygorystyczne mypy, a także buduje i sprawdza
oba artefakty dystrybucji pod kątem metadanych licencji MIT i obecności
`LICENSE`. Pytest zbiera również testy zapisane jako `unittest.TestCase`, dlatego
celowo nie ma drugiego, niefiltrowanego uruchomienia testów.

Ten szybki zestaw celowo wyklucza wolne testy, testy z rzeczywistym modelem,
benchmarki, publikowanie wydań i wszystkie zależne od sieci kontrole produktu.
Te obciążenia wymagają własnych, jawnych zadań i pozostają poza kontrolą dla
każdej zmiany. Moduły pytest przeznaczone wyłącznie do badań oznaczaj
`pytest.mark.research`, przypadki wymagające dużych zasobów —
`@pytest.mark.slow`, a testy wymagające rzeczywistego modelu lokalnego —
`@pytest.mark.model`. Szybka kontrola uruchamia `uv run --locked --extra dev
pytest -m "not research and not slow and not model"`; polecenia dla samego
produktu, badań i jawnych testów slow/model opisuje
[przewodnik po procesie badawczym](docs/development/research-workflow.md).

## Modele publiczne

Polis udostępnia obecnie niezmienne modele wyników analizy, deterministyczną,
ściśle wersjonowaną serializację JSON oraz protokoły runtime'u dla przyszłych
analizatorów deterministycznych i backendów generowania lokalnego.
[Kontrakt publicznego modelu analizy](docs/public-api.md) opisuje semantykę pól,
reguły offsetów Unicode, błędy walidacji i zgodność schematu. Sposób sprawdzenia
działania bez sieci opisuje [przewodnik po weryfikacji offline](docs/offline-operation.md).
Bieżące zachowanie i granice
wyjaśniają [przewodnik szybkiego startu](docs/quick-start.md),
[przewodnik po prywatności](docs/privacy.md) i
[ograniczenia](docs/limitations.md).
[Polityka zgodności i wersjonowania semantycznego](docs/compatibility.md)
określa gwarancje stabilności publicznych kontraktów.
[Audyt prywatności i zależności](docs/privacy-audit.md) dokumentuje dowody
bramki wydania. [Lista kontrolna kandydata do wydania](docs/prerelease-candidate.md)
dokumentuje ścieżkę weryfikacji bramki wydania.
[Weryfikacja dystrybucji](docs/distribution-verification.md) opisuje tożsamość
jednokrotnie zbudowanego wydania i kontrole skrótów po publikacji. Dopisywane
wyłącznie na końcu [erratum 0.1.0](docs/release-notes/0.1.0-erratum.md) koryguje
opublikowane dowody skrótów artefaktów bez przepisywania tego wydania.
[Granica protokołów](docs/architecture/protocols.md) opisuje sposób łączenia
bogatszych orkiestratorów i wariantów adapterów wokół stabilnych kontraktów.
[Dziennik zmian](CHANGELOG.md) śledzi historię wydań, a
[informacje o wydaniu](docs/release-notes/0.1.0.md) dokumentują bieżące granice
wsparcia.

## Interfejs wiersza poleceń

Polis dostarcza również cienki interfejs CLI do analizy ręcznej lub skryptowej:

```console
python -m polis.cli analyze --json "Witaj,świecie."   # text argument
printf 'Witaj,świecie.\n' | python -m polis.cli analyze --stdin --json  # stdin input
python -m polis.cli analyze --file input.txt --json      # UTF-8 file input
```

Przydatne opcje:

- `--category`: powtarzalny filtr kategorii znalezisk
- `--minimum-confidence`: minimalny próg pewności
- `--apply <finding-id> ...`: zastosowanie wybranych znalezisk
- `--json`: zwrócenie ustrukturyzowanych danych wyjściowych JSON
- Punkty rozszerzeń i własne adaptery opisuje [przewodnik po personalizacji](docs/customization.md).

Kody zakończenia:

- `0`: polecenie zakończyło się powodzeniem
- `1`: analiza była prawidłowa, lecz nie udało się zastosować żadnego wybranego znaleziska
- `2`: walidacja CLI wykryła błąd konfiguracji lub parsowania danych wejściowych

Uwagi o prywatności:

- Domyślnie tekst wejściowy nie jest zapisywany w wyjściu błędów i nie opuszcza
  procesu.
- Błędy walidacji i runtime'u są raportowane wyłącznie za pomocą kodów na
  poziomie operacji oraz bezpiecznego kontekstu.

## Dane ewaluacyjne

Początkowy licencjonowany polski zbiór referencyjny i większe korpusy badawcze
są zasobami ewaluacyjnymi, a nie deklaracją zakresu obsługi produkcyjnej. Podlegają
rygorystycznym walidatorom; ich schemat, pochodzenie CC0, trudne przypadki
negatywne i zasady wnoszenia zmian dokumentuje
[przewodnik po zbiorze ewaluacyjnym](docs/evaluation-dataset.md).

## Grupy zależności

Domyślna instalacja nie ma zależności produkcyjnych. Opcjonalna grupa `dev`
służy wyłącznie do lokalnej pracy programistycznej i obejmuje następujące
narzędzia na liberalnych licencjach, z których każde dopuszcza ADR-0001:

| Zależność | Minimalna wersja | Zastosowanie | Uzasadnienie licencji |
| --- | --- | --- | --- |
| `build` | 1.3.0 | Budowanie artefaktów wheel i dystrybucji źródłowej. | MIT znajduje się na liście dozwolonych licencji. |
| `hatchling` | 1.27.0 | Backend budowania używany z zablokowanego środowiska. | MIT znajduje się na liście dozwolonych licencji. |
| `mypy` | 2.3.0 | Uruchamianie rygorystycznej statycznej kontroli typów. | MIT znajduje się na liście dozwolonych licencji. |
| `packaging` | 26.2 | Parsowanie i porównywanie tożsamości wydań PEP 440 w narzędziach przeznaczonych tylko dla programistów. | Apache-2.0 OR BSD-2-Clause znajduje się na liście dozwolonych licencji. |
| `pytest` | 9.0.0 | Uruchamianie zestawu testów. | MIT znajduje się na liście dozwolonych licencji. |
| `ruff` | 0.15.0 | Kontrola lintingu i formatowanie plików Pythona. | MIT znajduje się na liście dozwolonych licencji. |

Backendem budowania jest `hatchling` 1.27.0 lub nowszy. Ta dolna granica to
pierwsze wydanie Hatchling obsługujące pola `license` i `license-files` z PEP
639; Hatchling jest objęty licencją MIT, a zatem dopuszczony przez ADR-0001.
Pełny zablokowany graf zależności przechodnich oraz decyzje o jego przyjęciu
zapisano w [przeglądzie licencji zależności](docs/development/dependency-licenses.md).
