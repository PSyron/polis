# Interfejs wiersza poleceń

Polecenie `polis` służy do ręcznej analizy tekstu i do jawnego zastosowania
wybranych znalezisk. Działa lokalnie: po instalacji domyślnych zależności nie
łączy się z siecią, nie wymaga modelu ani procesu Java, a tekst nie opuszcza
procesu.

```console
python -m pip install polis-nlp
polis --version
polis --help
polis analyze --help
```

Globalne opcje podaj przed subcommandem. W szczególności plik konfiguracji
zawsze występuje przed `analyze`:

```console
polis --config polis.toml analyze "Witaj,świecie."
```

`--version` wypisuje wersję programu, a `-h` / `--help` opisują dostępne
komendy i opcje. `--config PATH` odczytuje lokalny plik TOML z domyślnymi
ustawieniami analizy; wspierana sekcja ma postać:

```toml
[analysis]
categories = ["agreement", "spelling", "punctuation"]
minimum_confidence = 0.8
```

Pełny przykład znajduje się w [`examples/polis.toml`](../examples/polis.toml).

## Wejście

Komenda `analyze` przyjmuje tekst na dokładnie jeden z trzech alternatywnych
sposobów. Nie łącz wejścia pozycyjnego z `--stdin` ani `--file`.

```console
# Tekst pozycyjny
polis analyze "Witaj,świecie."

# Standardowe wejście
printf '%s\n' 'Witaj,świecie.' | polis analyze --stdin --json

# Plik zapisany w UTF-8
printf '%s\n' 'Witaj,świecie.' > input.txt
polis analyze --file input.txt --json
```

Argument pozycyjny to `text`. `--stdin` czyta całe standardowe wejście, a
`--file PATH` czyta wskazany plik zakodowany w UTF-8. CLI zapisuje stdout i
stderr w UTF-8, również gdy środowisko procesu odziedziczy inny kodek.

## Wyniki analizy

Bez `--json` wynik jest czytelną dla człowieka listą wierszy rozdzielonych
tabulatorami: `id`, `category`, `severity`, komunikat, źródło i pewność.
Gdy nie ma znalezisk, program wypisuje `No findings.`.

```console
polis analyze "Witaj,świecie."
```

Wartość `id` identyfikuje konkretne znalezienie i jest potrzebna przy
`--apply`. Dla programów użyj `--json`:

```console
polis analyze "Witaj,świecie." --json
```

Bez `--apply` dokument JSON jest bezpośrednim `AnalysisResult`. Ma pola
`schema_version`, `text`, `options` i `issues`; każdy element `issues` zawiera
m.in. `id`, kategorię, komunikat, sugestię, źródło, pewność oraz zakres
`[start, end)` w oryginalnym tekście.

## Filtrowanie i konfiguracja

`--category CATEGORY` ogranicza analizę do kategorii i można je powtarzać.
`--minimum-confidence VALUE` przyjmuje próg od `0.0` do `1.0`. Flaga na
wierszu poleceń zastępuje tylko odpowiadającą jej wartość z TOML; flaga kategorii
nie zmienia progu z TOML, a flaga progu nie zmienia kategorii z TOML.

```console
polis --config polis.toml analyze "Witaj,świecie." \
  --category punctuation \
  --category spelling \
  --minimum-confidence 0.5 \
  --json
```

## Jawne stosowanie znalezień

`--apply ID [ID ...]` przyjmuje co najmniej jeden identyfikator znalezienia z
wyniku tej samej analizy. Nie oznacza automatycznej korekty: to świadomy wybór
użytkownika. Poniższy przykład stosuje znalezienie pokazane przez wcześniejsze
wywołanie dla dokładnie tego tekstu:

```console
polis analyze "Witaj,świecie." --json \
  --apply finding_f398d601dc7f6b443522c17c3774c308
```

Po `--apply --json` najwyższy poziom odpowiedzi **nie** jest samym
`AnalysisResult`; ma postać:

```json
{
  "analysis_result": {"schema_version": 1, "text": "Witaj,świecie.", "issues": [{"id": "finding_f398d601dc7f6b443522c17c3774c308"}]},
  "corrected_text": "Witaj, świecie."
}
```

`analysis_result` zawiera pełny wynik analizy, a `corrected_text` tekst po
wybranych poprawkach. Bez `--json` udane `--apply` wypisuje tylko poprawiony
tekst.

Polis automatycznie stosuje wyłącznie zakwalifikowane, niekolidujące poprawki
w API korekty. Znalezienia `review-only` oraz `skipped` nie uzyskują przez to
prawa do automatyzacji: można je zastosować tylko po wskazaniu ich ID. Dotyczy
to także sugestii opartych na Morfeusz2 — lokalna dostępność tego optional extra
nie zmienia ich statusu na automatyczny.

## Kody zakończenia i błędy

- `0` — analiza lub jawne zastosowanie wskazanych ID zakończyły się powodzeniem.
- `1` — nie można zastosować wybranego ID, na przykład jest nieznany albo
  poprawki kolidują.
- `2` — błąd użycia, konfiguracji lub odczytu wejścia, na przykład brak pliku
  wskazanego przez `--file`.

Błędy trafiają na stderr z prefiksem `error:`. Komunikat opisuje problem
konfiguracji, wejścia albo wyboru korekty, lecz nie wypisuje analizowanego tekstu.
Poprawne wejście plikowe musi być UTF-8.

Zobacz także [szybki start](quick-start.md), [publiczne API](public-api.md),
[pracę offline](offline-operation.md) i [politykę prywatności](privacy.md).
