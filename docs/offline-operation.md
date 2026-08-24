# Praca offline

Domyślny `Analyzer(AnalyzerConfig())` wykonuje wyłącznie lokalne reguły
deterministyczne. Nie otwiera połączeń sieciowych, nie uruchamia procesu
pomocniczego i nie pobiera zasobów.

```python
from polis import Analyzer, AnalyzerConfig

result = Analyzer(AnalyzerConfig()).analyze("Witaj,świecie.")
```

Konfiguracja jest lokalnym plikiem TOML wskazanym przez wywołującego. Tylko
sekcja `[analysis]` jest interpretowana i wspierana; jej klucze to `categories`
i `minimum_confidence`. Dokładnie historyczne tabele `[backend]`, `[language_tool]`,
`[contextual_inflection]` i `[vendored_language_tool]` są odrzucane przez
`ConfigurationError` z kodem `configuration.unsupported_section`. Inne nieznane
tabele i klucze parser obecnie ignoruje; nie są wspieranym interfejsem i nie
należy na tym zachowaniu polegać.

Testy i dystrybucje weryfikują tę granicę w izolowanym środowisku. Aplikacja
wywołująca odpowiada za własne logowanie i magazynowanie tekstu; Polis nie
wysyła wejścia poza proces.

## Opcjonalna morfologia

Extra `polis-nlp[morphology]` instaluje Morfeusz2 1.99.15 wyłącznie dla czterech
zamkniętych sugestii: `Nie widzę czerwony samochód.` →
`Nie widzę czerwonego samochodu.`, `Te duże okno jest otwarte.` →
`To duże okno jest otwarte.` oraz `Oni czyta książkę.` →
`Oni czytają książkę.` oraz `Potrzebuję pomoc.` → `Potrzebuję pomocy.`.
Wszystkie pozostają do przeglądu. Dostawca analizuje
i generuje formy lokalnie; nie otwiera połączenia, nie pobiera słownika i nie
uruchamia procesu Java.

Runtime przypina i lokalnie sprawdza następującą oczekiwaną tożsamość providera:

- `package_version`: `1.99.15`;
- `dictionary_id`: `pl.sgjp.sgjp-2026.06.01`;
- `dictionary_notice_sha256`:
  `84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`.

Diagnoza nie wymaga sieci ani czytania kodu: odczytaj
`Analyzer(AnalyzerConfig()).morphology_status`. Dla `drifted` porównaj
`expected_identity.package_version`, `expected_identity.dictionary_id` i
`expected_identity.dictionary_notice_sha256` z odpowiadającymi polami
`actual_identity`. W ten sposób widać zarówno wartość oczekiwaną, jak i
faktyczną dla każdego elementu, który spowodował dryft.

Stan `drifted` emituje dokładnie jedno `UserWarning` na proces, nawet jeśli
tworzonych jest więcej analizatorów. Stan `unavailable` nie emituje ostrzeżenia:
brak opcjonalnego extra `morphology` jest prawidłową, udokumentowaną
konfiguracją.

Brak extra, błąd dostawcy, niepełne dane, niejednoznaczna analiza lub dryft
któregokolwiek elementu nadal powodują abstencję reguł zależnych od morfologii;
pozostałe reguły działają wtedy normalnie. Pinning, fail-closed i kształt
znalezisk pozostają bez zmian — status oraz ostrzeżenie tylko ujawniają przyczynę
abstencji.
