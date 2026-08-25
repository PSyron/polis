# ADR-0022: Przyjęcie konserwatywnego zakresu produktu v1

- Status: Accepted
- Date: 2026-08-05
- Owner: Paweł Cyroń
- Issue: #191

## Kontekst

Issue #185 zatwierdziło kierunek, w którym Polis v1 jest małym produktem
runtime-first do bezpiecznej korekty polskiej formy. Dotychczasowe żywe źródła
nadal dopuszczają lokalny LLM, pełny LanguageTool, proces Java, kontekstowe
wnioskowanie semantyczne i rozbudowę katalogu M6 jako możliwe składniki
wspieranego runtime'u. Taki obraz jest szerszy niż produkt, który można
uzasadnić obecną bazą regresyjną.

Issue #188 utworzyło i zweryfikowało pełne zdalne archiwum sprzed sprzątania.
[Manifest archiwum](../../project/v2-research-archive-manifest.md) wiąże gałąź
`feature/v2-research-archive` z literalnym SHA
`ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8`. Dopiero ten zapis pozwala usunąć
z `main` wykonywalny materiał v2 bez utraty jego pełnego stanu.

Ta decyzja zmienia politykę produktu i zgodności. Nie usuwa kodu, badań,
vendoru, testów ani dowodów.

## Decyzja

### Niezmiennik produktu v1

Polis v1 poprawia wyłącznie jednoznaczną lokalną formę tekstu. Sugestia jest
dopuszczalna tylko wtedy, gdy błąd i minimalna poprawka wynikają z lokalnego
zapisu, zachowują półotwarty zakres `[start, end)` i nie wymagają odgadnięcia
intencji, faktów, czasu, aspektu, stylu, tonu ani sensu. Niepewność, konflikt lub
brak danych prowadzą do braku sugestii.

Wspierany runtime v1 obejmuje deterministyczne reguły wysokiej precyzji dla
fleksji, rekcji, zgody, pisowni, ortotypografii, bezpiecznej interpunkcji oraz
nielicznych lokalnych problemów składniowych. Nie obejmuje:

- zmiany znaczenia ani zgodności czasów i aspektu;
- lokalnego LLM, modelowego rankera i fine-tuningu;
- pełnego LanguageTool, procesu Java ani szerokiej integracji reguł upstream;
- kontekstowego wnioskowania semantycznego;
- rozszerzania katalogu reguł M6 bez bieżącego konsumenta v1.

Badania nad tymi obszarami mogą wrócić wyłącznie przez nowe issue i nowy ADR
dla v2. Nie są zależnością wydania, pakowania ani CI v1.

### Skutki dla wcześniejszych decyzji

ADR-0004–ADR-0018 i ADR-0020 pozostają zaakceptowanym, niezmiennym zapisem
historii. Ich wyniki badawcze, granice bezpieczeństwa i udokumentowane
odrzucenia nadal opisują stan, dla którego powstały. ADR-0022 zastępuje jednak
każdą ich interpretację, według której LLM, LanguageTool, Java, kontekstowa
fleksja albo hybrydowy ranking należą do wspieranego runtime'u v1.

ADR-0019 zachowuje pełną moc: `polis.evaluation` pozostaje zgodnym importowo
namespace'em w całej linii 0.x. Sprzątanie nie może usunąć tego namespace'u ani
jego udokumentowanych lekkich walidatorów bez osobnej decyzji i migracji
wymaganej przez ADR-0019.

ADR-0021 pozostaje historyczną decyzją o planowanej własności katalogu.
ADR-0022 zastępuje jej plan implementacji i rozbudowy w v1. Obecny
deterministyczny rejestr może pozostać mały; prace M6 nad wyborem źródeł,
inspekcją i katalogiem nie są częścią v1.

### Zgodność schematu, błędów i wyników

`SourceKind.LLM` pozostaje przez całą linię 0.x jako historyczna wartość
wersjonowanego schematu JSON. Zachowanie tej wartości nie oznacza obecności
backendu LLM ani prawa do wygenerowania nowego znaleziska LLM przez wspierany
runtime.

Publiczna hierarchia wyjątków z ADR-0003 pozostaje przez całą linię 0.x.
Usunięcie implementacji backendu nie usuwa typów `BackendUnavailableError`,
`AnalysisTimeoutError` ani `InvalidBackendResponseError`; istniejące importy
oraz deserializacja historycznych kontraktów pozostają poprawne.

`SuggestionOutcome`, `SuggestionStatus` i
`CorrectionResult.suggestion_outcomes` pozostają przez całą linię 0.x.
Deterministyczne wykonanie bez opcjonalnego backendu zwraca pustą krotkę
wyników. Ewentualne usunięcie tych członków może nastąpić dopiero w 1.0 wraz z
jawnymi release notes i przykładem migracji.

Publiczne członki cyklu życia `Analyzer.close()`, `Analyzer.__enter__()`,
`Analyzer.__exit__()` i `Analyzer.language_tool_process_start_count` pozostają
przez całą linię 0.x. Po usunięciu posiadanego procesu ich bezpieczne zachowanie
jest no-op, a licznik zwraca `0`. Usunięcie może nastąpić dopiero w 1.0 wraz z
jawnymi release notes i migracją. `Analyzer.analyze_async()`,
`Analyzer.correct_async()` i `Analyzer.from_config()` pozostają zwykłymi
publicznymi punktami wejścia.

### Pola konstruktora `AnalyzerConfig`

Poniższe siedem pól konfiguruje wyłącznie zachowanie poza zakresem v1.
ADR-0022 jawnie dopuszcza ich usunięcie w atomowym issue runtime'u przed 1.0.
Dokumentacja migracji i release notes tej zmiany muszą wymienić każde pole;
Python zgłasza wtedy zwykły `TypeError` dla nieznanego argumentu konstruktora.

| Pole | Decyzja zgodności | Migracja |
| --- | --- | --- |
| `use_local_heuristic_backend` | Usunąć; mock LLM nie jest funkcją produktu. | Pominąć pole; runtime zawsze używa wspieranych źródeł deterministycznych. |
| `language_tool_url` | Usunąć; zewnętrzny pełny LanguageTool nie jest wspierany. | Pominąć pole; osobna integracja może powstać dopiero jako jawne rozszerzenie v2. |
| `language_tool_timeout_seconds` | Usunąć razem z transportem HTTP. | Pominąć pole; bez transportu nie istnieje timeout do skonfigurowania. |
| `contextual_inflection_stdio_path` | Usunąć; kontekstowa ścieżka stdio nie należy do v1. | Pominąć pole; zachowanie nie ma zamiennika w v1. |
| `contextual_inflection_timeout_seconds` | Usunąć razem ze ścieżką stdio. | Pominąć pole; bez transportu nie istnieje timeout do skonfigurowania. |
| `vendored_language_tool_stdio_path` | Usunąć; vendored Java nie należy do v1. | Pominąć pole i nie uruchamiać procesu; pełny stan pozostaje w archiwum #188. |
| `vendored_language_tool_timeout_seconds` | Usunąć razem z vendored stdio. | Pominąć pole; bez procesu nie istnieje timeout do skonfigurowania. |

Pola `categories` i `minimum_confidence` pozostają wspierane. Fabryki
`AnalyzerConfig.from_toml` oraz `AnalyzerConfig.from_config` pozostają
wspierane i odczytują lokalny plik TOML. Nie wykonują sieci ani nie szukają
konfiguracji niejawnej.

### Historyczne sekcje TOML

Sekcja `[analysis]` i jej wspierane klucze pozostają bez zmian. Następujące
sekcje są usuwane jako powierzchnie konfiguracji v1:

| Sekcja i klucze | Decyzja | Migracja |
| --- | --- | --- |
| `[backend]`: `use_mock` | Odrzucić całą sekcję. | Usunąć sekcję; analiza deterministyczna jest domyślna. |
| `[language_tool]`: `base_url`, `timeout_seconds` | Odrzucić całą sekcję. | Usunąć sekcję; transport HTTP nie ma zamiennika v1. |
| `[contextual_inflection]`: `stdio_path`, `timeout_seconds` | Odrzucić całą sekcję. | Usunąć sekcję; kontekstowa ścieżka nie ma zamiennika v1. |
| `[vendored_language_tool]`: `stdio_path`, `timeout_seconds` | Odrzucić całą sekcję. | Usunąć sekcję; vendored Java pozostaje tylko w archiwum. |

Obecność którejkolwiek usuniętej sekcji zawsze kończy parsowanie stabilnym
`ConfigurationError` o kodzie `configuration.unsupported_section` i
`retryable=False`. Komunikat zawiera odrzuconą nazwę sekcji oraz dokładną frazę
`is not supported in Polis v1`. Kontekst zawiera `operation`, `path` i klucz
`section` z nazwą sekcji bez nawiasów. Parser sprawdza samą obecność sekcji,
więc nie może po cichu zignorować pustej tabeli ani nieznanego klucza w tej
tabeli.

### Protokoły bez konsumenta

`LocalGenerationBackend`, `LocalFindingBackend` i `MonotonicClock` mogą zostać
usunięte dopiero w tym samym lub późniejszym atomowym issue, które najpierw
wykaże, że composition root, pipeline i wszystkie wspierane adaptery v1 już ich
nie konsumują. Usunięcie eksportów wymaga aktualizacji testów typów,
dokumentacji publicznej i release notes. Nie wolno pozostawić protokołu jako
spekulacyjnej abstrakcji bez konsumenta.

### Powłoka dowodowa na `main`

Na `main` pozostają dokładnie zinwentaryzowane, niezmienne dowody: zaakceptowane
ADR-y, opublikowane release notes, historyczne plany `docs/superpowers/`, trzy
zamrożone checklisty przeglądu, wymagane raporty, wyniki, konfiguracje,
manifesty, markery holdoutu, pliki proweniencji, licencje i noty upstream.
Inwentarz schematu 1 wymienia każdy taki plik przez dokładny wpis `paths` przed
ogólnymi regułami dokumentacji. Prefiksy `experiments/`, `data/` i
`third_party/` nie nadają już ochrony całym drzewom.

Po weryfikacji klasyfikacji wykonywalne runnery badań, źródła vendorowe i kod
poza zakresem v1 mogą zostać usunięte z `main` w osobnych issue. W tym issue nic
nie jest usuwane, przenoszone, regenerowane ani ponownie uruchamiane.

## Cofnięcie decyzji

Cofnięcie sprzątania oznacza odtworzenie potrzebnego pliku z literalnego SHA
`ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8` na
`feature/v2-research-archive`, a nie ponowne generowanie badania. Zmiana zakresu
produktu wymaga nowego issue i nowego ADR-u, który zastępuje ADR-0022. Nie wolno
edytować ADR-0004–ADR-0021 ani zamrożonych dowodów w celu dopasowania historii
do nowego kierunku.

## Konsekwencje

- Zakres v1 jest mniejszy, przewidywalny i niezależny od modelu, Javy, sieci
  oraz badań.
- Późniejsze issue mogą usuwać wykonywalną powierzchnię v2 dopiero po
  sprawdzeniu dokładnej klasyfikacji dowodów.
- Historyczne schematy, wyjątki, wyniki sugestii, cykl życia analizatora i
  `polis.evaluation` zachowują określoną granicę kompatybilności.
- Usunięte sekcje TOML kończą się jawnym, stabilnym błędem zamiast cichego
  zignorowania.
- Pełny stan sprzed sprzątania pozostaje odtwarzalny z archiwum #188.
