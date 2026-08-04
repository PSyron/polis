# Polityka kompatybilności i wersjonowanie semantyczne

Ten dokument publikuje bazową kompatybilność M4 i politykę wycofywania.

## Wspierane konfiguracje

`polis` jest weryfikowany na tej samej macierzy co szybkie CI:

- CPython 3.12, 3.13, 3.14 w systemie Linux x86_64;
- CPython 3.12, 3.14 w systemie macOS arm64;
- CPython 3.12, 3.14 w systemie Windows x86_64.

Podstawowe kontrole deterministyczne nie wymagają opcjonalnego środowiska
uruchomieniowego modelu. Backendy modeli są opcjonalnymi rozszerzeniami; ich brak
nie oznacza zdegradowanego stanu podstawowego runtime'u, a opcjonalne badania
modeli nigdy nie blokują wydania runtime'u. Ścieżka wydania runtime'u nie wymaga
modelu, procesu Java, usługi sieciowej, korpusu badawczego ani zużytego holdoutu.

### Egzekwowanie dowodów i polityki wycofywania

- Asercje kompatybilności są sprawdzane w `.github/workflows/fast-ci.yml` (Linux
  x86_64, macOS arm64, Windows x86_64) przy każdym pushu i PR-ze.
- Dla każdej blokady wydania weryfikujemy zestaw danych kompatybilności i bramki
  jakości poleceniem
  `uv run --locked --extra dev python scripts/verify_prerelease_candidate.py`.
- Każda wymagana zmiana API lub schematu musi przed wydaniem zaktualizować
  `tests/fixtures/public_api_snapshot.json` i zawierać noty migracyjne.

## Profil weryfikacji platform 1.0

Ten wersjonowany profil przypisuje dowody zależne od platformy jawnemu
właścicielowi. Kontrola, której nie można uruchomić na jednej platformie, nie
jest po cichu usuwana: nadal odpowiada za nią wskazane zadanie platformowe albo
osobna ścieżka weryfikacji bramki wydania. Dowód z jednego systemu operacyjnego
nie kwalifikuje innego systemu operacyjnego.

| Kontrola | Właściciel | Platformy i ścieżka weryfikacji |
| --- | --- | --- |
| Szybki zestaw deterministyczny i macierz wspieranych interpreterów | `.github/workflows/fast-ci.yml` | Szybkie CI na Linuxie, macOS i Windowsie |
| Granica procesu CLI dla UTF-8, w tym odziedziczone strumienie CP1252 | `tests/test_cli.py` i `tests/test_release_distribution_installation.py` | Każda platforma szybkiego CI; czysta instalacja wheel i sdist powtarza kontrolę granicy |
| Efektywna polityka `text`/`eol` oraz stabilność bajtów i skrótów checkoutu | `tests/test_fast_ci_workflow.py` | Każda platforma szybkiego CI, w tym behawioralny checkout skonfigurowany dla CRLF |
| Dokładne bajtowo nadpisania kodu upstream dostarczanego ze źródłami | `.gitattributes` i `tests/test_fast_ci_workflow.py` | Każda platforma szybkiego CI; `-text -eol` musi pozostać efektywne |
| Bity wykonywalności POSIX programów uruchamiających dostarczanych ze źródłami | `tests/test_languagetool_vendor_artifacts.py` | Szybkie CI na Linuxie i macOS; Windows nie modeluje bitu trybu POSIX, więc zadania POSIX zachowują ten dowód |
| Dowód odmowy sieci w macOS (`sandbox-exec`) | właściciel kwalifikacji wydania zdaniowego (issue #79) | Zadanie wydania na macOS przez osobną weryfikację bramki wydania; Linux i Windows wymagają własnych wymuszonych mechanizmów odmowy, zanim będą mogły deklarować równoważny dowód |
| Dowody procesów i zasobów POSIX (`/bin/ps`, `lsof`, `sysctl`) | właściciel kwalifikacji wydania zdaniowego (issue #79) | Natywne dla platformy zadania wydania na Linuxie/macOS; polecenie wyłącznie dla Darwina nie może zastępować dowodu dla Linuxa |
| Dowody potoków, procesów, zasobów i odmowy sieci w Windowsie | właściciel kwalifikacji wydania zdaniowego (issue #79) | Zadanie wydania na Windowsie z natywnymi mechanizmami Windows; POSIX-owe `select()` na potokach podprocesów i narzędzia POSIX nie są akceptowanymi zamiennikami |

Bramka wydania zdaniowego musi zgłaszać niewspierany lub niedostępny dowód
platformowy jako blokadę wydania. Pominięcie jest dopuszczalne tylko wtedy, gdy
tabela przypisuje tę samą kontrolę innemu wymaganemu zadaniu, na przykład
weryfikację bitów wykonywalności POSIX na Linuxie/macOS.

## Polityka kompatybilności publicznego API

- **Patch**: poprawki, aktualizacje wyłącznie dokumentacyjne, dodatki testów oraz
  naprawy błędów bez wpływu łamiącego zachowanie stabilnych symboli publicznych.
- **Minor**: dodawane symbole publiczne, dodawane wartości enum, bezpieczniejsze
  komunikaty walidacji i nowe funkcje opcjonalne.
- **Major**: zmiany łamiące istniejący kod korzystający z udokumentowanych
  symboli (`polis.__all__` / `public API snapshots`) albo wersji serializowanych
  schematów.

## Polityka wersji wydań

Wybór wydania używa linii wersji SemVer `MAJOR.MINOR.PATCH`: nowa, addytywna
linia wersji Polis po `0.1.0` to `0.2.0`. Metadane i artefakty pakietu Pythona
używają
odpowiadających im kanonicznych postaci PEP 440: zwykły rozwój to `0.2.0.dev0`,
kandydat to `0.2.0rcN`, a stabilny pakiet to `0.2.0`. Każda wybrana wersja
pakietu ma dokładnie odpowiadający tag Git `v<version>`; weryfikator wydania
odrzuca postacie skrócone, lokalne, równe i niższe.

`pyproject.toml` jest autorytatywnym źródłem wersji pakietu. Weryfikator wymaga,
aby metadane źródłowe, nazwy artefaktów, osadzone metadane wheel/sdist, manifest,
nagłówek noty wydania, nagłówek changelogu i żądany tag opisywały jedną dokładną
tożsamość.

## Kompatybilność danych serializowanych

- Publiczny JSON analizy ma obecnie `schema_version = 1`.
- Każda zmiana kształtu danych przesyłanych po łączu lub semantyki identyfikatorów
  jest zmianą **major** i musi otrzymać instrukcję migracji.
- Polityka `1.2` nie zmienia `Finding` ani wersji `1` schematu JSON analizy.
  Serializowane znaleziska nie niosą uprawnienia do automatycznej korekty.
- `CorrectionResult.source_policy_version` jest addytywnym polem API Pythona.
  To zadanie nie wprowadza kanonicznego schematu JSON dla `CorrectionResult`.
- Protokół żądań i odpowiedzi zainstalowanego programu bezpieczeństwa zdaniowego
  używa wersji `2` schematu i zapisuje zaobserwowaną wersję polityki runtime'u.
  Jego protokół jest odrębny od historycznego raportu ewaluacji, który zachowuje
  wersję `1` schematu, stabilność bajtową i identyfikację historyczną polityką
  `1.1`.

## Jak śledzimy kompatybilność

- `scripts/verify_prerelease_candidate.py` uruchamia bramki jakości.
- `tests/fixtures/public_api_snapshot.json` zapisuje stabilne eksporty i wersje schematów.
- `tests/test_api_compatibility.py` zgłasza błąd, gdy eksporty runtime'u lub
  kontrakty schematów zmieniają się bez aktualizacji migawki.
- Każda aktualizacja migawki wymaga jawnego przeglądu na poziomie issue oraz
  not wydania.
