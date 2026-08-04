# Przegląd licencji zależności budowania i rozwoju

- Data przeglądu: 2026-07-20
- Właściciel: Paweł Cyroń
- Zakres: pełny graf z `uv.lock` dla opcjonalnej grupy `dev`, w tym projekt
  lokalny i backend budowania
- Decyzja: zatwierdzono do użycia przy budowaniu i rozwoju z zachowaniem
  poniższych obowiązków

Dokładne wersje i skróty artefaktów zapisano w `uv.lock`. Kolumna Dowody zawiera
odnośniki do niezmiennego, właściwego dla wersji dokumentu JSON z PyPI, którego
użyto do weryfikacji tożsamości pakietu i opublikowanych metadanych licencji.
Pliki licencji w repozytoriach sprawdzono tam, gdzie PyPI udostępnia wyłącznie
historyczny klasyfikator.

| Pakiet | Wersja | Wyrażenie SPDX | Rola | Dowody i obowiązki |
| --- | --- | --- | --- | --- |
| `ast-serialize` | 0.6.0 | MIT | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/ast-serialize/0.6.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `build` | 1.5.0 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/build/1.5.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `colorama` | 0.4.6 | BSD-3-Clause | zależność przechodnia budowania w Windows | [Metadane PyPI](https://pypi.org/pypi/colorama/0.4.6/json); zachowaj prawa autorskie, warunki i wyłączenie odpowiedzialności; nie używaj nazw współtwórców do promowania produktu. |
| `hatchling` | 1.31.0 | MIT | bezpośrednia zależność budowania i rozwoju | [Metadane PyPI](https://pypi.org/pypi/hatchling/1.31.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `iniconfig` | 2.3.0 | MIT | zależność przechodnia pytest | [Metadane PyPI](https://pypi.org/pypi/iniconfig/2.3.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `librt` | 0.13.0 | MIT | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/librt/0.13.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `mypy` | 2.3.0 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/mypy/2.3.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `mypy-extensions` | 1.1.0 | MIT | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/mypy-extensions/1.1.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `packaging` | 26.2 | Apache-2.0 OR BSD-2-Clause | zależność przechodnia build, Hatchling i pytest | [Metadane PyPI](https://pypi.org/pypi/packaging/26.2/json); złożone wyrażenie zostało jawnie zatwierdzone w wariancie BSD-2-Clause. W razie redystrybucji zachowaj prawa autorskie, warunki licencji i wyłączenie odpowiedzialności. |
| `pathspec` | 1.1.1 | MPL-2.0 | zależność przechodnia Hatchling i mypy | [Metadane PyPI](https://pypi.org/pypi/pathspec/1.1.1/json); MPL-2.0 jest jawnie zatwierdzona dla tej zależności używanej wyłącznie do budowania i rozwoju. Zachowaj noty i tekst licencji; jeśli zmodyfikowane pliki objęte licencją są rozpowszechniane, udostępnij ich źródła na MPL-2.0. Polis nie modyfikuje tego pakietu ani go nie dołącza. |
| `pluggy` | 1.6.0 | MIT | zależność przechodnia pytest | [Metadane PyPI](https://pypi.org/pypi/pluggy/1.6.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `polis-nlp` | 0.2.0.dev0 | MIT | projekt lokalny | `pyproject.toml` i `LICENSE`; kod i dokumentacja autorstwa projektu pozostają na licencji MIT. |
| `pygments` | 2.20.0 | BSD-2-Clause | zależność przechodnia pytest | [Metadane PyPI](https://pypi.org/pypi/pygments/2.20.0/json); w razie redystrybucji zachowaj prawa autorskie, warunki licencji i wyłączenie odpowiedzialności. |
| `pyproject-hooks` | 1.2.0 | MIT | zależność przechodnia build | [Metadane PyPI](https://pypi.org/pypi/pyproject-hooks/1.2.0/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `pytest` | 9.1.1 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/pytest/9.1.1/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `ruff` | 0.15.22 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/ruff/0.15.22/json); w razie redystrybucji zachowaj informację o prawach autorskich i notę MIT. |
| `trove-classifiers` | 2026.6.1.19 | Apache-2.0 | zależność przechodnia Hatchling | [Metadane PyPI](https://pypi.org/pypi/trove-classifiers/2026.6.1.19/json); w razie redystrybucji zachowaj licencję i noty oraz oznacz zmodyfikowane pliki. |
| `typing-extensions` | 4.16.0 | PSF-2.0 | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/typing-extensions/4.16.0/json); w razie redystrybucji zachowaj licencję PSF i noty. |

## Zewnętrzne narzędzie inicjujące

uv nie może należeć do grafu, który samo rozwiązuje, dlatego podlega osobnemu
przeglądowi i przypięciu. `tool.uv.required-version` odrzuca każdą wersję inną
niż 0.11.2, a README instaluje dokładnie to wydanie.

| Narzędzie | Wersja | Wyrażenie SPDX | Rola | Dowody i obowiązki |
| --- | --- | --- | --- | --- |
| `uv` | 0.11.2 | Apache-2.0 OR MIT | inicjowanie środowiska i workflow oparty na lockfile | [Metadane PyPI](https://pypi.org/pypi/uv/0.11.2/json) i [licencja upstream](https://github.com/astral-sh/uv/tree/0.11.2#license); złożone wyrażenie zostało jawnie zatwierdzone w wariancie MIT. W razie redystrybucji zachowaj informację o prawach autorskich i notę licencji MIT. |

## Akcje workflow CI

Szybki workflow używa wyłącznie poniższych akcji zewnętrznych. Każda jest
przypięta do niezmiennego commita opublikowanego przez sprawdzoną wersję główną
i objęta licencją MIT. Commity akcji nie są zależnościami Pythona i nie zmieniają
`uv.lock`.

| Akcja | Commit | Wyrażenie SPDX | Rola | Dowody i obowiązki |
| --- | --- | --- | --- | --- |
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | MIT | Pobranie proponowanej rewizji źródeł. | [Licencja](https://github.com/actions/checkout/blob/34e114876b0b11c390a56381ad16ebd13914f8d5/LICENSE); w razie redystrybucji zachowaj noty. |
| `actions/setup-python` | `ece7cb06caefa5fff74198d8649806c4678c61a1` | MIT | Instalacja interpretera CPython wybranego przez macierz; jego [przypięty schemat danych wejściowych](https://github.com/actions/setup-python/blob/ece7cb06caefa5fff74198d8649806c4678c61a1/action.yml) przyjmuje `x86`, `x64` lub `arm64`, dlatego `x86_64` z ADR jest mapowane na `x64`. | [Licencja](https://github.com/actions/setup-python/blob/ece7cb06caefa5fff74198d8649806c4678c61a1/LICENSE); w razie redystrybucji zachowaj noty. |
| `astral-sh/setup-uv` | `37802adc94f370d6bfd71619e3f0bf239e1f3b78` | MIT | Instalacja uv 0.11.2 i buforowanie środowiska z lockfile. | [Licencja](https://github.com/astral-sh/setup-uv/blob/37802adc94f370d6bfd71619e3f0bf239e1f3b78/LICENSE); w razie redystrybucji zachowaj noty. |

## Decyzja o przyjęciu

Wszystkie pakiety przypięte w lockfile oprócz `pathspec` i `packaging` używają jednego
identyfikatora SPDX dozwolonego już przez ADR-0001. `packaging` łączy dwie
dozwolone licencje operatorem `OR`; Polis przyjmuje go w wariancie
BSD-2-Clause. Zewnętrzne narzędzie inicjujące uv również używa złożonego
wyrażenia `Apache-2.0 OR MIT` i zostaje jawnie przyjęte w wariancie MIT.
`pathspec` używa MPL-2.0, która znajduje się poza domyślną listą dozwolonych
licencji; zostaje przyjęta wyłącznie jako niezmodyfikowana zależność przechodnia
budowania i rozwoju i nie jest dołączana do artefaktów dystrybucji Polis. Te
jawne decyzje spełniają wymaganie osobnego przeglądu z ADR-0001. Zmiana
któregokolwiek sprawdzonego wyrażenia, roli, wersji lub modelu redystrybucji
wymaga nowego przeglądu.

## Opcjonalny zewnętrzny silnik reguł

LanguageTool 6.8 jest wspierany jako opcjonalny proces lokalny, lecz nie znajduje
się w `pyproject.toml`, `uv.lock`, wheel ani dystrybucjach źródłowych. Jego
otwartoźródłowy rdzeń i polskie reguły gramatyczne są objęte licencją
LGPL-2.1-or-later. Domyślny runtime Pythona go nie wymaga. Po włączeniu adapter
loopback komunikuje się przez HTTP z niezmodyfikowanym, osobno zainstalowanym
procesem i nie redystrybuuje jego plików wykonywalnych. OpenJDK 17 jest podobnie
dostarczany przez lokalny menedżer pakietów, a nie przez Polis.

Na potrzeby M4 repozytorium zawiera niezmodyfikowany rdzeń LanguageTool 6.8 i
polskie drzewa `src/main` w `third_party/languagetool-pl`, wraz z dokładnym
pochodzeniem, tekstem LGPL i maszynowo czytelnym manifestem zawartości. Most
stdio autorstwa projektu łączy się z lokalnie zbudowanymi, niepołączonymi
plikami JAR rdzenia i części polskiej tylko wtedy, gdy wywołujący jawnie buduje
dostarczony runner i wskazuje go Polis. Pamięć podręczna Maven, biblioteki
runtime'u i wyniki budowania Java pozostają ignorowanymi artefaktami lokalnymi;
cały katalog jest wykluczony z wyjścia wheel i sdist Pythona. Artefakty te
znajdują się poza granicą sprawdzonej dystrybucji Pythona na licencji MIT i nie
stają się zależnościami produkcyjnymi Pythona.

Polski zasób morfologiczny zachowuje notę BSD-2-Clause. Zasób Hunspell zachowuje
upstreamowe warianty GPL/LGPL/MPL/CC-SA-1.0 i notę Apache-2.0 dotyczącą danych
częstotliwości. Te noty właściwe dla zasobów są wskazane w manifeście modułu i
`NOTICE`; nie są sprowadzane do oznaczenia LGPL rdzenia.

Każda propozycja dołączenia, zmodyfikowania lub redystrybucji LanguageTool albo
JVM wymaga nowego przeglądu licencji i dystrybucji; ADR-0006 nie zatwierdza
dołączania.
