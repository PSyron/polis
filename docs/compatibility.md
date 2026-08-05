# Zgodność i wersjonowanie v1

## Wspierane konfiguracje

`polis` jest weryfikowany na macierzy ADR-0001:

- CPython 3.12, 3.13, 3.14 w systemie Linux x86_64;
- CPython 3.12, 3.14 w systemie macOS arm64;
- CPython 3.12, 3.14 w systemie Windows x86_64.

Wspierany runtime v1 jest deterministyczny i offline: nie wymaga modelu,
procesu Java, usługi sieciowej, korpusu badawczego ani zużytego holdoutu.
Opcjonalne badania modeli nigdy nie blokują wydania runtime'u. Ścieżka wydania
runtime'u nie wymaga modelu, procesu Java, usługi sieciowej, korpusu badawczego
ani zużytego holdoutu.

### Egzekwowanie dowodów i polityki wycofywania

- Asercje kompatybilności sprawdza `.github/workflows/fast-ci.yml` na Linuxie,
  macOS i Windowsie przy każdym pushu i pull requeście.
- Zmiana API lub schematu aktualizuje
  `tests/fixtures/public_api_snapshot.json` i wymaga not migracyjnych.
- `tests/test_api_compatibility.py` wykrywa nieuzgodnioną zmianę eksportów
  runtime'u albo kontraktu schematu.

## Profil weryfikacji platform 1.0

Ten wersjonowany profil przypisuje dowody zależne od platformy jawnemu
właścicielowi. Kontrola niedostępna na jednej platformie nie jest po cichu
usuwana: odpowiada za nią wskazany test albo osobną weryfikację bramki wydania.
Dowód z jednego systemu operacyjnego nie kwalifikuje innego.

| Kontrola | Właściciel | Platformy i ścieżka weryfikacji |
| --- | --- | --- |
| Szybki zestaw deterministyczny i macierz wspieranych interpreterów | `.github/workflows/fast-ci.yml` | Szybkie CI na Linuxie, macOS i Windowsie |
| Granica procesu CLI dla UTF-8 i odziedziczonego CP1252 | `tests/test_cli.py` i `tests/test_release_distribution_installation.py` | Każda platforma szybkiego CI; czysta instalacja wheel i sdist powtarza kontrolę |
| Efektywna polityka `text`/`eol` oraz stabilność bajtów i skrótów checkoutu | `tests/test_fast_ci_workflow.py` | Każda platforma szybkiego CI, w tym checkout skonfigurowany dla CRLF |
| Dowód pracy z zablokowaną siecią | `tests/test_offline_verification.py` i `tests/test_privacy_dependency_audit.py` | Szybki runtime v1 nie podejmuje połączenia; testy wymuszają błąd sieci |
| Izolowana instalacja artefaktów i właściwy dla platformy układ środowiska | `tests/test_release_distribution_installation.py` i `scripts/verify_distribution_install.py` | Wheel i sdist są instalowane w czystych środowiskach na każdej wspieranej platformie |

Niedostępny dowód platformowy blokuje kwalifikację wydania, chyba że tabela
przypisuje tę samą kontrolę innemu wymaganemu zadaniu.

## Polityka kompatybilności publicznego API

- **Patch**: poprawki, aktualizacje dokumentacji, dodatki testów i naprawy bez
  łamiącego wpływu na stabilne symbole publiczne.
- **Minor**: addytywne symbole publiczne, wartości enum i bezpieczniejsze
  komunikaty walidacji.
- **Major**: zmiany łamiące udokumentowane symbole (`polis.__all__` i snapshot
  API) albo wersje serializowanych schematów.

## Polityka wersji wydań

Wersja SemVer `MAJOR.MINOR.PATCH` ma odpowiadającą postać PEP 440: zwykły rozwój
to `0.2.0.dev0`, kandydat `0.2.0rcN`, a stabilny pakiet `0.2.0`. Każda wybrana
wersja pakietu ma odpowiadający tag Git `v<version>`. `pyproject.toml` jest
autorytatywnym źródłem wersji; metadane, nazwy artefaktów, manifest, release
notes i tag muszą opisywać jedną dokładną tożsamość.

## Kompatybilność danych serializowanych

Publiczny JSON analizy ma `schema_version = 1`; zmiana jego kształtu lub
semantyki identyfikatorów jest zmianą major i wymaga migracji. Polityka `1.2`
nie zmienia `Finding` ani schematu wyniku analizy. `CorrectionResult.source_policy_version`
jest addytywnym polem API Pythona i nie ma osobnego schematu JSON.

W linii 0.x importy `polis.evaluation.load_dataset` i
`polis.evaluation.validate_dataset` zachowują zgodność przez
[ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md).
`Analyzer.close()`, menedżer kontekstu i
`language_tool_process_start_count` pozostają dla zgodności 0.x; runtime v1 nie
posiada procesu, więc licznik zwraca `0`, a zamknięcie jest no-op. Dane
historycznego schematu zachowują `SourceKind.LLM` oraz typy wyników sugestii,
ale wspierany runtime v1 nie tworzy takich znalezisk ani wywołań.

Obecną granicę produktu przyjmuje
[ADR-0022](architecture/decisions/0022-conservative-v1-product-scope.md).
