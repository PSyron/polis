# Przegląd licencji zależności budowania i rozwoju

- Data przeglądu: 2026-08-10
- Właściciel: Paweł Cyroń
- Zatwierdzający: Paweł Cyroń
- Audytowana rewizja: `59919931a95589d0ef5498fc8bcfe6ea0b67d62a`
- Zakres: pełny graf z `uv.lock` dla opcjonalnych grup `dev` i `morphology`, w
  tym projekt lokalny i backend budowania
- Decyzja: zatwierdzono do użycia przy budowaniu i rozwoju z zachowaniem
  poniższych obowiązków

Dokładne wersje i skróty artefaktów zapisano w `uv.lock`. Kolumna dowodów
zawiera odnośniki do niezmiennych, właściwych dla wersji metadanych PyPI,
które potwierdzają tożsamość pakietu i opublikowane metadane licencji.

| Pakiet | Wersja | Wyrażenie SPDX | Rola | Dowody i obowiązki |
| --- | --- | --- | --- | --- |
| `ast-serialize` | 0.6.0 | MIT | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/ast-serialize/0.6.0/json); przy redystrybucji zachowaj notę MIT. |
| `build` | 1.5.0 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/build/1.5.0/json); przy redystrybucji zachowaj notę MIT. |
| `colorama` | 0.4.6 | BSD-3-Clause | zależność przechodnia budowania w Windows | [Metadane PyPI](https://pypi.org/pypi/colorama/0.4.6/json); zachowaj prawa autorskie, warunki i wyłączenie odpowiedzialności. |
| `hatchling` | 1.31.0 | MIT | bezpośrednia zależność budowania i rozwoju | [Metadane PyPI](https://pypi.org/pypi/hatchling/1.31.0/json); przy redystrybucji zachowaj notę MIT. |
| `iniconfig` | 2.3.0 | MIT | zależność przechodnia pytest | [Metadane PyPI](https://pypi.org/pypi/iniconfig/2.3.0/json); przy redystrybucji zachowaj notę MIT. |
| `librt` | 0.13.0 | MIT | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/librt/0.13.0/json); przy redystrybucji zachowaj notę MIT. |
| `mypy` | 2.3.0 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/mypy/2.3.0/json); przy redystrybucji zachowaj notę MIT. |
| `mypy-extensions` | 1.1.0 | MIT | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/mypy-extensions/1.1.0/json); przy redystrybucji zachowaj notę MIT. |
| `morfeusz2` | 1.99.15 | BSD-2-Clause | bezpośrednia zależność extras `dev` i `morphology`; benchmark #238 oraz opcjonalny konsument #239 | [Metadane PyPI](https://pypi.org/pypi/morfeusz2/1.99.15/json) i [licencja dostawcy](https://morfeusz.sgjp.pl/doc/license/); zachowaj notę, warunki i wyłączenie odpowiedzialności programu oraz dołączonych danych fleksyjnych SGJP/Polimorf. Licencja nie obejmuje całego słownika gramatycznego SGJP. |
| `packaging` | 26.2 | Apache-2.0 OR BSD-2-Clause | bezpośrednia zależność deweloperska `dev` (`packaging>=26.2`); także zależność przechodnia build, Hatchling i pytest | [Metadane PyPI](https://pypi.org/pypi/packaging/26.2/json); złożone wyrażenie zatwierdzono w wariancie BSD-2-Clause. |
| `pathspec` | 1.1.1 | MPL-2.0 | zależność przechodnia Hatchling i mypy | [Metadane PyPI](https://pypi.org/pypi/pathspec/1.1.1/json); osobna akceptacja wyłącznie dla niezmodyfikowanej zależności budowania i rozwoju. |
| `pluggy` | 1.6.0 | MIT | zależność przechodnia pytest | [Metadane PyPI](https://pypi.org/pypi/pluggy/1.6.0/json); przy redystrybucji zachowaj notę MIT. |
| `polis-nlp` | 0.2.0 | MIT | projekt lokalny | `pyproject.toml` i `LICENSE`; kod i dokumentacja projektu są na licencji MIT. |
| `pygments` | 2.20.0 | BSD-2-Clause | zależność przechodnia pytest | [Metadane PyPI](https://pypi.org/pypi/pygments/2.20.0/json); zachowaj prawa autorskie, warunki i wyłączenie odpowiedzialności. |
| `pyproject-hooks` | 1.2.0 | MIT | zależność przechodnia build | [Metadane PyPI](https://pypi.org/pypi/pyproject-hooks/1.2.0/json); przy redystrybucji zachowaj notę MIT. |
| `pytest` | 9.1.1 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/pytest/9.1.1/json); przy redystrybucji zachowaj notę MIT. |
| `ruff` | 0.15.22 | MIT | bezpośrednia zależność deweloperska | [Metadane PyPI](https://pypi.org/pypi/ruff/0.15.22/json); przy redystrybucji zachowaj notę MIT. |
| `trove-classifiers` | 2026.6.1.19 | Apache-2.0 | zależność przechodnia Hatchling | [Metadane PyPI](https://pypi.org/pypi/trove-classifiers/2026.6.1.19/json); zachowaj licencję i noty. |
| `typing-extensions` | 4.16.0 | PSF-2.0 | zależność przechodnia mypy | [Metadane PyPI](https://pypi.org/pypi/typing-extensions/4.16.0/json); zachowaj licencję PSF i noty. |

## Decyzja #277: reprezentacja licencji dystrybucyjnej i CC0

### Rzeczywiste źródło obowiązków

- Projektowy kod i dokumentacja są objęte `license = "MIT"` w `pyproject.toml`
  i `license-files = ["LICENSE"]`, dlatego kontrakt runtime i opublikowane
  artefakty są licencjonowane jako MIT.
- Aktywnie dystrybuowany kod jest ograniczony do `/src/polis/**` bez warstwy badawczej;
  wszystkie rekordy jakości `src/polis/evaluation/datasets/quality/v1/*` i
  `src/polis/evaluation/datasets/v1/cases.json` deklarują `license: CC0-1.0`.
- `packaging`, `mypy`, `ruff`, `build`, `hatchling`, `pytest`, `morfeusz2` oraz powiązane
  pozycje zgodnie z `pyproject.toml` i `uv.lock` pozostają narzędziami
  deweloperskimi i nie stanowią zmienionej powierzchni danych użytkownika.

### Decyzja dla obecnych artefaktów

- **Zalecenie**: utrzymać obecny model bez zmian.
- **Polityka**: nie wprowadzać dodatkowych plików `LICENSES/` ani globalnych
  plików legalnych podsumowań dla CC0, dopóki rozsyłane pliki danych pozostają
  jawnie oznaczone i ograniczone do bieżącego zakresu dystrybucji runtime.
- **Zakres artefaktów**: dla bieżących wheel i sdist zachować `MIT` dla kodu i
  dokumentacji projektu oraz `CC0-1.0` dla
  `src/polis/evaluation/datasets/quality/v1/cases.json` i
  `src/polis/evaluation/datasets/v1/cases.json`. Osobne dane, modele oraz noty
  upstream/providerów, w tym dotyczące niebundlowanego `morfeusz2`, nie są
  częścią tej powierzchni dystrybucji.
- **Wynik dokumentacyjny**: w tym issue nie dodawać osobnego pliku legal-code ani
  `NOTICE` dla CC0 i nie zmieniać metadanych PEP 639. Jest to decyzja dla
  obecnej granicy artefaktów, a nie opinia prawna; ten audyt nie stwierdza
  naruszenia ani nie przesądza o obowiązku prawnym.

### Zobowiązania i wznowienie

Jeśli przyszła zmiana w przyszłości włączy nowe pliki danych (poza powyższymi),
dozwolone są tylko dwa warianty:

1. dodać wymagany plik prawny CC0/NOTICE oraz odzwierciedlić to w
   metadanych i testach dystrybucyjnych w osobnym issue,
2. lub pozostawić brak dodatkowych plików prawnych przy braku takiej potrzeby i
   zachować dotychczasowy kontrakt publikacyjny.

Każda zmiana dystrybucji metadanych i bundlingu danych uruchamia odrębne
`issue` implementacyjne z nowym zakresem testów.

Wynik obecnego przeglądu zakłada również, że przy dzisiejszym zakresie
dystrybucji nie wprowadzamy i nie dołączamy noty upstream dla osobnych danych
czy modeli; te komponenty nie są częścią pakietu runtime.

## Autorytatywne źródła

- [Python Packaging Core Metadata (`License-Expression`, `License-File`)](https://packaging.python.org/en/latest/specifications/core-metadata/#license)
- [MIT License](https://opensource.org/license/mit)
- [Creative Commons CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- [PEP 639 – License Expression](https://peps.python.org/pep-0639/)

## Zewnętrzne narzędzie inicjujące

uv nie należy do grafu, który samo rozwiązuje, dlatego podlega osobnemu
przeglądowi i przypięciu. `tool.uv.required-version` odrzuca każdą wersję inną
niż 0.11.2, a README wskazuje dokładnie to wydanie.

| Narzędzie | Wersja | Wyrażenie SPDX | Rola | Dowody i obowiązki |
| --- | --- | --- | --- | --- |
| `uv` | 0.11.2 | Apache-2.0 OR MIT | inicjowanie środowiska i workflow oparty na lockfile | [Metadane PyPI](https://pypi.org/pypi/uv/0.11.2/json) i [licencja upstream](https://github.com/astral-sh/uv/tree/0.11.2#license); złożone wyrażenie zatwierdzono w wariancie MIT. |

## WikEd Error Corpus (niebundlowany artefakt badawczy)

Protokół #427 zapisuje deklarowaną licencję źródła jako `CC-BY-SA-3.0`, zgodnie
z opisem WikEd mówiącym o dziedziczeniu licencji źródłowych rewizji Wikipedii.
To nie jest potwierdzenie warunków konkretnego pliku `wiked-v1.0.pl.tgz`:
status pozostaje `pending_artifact_authority_confirmation`, dopóki maintainer
nie uzyska i nie zwiąże niezmiennego dowodu dla tego wydania. Archiwum, staging,
plaintext i ewentualne noty upstream nie są częścią wheel ani sdist Polis.

## Akcje workflow CI i wydania

Workflow szybkiego CI i chronionego wydania używają wyłącznie poniższych akcji
zewnętrznych. Każda jest przypięta do niezmiennego commita. Commity akcji nie
są zależnościami Pythona i nie zmieniają `uv.lock`.

| Akcja | Commit | Wyrażenie SPDX | Rola | Dowody i obowiązki |
| --- | --- | --- | --- | --- |
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | MIT | Pobranie rewizji źródeł. | [Licencja](https://github.com/actions/checkout/blob/34e114876b0b11c390a56381ad16ebd13914f8d5/LICENSE); zachowaj noty. |
| `actions/setup-python` | `ece7cb06caefa5fff74198d8649806c4678c61a1` | MIT | Instalacja CPythona z macierzy; `x86_64` ADR mapuje na wejście `x64`. | [Licencja](https://github.com/actions/setup-python/blob/ece7cb06caefa5fff74198d8649806c4678c61a1/LICENSE); zachowaj noty. |
| `astral-sh/setup-uv` | `37802adc94f370d6bfd71619e3f0bf239e1f3b78` | MIT | Instalacja uv 0.11.2 i buforowanie środowiska z lockfile. | [Licencja](https://github.com/astral-sh/setup-uv/blob/37802adc94f370d6bfd71619e3f0bf239e1f3b78/LICENSE); zachowaj noty. |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | MIT | Przekazanie jednego niezmiennego bundle po kwalifikacji. | [Licencja](https://github.com/actions/upload-artifact/blob/ea165f8d65b6e75b540449e92b4886f43607fa02/LICENSE); zachowaj noty. |
| `actions/download-artifact` | `d3f86a106a0bac45b974a628896c90dbdf5c8093` | MIT | Pobranie tych samych bajtów w macierzy i przed publikacją. | [Licencja](https://github.com/actions/download-artifact/blob/d3f86a106a0bac45b974a628896c90dbdf5c8093/LICENSE); zachowaj noty. |
| `pypa/gh-action-pypi-publish` | `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` | BSD-3-Clause | Upload dwóch zweryfikowanych dystrybucji przez OIDC. | [Licencja](https://github.com/pypa/gh-action-pypi-publish/blob/dc37677b2e1c63e2034f94d8a5b11f265b73ba33/LICENSE.md); zachowaj prawa autorskie, warunki i wyłączenie odpowiedzialności. |

## Decyzja o przyjęciu

Wszystkie pakiety przypięte w lockfile oprócz `pathspec` i `packaging` używają
pojedynczego identyfikatora SPDX dozwolonego przez ADR-0001. `packaging` łączy
dwie dozwolone licencje operatorem `OR`; przyjęto wariant BSD-2-Clause. uv
również używa `Apache-2.0 OR MIT` i jest przyjęte w wariancie MIT. `pathspec`
jest objęte MPL-2.0 poza domyślną listą, dlatego ma odrębną akceptację wyłącznie
jako niezmodyfikowana zależność budowania i rozwoju, niedołączana do artefaktów
Polis. Zmiana sprawdzonego wyrażenia, roli, wersji lub modelu redystrybucji
wymaga nowego przeglądu.

Morfeusz2 pozostaje dokładnie przypięty w grupie `dev` i opcjonalnym extra
`morphology`; nie jest zależnością instalacji domyślnej. Jego natywne koło, kod
i dane nie trafiają do wheel ani sdist Polis. Przyjęcie obejmuje kwalifikację
dostawcy z issue #238 i jednego konsumenta review-only z issue #239. Szersze
użycie albo redystrybucja wymaga osobnej decyzji, ponownego przeglądu platform
i spełnienia obowiązków BSD-2-Clause.
