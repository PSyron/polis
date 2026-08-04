# Weryfikacja pracy offline

Projekt jest przeznaczony do analizy bez dostępu do sieci zewnętrznej.
Analizowany tekst nie opuszcza urządzenia użytkownika.

## Wspierana konfiguracja offline

- Domyślny runtime używa `Analyzer` i rejestru reguł deterministycznych w całości
  w jednym procesie. Przy `AnalyzerConfig(use_local_heuristic_backend=False)`
  i bez opcjonalnych sekcji LanguageTool Polis nie wymaga Java, procesu
  LanguageTool, modelu ani dostępu do sieci.
- Opcjonalny mock backend używa lokalnego parsowania promptu i lokalnego
  transportu (`MockHeuristicBackend`).
- Silnik specjalistyczny pozostaje wyłączony, dopóki wywołujący jawnie nie
  wstrzyknie jednocześnie routera i backendu. Silnik #60 sam nie wykonuje I/O;
  wstrzyknięty adapter nadal odpowiada za wykazanie transportu wyłącznie
  lokalnego.
- Opcjonalna obsługa LanguageTool przez loopback HTTP łączy się wyłącznie
  z osobno uruchomionym serwerem LanguageTool 6.8 pod numerycznym adresem pętli
  zwrotnej. Nigdy nie używa publicznego API LanguageTool, nazwy DNS, proxy ani
  przekierowania.
- Opcjonalny tryb LanguageTool przez dołączone stdio uruchamia bezpośrednio jeden
  stale działający lokalny proces potomny z jawnej ścieżki bezwzględnej. Nie
  otwiera gniazd ani nie wykonuje niejawnego pobierania lub aktualizacji.
- Instalacja zależności używa plików lock `uv` z repozytorium.

## Polecenie weryfikacyjne

Uruchom poniższe polecenie, aby zweryfikować analizę przy zablokowanym ruchu
wychodzącym:

```console
pytest -q tests/test_offline_verification.py
```

Fixtura testowa blokuje `socket.create_connection`, dlatego każda przypadkowa
próba użycia sieci wychodzącej powoduje niepowodzenie testu, zanim rozpocznie
się analiza.

## Oczekiwane wyniki

- Analyzer działa poprawnie w domyślnym trybie deterministycznym
  (`use_local_heuristic_backend = false`) bez uruchamiania opcjonalnej obsługi
  LanguageTool.
- Analyzer działa poprawnie po włączeniu lokalnego mock backendu przez
  konfigurację.
- Kontrole nie zapisują w logach prywatnego tekstu wejściowego.

## Opcjonalna ścieżka zdaniowa dołączonego LanguageTool

Zbuduj przypięty podzbiór podczas jawnego przygotowania zależności:

```console
cd third_party/languagetool-pl
./scripts/build.sh
```

Następnie skonfiguruj jedną sesję stdio działającą wyłącznie dla zdań:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Analyzer uruchamia proces leniwie i używa go ponownie do zakwalifikowanych
kontroli interpunkcji oraz syntezy kontekstowej. Procesy należące do analizatora
zamykaj przez menedżer kontekstu albo `Analyzer.close()`. Source-policy `1.1`
zachowuje automatyczne stosowanie zakwalifikowanych wstawień przecinka, a
fleksję kontekstową pozostawia do review. Brak pliku wykonywalnego, timeout,
wadliwa albo zbyt duża odpowiedź, przerwany potok lub zatrzymany proces powodują
bezpieczne odrzucenie (fail-closed), bez usuwania wbudowanych znalezisk
deterministycznych i bez umieszczania analizowanego tekstu w błędzie.

Runner nie wiąże żadnego portu i nie otwiera gniazd sieciowych. Usunięcie
`[vendored_language_tool]` wyłącza proces. Nie łącz tej sekcji z żadnym z dwóch
poniższych trybów opcjonalnych. Dołączone drzewo źródeł, cache Mavena, pliki JAR
i wygenerowane wyniki budowania Java są artefaktami budowania repozytorium oraz
są wykluczone z wheel i dystrybucji źródłowych Polis.

## Opcjonalny tryb zgodności LanguageTool przez pętlę zwrotną

Uruchom osobno zainstalowany serwer LanguageTool 6.8 nasłuchujący na interfejsie
pętli zwrotnej, a następnie włącz go jawnie:

```toml
[language_tool]
base_url = "http://127.0.0.1:8081"
timeout_seconds = 1.0
```

Pomiń całą sekcję, aby wyłączyć adapter. Konfiguracja nie uruchamia ani nie
pobiera serwera. Przed wysłaniem analizowanego tekstu Polis wykonuje żądanie
preflight ze stałym tekstem i wymaga nazwy serwera `LanguageTool` oraz wersji
`6.8`. Zachowywane są wyłącznie poddane review znaleziska przecinkowe z
`BRAK_PRZECINKA_KTORY`,
`BRAK_PRZECINKA_SPOJNIK_PROSTY`, `BRAK_PRZECINKA_ZE`,
`BRAK_PRZECINKA_ZEBY` i `WOLACZ_BEZ_PRZECINKA`. Awaria lokalnego sidecara nie
tworzy opcjonalnych znalezisk i nie odrzuca znalezisk z reguł działających
w procesie Polis.

Starsza ścieżka fleksji kontekstowej używa bezpośrednio runnera stdio zbudowanego
ze źródeł, lecz uruchamia osobny proces dla każdego kwalifikującego się zdania:

```toml
[contextual_inflection]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Ścieżka musi być bezwzględna i wykonywalna. Każde wywołanie uruchamia ten lokalny
proces, używa zachowującej tagi operacji `synthesize_context` i zamyka proces po
otrzymaniu odpowiedzi dla zdania. Awarie nie tworzą sugestii fleksyjnej.
Sugestie nigdy nie są stosowane automatycznie. Wejście wielozdaniowe znajduje
się poza zakresem tej reguły i nie powoduje wywołania procesu morfologii
kontekstowej.

## Granice wspieranej konfiguracji

Ta weryfikacja nie uruchamia ani nie waliduje osobno zainstalowanych runtime'ów.
Zanim zewnętrzny backend zostanie uznany za wspierany, dodaj dla jego runtime'u
jawną politykę offline i test integracyjny.
Obecna wspierana konfiguracja nie włącza żadnego rzeczywistego modelu
specjalistycznego.

Na potrzeby audytów odtwarzalności na poziomie źródeł repozytorium zawiera
`third_party/languagetool-pl` z przypiętą proweniencją LanguageTool i lokalnymi
skryptami budowania. Ten katalog jest jawnie wykluczony z pakowanych artefaktów.

Po jednorazowym przygotowaniu i zbudowaniu zależności z dostępem do sieci
dołączony podzbiór można ponownie budować i uruchamiać bez dostępu do sieci:

```console
cd third_party/languagetool-pl
POLIS_LT_OFFLINE=1 ./scripts/build.sh
./scripts/run_stdio.sh
```

Proces stdio nie wiąże portu. Ładuje zapisane w repozytorium polskie reguły
i zasoby 6.8 oraz zwraca wyłącznie identyfikatory pięciu reguł przecinkowych
zakwalifikowanych na korpusie.
