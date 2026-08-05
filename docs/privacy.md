# Gwarancje prywatności

Polis v1 analizuje tekst lokalnie. Domyślny `Analyzer` wykonuje wyłącznie
deterministyczne reguły w procesie aplikacji: nie wysyła wejścia przez sieć, nie
uruchamia usługi pomocniczej i nie pobiera zasobów.

## Dane wejściowe i wyniki

- CLI czyta tekst ze standardowego wejścia, argumentu albo jawnie wskazanego
  pliku; sam go nie utrwala ani nie przesyła.
- `Finding` i `CorrectionResult` pozostają w pamięci procesu wywołującego.
  Zapisywanie wyników, logowanie i kontrola dostępu należą do aplikacji
  integrującej Polis.
- `PolisError.context` zawiera wyłącznie bezpieczne metadane operacji, takie jak
  `operation`, `backend`, `path` i `finding_ids`; nie zawiera analizowanego
  tekstu, promptów ani surowych odpowiedzi.

## Konfiguracja i audyt

Konfiguracja jest lokalnym plikiem TOML przekazanym jawnie do
`Analyzer.from_config()`. Runtime v1 interpretuje i wspiera tylko `[analysis]`
z kluczami `categories` i `minimum_confidence`. Dokładnie historyczne tabele
`[backend]`, `[language_tool]`, `[contextual_inflection]` i
`[vendored_language_tool]` są odrzucane kontrolowanym `ConfigurationError`.
Inne nieznane tabele i klucze parser obecnie ignoruje; nie są wspieranym
interfejsem i nie należy na tym zachowaniu polegać.

Przed wydaniem uruchom test instalacji offline, sprawdź zawartość artefaktów i
nie dodawaj do repozytorium sekretów ani prywatnych tekstów. Dowody tych kontroli
zawiera [audyt prywatności](privacy-audit.md).
