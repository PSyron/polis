# Publiczne modele analizy

Polis udostępnia niezmienne, typowane modele danych zarówno z `polis`, jak
i `polis.core`. Ten kontrakt opisuje dane analizy i publiczny interfejs
analizatora. Obecny pakiet dostarcza cienki analizator runtime'owy w `polis` oraz
bardziej rygorystyczny kontrakt w
[ADR-0003](architecture/decisions/0003-public-api-and-exception-contract.md).
Narzędzia ewaluacyjne repozytorium w `polis.evaluation` zachowują kompatybilność
importów dla bieżącej linii 0.x zgodnie z
[ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md),
ale nie są głównym interfejsem runtime'owej analizy tekstu.

Wspierany runtime działa offline i jest konserwatywny. Żaden przetestowany model
lokalny nie zakwalifikował się do korekt ani sugestii produkcyjnych, dlatego
domyślnie nie jest wybierany żaden model. Opcjonalny adapter LanguageTool działa
wyłącznie lokalnie, wyłącznie dla zdań i ma wąski zakres: zachowuje tylko pięć
opisanych poniżej identyfikatorów zakwalifikowanych reguł przecinkowych. Adaptery
DOCX/ODT/RTF, GUI i szerokie przepisywanie stylistyczne pozostają poza zakresem
pakietu.

## Zatwierdzony kontrakt analizatora

Przyszłe API z głównej przestrzeni pakietu jest celowo niewielkie:

```python
import polis
from polis import AnalysisOptions, Analyzer

analyzer = Analyzer.from_config("polis.toml")
result: polis.AnalysisResult = analyzer.analyze(
    "Te zdanie zawiera błąd.",
    options=AnalysisOptions(categories={"agreement"}, minimum_confidence=0.8),
)
corrected = result.apply(issue_ids=(result.issues[0].id,))
```

`Analyzer.from_config(path)` odczytuje jawną lokalną konfigurację TOML i nigdy
nie korzysta z sieci. `Analyzer(config)` jest równoważnym konstruktorem, gdy
wywołujący wcześniej zwalidował `AnalyzerConfig`. `analyze()` blokuje wątek
wywołujący; `await analyze_async()` ma identyczne wejścia, kolejność wyników,
filtry i błędy dla aplikacji z pętlą zdarzeń. Przekazanie `None` jako opcji używa
domyślnego `AnalysisOptions()`; w przeciwnym razie filtry kategorii i pewności są
odzwierciedlone w `result.options`.

Jedno wywołanie zwraca kompletny, zwalidowany wynik dla wymaganego
skonfigurowanego zakresu albo zgłasza kontrolowany błąd operacyjny. Nie jest
zwracany częściowy wynik analizy. Zapobiega to wynikowi wyglądającemu na
poprawny, który po cichu pomija backend zakończony błędem. Obecny wynik schematu
w wersji 1 nie ma pola stanu częściowego; każda przyszła funkcja analizy
częściowej wymaga jawnego, wersjonowanego kontraktu wyniku.
Dokładny znacznik kontraktu brzmi: „No partial `AnalysisResult` is returned.”

Domyślnie wyłączona reguła LanguageTool jest udokumentowanym wąskim wyjątkiem:
ponieważ jest opcjonalną regułą best-effort, awarię lokalnej usługi reprezentuje
zero znalezisk tej reguły, natomiast ukończone znaleziska wbudowane pozostają.
Nie zmienia to obsługi błędów wymaganych analizatorów ani backendów LLM i nie
wprowadza pola wyniku częściowego.

`result.apply(issue_ids)` stosuje wyłącznie wskazane znaleziska z danego wyniku.
Waliduje cały wybór przed zmianą wyjścia, odrzuca korekty nieznane, powielone,
pozbawione sugestii, nakładające się albo o tej samej granicy, a następnie
stosuje kompatybilne zastąpienia od prawej do lewej we współrzędnych
oryginalnego tekstu. Pusty wybór zwraca tekst źródłowy. Operacja jest atomowa:
błąd wyboru nie zwraca częściowo poprawionego tekstu.

## Konserwatywna korekta

`Analyzer.correct(text)` jest wygodną ścieżką dla zdania lub akapitu. Wejście
akapitowe jest wspierane przez deterministyczną ścieżkę runtime'u; opcjonalne
ścieżki LanguageTool i fleksji kontekstowej pozostają wyłącznie zdaniowe
i wstrzymują się dla treści wielozdaniowej.
`await Analyzer.correct_async(text)` uruchamia identyczną orkiestrację bez
uruchamiania pętli zdarzeń; wyniki, kolejność, budżety wywołań, błędy i decyzje
polityki są równoważne.
Zwraca `CorrectionResult` z `original_text`, `corrected_text`,
`applied_findings`, `skipped_findings`, `suggestion_outcomes` oraz
`source_policy_version`.
Automatycznie stosuje wyłącznie niekolidujące znaleziska reguł
deterministycznych objęte skalibrowanym kontraktem source-policy. Obecnie są to:

- `agreement.copula`
- `spelling.jestes`
- `spelling.wlasnie`
- `spelling.zeby`
- `syntax.comma_space`
- `syntax.list_space`
- `syntax.quote_space`
- `syntax.sentence_space`
- `languagetool.pl` (wyłącznie pięć jawnych identyfikatorów reguł
  udokumentowanych poniżej)
Pozostałe znaleziska, w tym przypadki wygenerowane przez model i pozbawione
możliwej sugestii, pozostają w `skipped_findings`.

`suggestion_outcomes` jest wersjonowaną krotką telemetryczną dla prób
opcjonalnych backendów. Dla każdej operacji obsługującej sugestie zapisuje:

- `status`: jedno z `complete`, `unavailable`, `timed_out` albo `invalid_response`;
- `backend`: stabilny identyfikator backendu;
- `operation`: nazwę operacji użytej do wywołania sugestii;
- `suggestions`: liczbę sugestii pochodzących z modelu, które utworzyła analiza;
- `model_calls`: rzeczywiste wywołania wykonane dla tej opcjonalnej ścieżki sugestii;
- `protocol_versions`: uporządkowane identyfikatory operacji i wersji specjalistycznych;
- `operation_version`: wersję kontraktu operacji sugestii;
- `source_policy_version`: wersję kontraktu source-policy.

Aktywny kontrakt source-policy `1.2` zezwala na automatyczne zastosowanie
tylko wtedy, gdy zainstalowane zachowanie deterministyczne dokładnie odpowiada
`(source, category, operation, behavior_version, source_policy_version)`,
a następnie spełnia próg pewności tego wpisu. Brakujące metadane zachowania,
nieznane wpisy i każda zmiana tożsamości pozostają do przeglądu; sama pewność
nie nadaje automatycznego uprawnienia, a znaleziska modelu są bezwarunkowo
odrzucane. Dziewięć automatycznych zachowań pozostaje bez zmian względem
historycznego zapisu kwalifikacji source-policy `1.1`. Ten historyczny kontrakt
jako pierwszy zakwalifikował jawne wstawienia przecinka `languagetool.pl`;
source-policy `1.2` zachowuje je wyłącznie jako zachowanie `check.allowlisted_comma`
`pl-6.8-five-rule-comma/1.0`, a nie jako szersze uprawnienie dla LanguageTool
lub całej kategorii.

Domyślny analizator udostępnia również wyłącznie zdaniowe źródła deterministyczne
`syntax.missing_reflexive` i `syntax.missing_correlative`. Obejmują tylko trzy
dokładne konstrukcje udokumentowane w [rules.md](rules.md) i nie zwracają
znaleziska, gdy wejście zawiera wiele zdań. Celowo nie figurują w polityce
automatycznej: `correct()` umieszcza ich znaleziska w `skipped_findings`,
a wywołujący może zastosować wybrane znalezisko przez `apply_suggestions()`.

Znaleziska modelu nigdy nie są automatycznie stosowane przez tę metodę;
wywołujący mogą nadal użyć
`CorrectionResult.apply_suggestions(finding_ids)`, aby jawnie wybrać wpisy
z `skipped_findings`. Metoda atomowo ponownie stosuje automatyczne znaleziska
i wybrane sugestie względem oryginalnego tekstu; wybory nieznane, powielone,
pozbawione możliwej sugestii lub kolidujące korzystają z istniejących
kontrolowanych błędów korekty.
Niezmieniony wynik specjalisty zużywa jedno wywołanie. Zmieniony kandydat lub
propozycja składniowa są walidowane, a następnie zużywają dokładnie jedno
dodatkowe wywołanie weryfikatora przyjmij/odrzuć. Weryfikator nie może zastąpić
propozycji. Zaakceptowane edycje specjalistyczne niosą oryginalne przesunięcia
akapitu i pozostają w `skipped_findings`, dopóki wywołujący jawnie nie wybierze
ich identyfikatorów przez `apply_suggestions()`.

Orkiestracja specjalistyczna jest wstrzykiwana jako zależność przez
`Analyzer(config, specialist_engine=...)`. Wartość domyślna to `None`, więc
zwykła konstrukcja nie wykonuje wywołań specjalistycznych. Issue #60 dostarcza
silnik niezależny od modelu oraz politykę przetestowaną z użyciem fake'ów; to API
nie wybiera ani nie włącza rzeczywistego modelu lub runtime'u.

Powyższe API analizatora jest implementowane przez cienki runtime w `polis`
i pozostaje niewielkie z założenia. `polis.core` i `polis` bezpośrednio
reeksportują ten sam model `AnalysisResult`, a sprawdzane przykłady dowodzą
dwukierunkowej kompatybilności przypisań między oboma importami i wartościami
zwracanymi przez analizator. Stubsy pozostają autorytatywnym kontraktem typów
w `tests/typecheck/stubs/`, a przykłady znajdują się w
`tests/typecheck/api_contract_examples.py`.

### Kontrolowane błędy

Wszystkie kontrolowane błędy operacyjne dziedziczą po `PolisError` i udostępniają
stabilne `code`, flagę `retryable` oraz bezpieczne mapowanie `context`. Nigdy nie
zawierają analizowanego tekstu, fragmentów źródłowych, sugestii, promptów,
pełnego wyjścia backendu ani sekretów. Pełna hierarchia i lista dozwolonego
kontekstu znajdują się w ADR-0003.

```python
from polis import (
    AnalysisTimeoutError,
    Analyzer,
    BackendUnavailableError,
    ConfigurationError,
    CorrectionConflictError,
    InvalidBackendResponseError,
    UncorrectableFindingError,
    UnknownFindingError,
)

try:
    analyzer = Analyzer.from_config("polis.toml")
except ConfigurationError as error:
    assert error.code == "configuration.invalid"
    assert error.retryable is False
    assert error.context["path"] == "polis.toml"

try:
    result = Analyzer.from_config("polis.toml").analyze("Tekst")
except BackendUnavailableError as error:
    assert error.retryable is True
    assert error.context["backend"]
except AnalysisTimeoutError as error:
    assert error.code == "analysis.timeout"
    assert error.context["backend"]
except InvalidBackendResponseError as error:
    assert error.retryable is False
    assert error.context["backend"]

try:
    result.apply(issue_ids=("finding_missing",))
except UnknownFindingError as error:
    assert error.code == "correction.unknown_finding"
    assert error.retryable is False
    assert error.context["finding_ids"] == "finding_missing"

try:
    result.apply(issue_ids=("finding_without_suggestion",))
except UncorrectableFindingError as error:
    assert error.code == "correction.uncorrectable_finding"
    assert error.retryable is False
    assert error.context["finding_ids"] == "finding_without_suggestion"

try:
    result.apply(issue_ids=("overlapping-first", "overlapping-second"))
except CorrectionConflictError as error:
    assert error.code == "correction.conflict"
    assert error.retryable is False
    assert error.context["finding_ids"]
```

## Konstruowanie wyniku

```python
from polis import (
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)

text = "Te zdanie zawiera błąd."
finding = Finding.create(
    category=Category.AGREEMENT,
    severity=Severity.ERROR,
    message="Niezgodność rodzaju zaimka i rzeczownika.",
    explanation="Forma „Te” nie zgadza się z rzeczownikiem „zdanie”.",
    original="Te zdanie",
    suggestion="To zdanie",
    start=0,
    end=9,
    confidence=Confidence(0.98),
    source=Source(SourceKind.RULE, "agreement"),
)
result = AnalysisResult(
    text=text,
    issues=(finding,),
    options=AnalysisOptions(
        categories={"agreement", "spelling"},
        minimum_confidence=0.75,
    ),
)
```

Modele są zamrożonymi dataclasses. Kolekcje są normalizowane do niezmiennych
krotek lub frozensetów, dlatego wyniku nie można zmienić po walidacji.

## Semantyka pól

`Category` ma wartości `inflection`, `agreement`, `syntax`, `spelling`,
`punctuation` oraz `style`. `Severity` ma wartości `error`, `warning`
i `suggestion`. Poziom ważności opisuje siłę prezentacji; nie zmienia wartości
pewności.

`Finding` zawiera:

| Pole | Znaczenie |
| --- | --- |
| `id` | Deterministyczny identyfikator służący do wyboru bazowego znaleziska w wyniku. |
| `category` | Typowana kategoria problemu. |
| `severity` | Typowany poziom ważności prezentacji. |
| `message` | Krótki opis widoczny dla użytkownika. |
| `explanation` | Powód zgłoszenia tekstu. |
| `original` | Dokładny wycinek wejścia wskazany przez `start:end`; pusty dla wstawienia i potencjalnie zawierający wyłącznie białą spację. |
| `suggestion` | Minimalne zastąpienie różniące się od `original` albo `None`, gdy brak uzasadnionego zastąpienia. Pusty napis oznacza usunięcie niepustego oryginału. |
| `start`, `end` | Półotwarty zakres w oryginalnym wejściu. |
| `confidence` | Skończona liczba od `0.0` do `1.0` włącznie. |
| `source` | Rodzina analizatora i stabilna nazwa serializowana jako `rule:name` albo `llm:name`. |

`AnalysisOptions(categories=None)` oznacza wszystkie kategorie. Pusta kolekcja
kategorii oznacza brak kategorii. Napisy kategorii są normalizowane do wartości
`Category`. `minimum_confidence` ma domyślną wartość `0.0` i jest normalizowane
do `Confidence`.

## Odniesienia do rozszerzeń i stabilności

Punkty rozszerzeń i granice udokumentowano w:

- [regułach](rules.md)
- [personalizacji](customization.md)
- [pracy offline](offline-operation.md)
- [metodologii ewaluacji i zbiorach danych](evaluation-dataset.md)
- [protokołach](architecture/protocols.md)
- [prywatności](privacy.md)
- [kompatybilności i SemVer](compatibility.md)
- [ograniczeniach](limitations.md)

## Przesunięcia i walidacja

Przesunięcia zawsze używają indeksów napisu Pythona i konwencji półotwartej
`[start, end)`. Liczą punkty kodowe Unicode, a nie bajty UTF-8 ani wizualne
klastry grafemów. Na przykład:

```python
text = "🙂 Te zdanie"
assert text[2:11] == "Te zdanie"
```

`Finding` odrzuca przesunięcia logiczne lub ujemne, odwrócone zakresy, zakresy,
których długość w punktach kodowych różni się od `len(original)`, puste
komunikaty lub wyjaśnienia, niepoprawne identyfikatory i źródła oraz niepoprawne
wartości pewności, w tym `NaN`, nieskończoność i wartości numeryczne zbyt duże
dla skończonego floata Pythona. Ujemne zero pewności jest normalizowane do
dodatniego `0.0`, dzięki czemu ma jedną kanoniczną reprezentację JSON.
`original` jest zachowywane dosłownie: wstawienie używa `start == end`
i `original == ""`, natomiast usunięcie białej spacji może użyć `original`
zawierającego wyłącznie białą spację oraz `suggestion == ""`. `AnalysisResult`
dodatkowo sprawdza, czy każdy zakres mieści się w `text`, czy `text[start:end]`
jest równe `original` oraz czy identyfikatory znalezisk są unikatowe. Wstawienia
o zerowej szerokości są poprawne na każdej granicy aż do końca wejścia.
Niepoprawna konstrukcja w Pythonie zgłasza `TypeError` dla błędnego typu wartości
i `ValueError` dla wartości spoza kontraktu.

Każda sugestia inna niż `None` musi dokładnie różnić się od `original`. Odrzuca
to zarówno zwykłe zastąpienia no-op, jak i przypadek o zerowej szerokości
`original == suggestion == ""`. Użyj `None`, aby reprezentować znalezisko bez
uzasadnionego zastąpienia. Poprawne wstawienie ma puste `original` i niepustą
sugestię; poprawne usunięcie ma niepuste (potencjalnie zawierające wyłącznie
białą spację) `original` i pustą sugestię.

`Finding.create()` tworzy identyfikator w postaci
`finding_<32 lowercase hexadecimal characters>`. Haszuje kanoniczne dane
tożsamości wersjonowanym 128-bitowym skrótem BLAKE2b. Tożsamość składa się
z kategorii, źródła, początku, końca, oryginalnego tekstu i opcjonalnej sugestii.
Komunikat, wyjaśnienie, poziom ważności i pewność są danymi prezentacyjnymi lub
kalibracyjnymi i nie zmieniają identyfikatora. Napisy tożsamości są haszowane
dokładnie w przekazanej postaci, z uwzględnieniem reprezentacji Unicode,
wielkości liter i białej spacji; Polis nie stosuje normalizacji Unicode ani
tekstu. Zmiana tożsamości zmienia identyfikator. Odrębne znaleziska o tej samej
tożsamości mają zatem ten sam identyfikator i nie mogą współistnieć w jednym
wyniku; każda inna kolizja identyfikatorów również jest odrzucana. Identyfikatory
nie są przeznaczone do użycia jako trwałe międzydokumentowe klucze bazy danych.

## Schemat JSON w wersji 1

Użyj funkcji swobodnych albo wygodnych metod wyniku:

```python
from polis import AnalysisResult, analysis_result_from_json, analysis_result_to_json

encoded = analysis_result_to_json(result)
assert result.to_json() == encoded
assert analysis_result_from_json(encoded) == result
assert AnalysisResult.from_json(encoded) == result
```

Schemat najwyższego poziomu ma postać:

```json
{
  "schema_version": 1,
  "text": "Te zdanie zawiera błąd.",
  "options": {
    "categories": ["agreement", "spelling"],
    "minimum_confidence": 0.75
  },
  "issues": [
    {
      "id": "finding_b89cbdbde56272994279f763b05cf63b",
      "category": "agreement",
      "severity": "error",
      "message": "Niezgodność rodzaju zaimka i rzeczownika.",
      "explanation": "Forma „Te” nie zgadza się z rzeczownikiem „zdanie”.",
      "original": "Te zdanie",
      "suggestion": "To zdanie",
      "start": 0,
      "end": 9,
      "confidence": 0.98,
      "source": "rule:agreement"
    }
  ]
}
```

Serializacja jest deterministyczna: klucze obiektów i kategorie opcji są
sortowane, polskie znaki pozostają nieucieczkowane, a nieistotna biała spacja
jest pomijana. Kolejność znalezisk jest zachowywana. Cykl
serializacji-deserializacji zachowuje tekst, opcje, kolejność znalezisk,
rozróżnienie sugestii `None` i pustego napisu, identyfikatory oraz wszystkie
wartości typowanych pól.

Dekoder jest celowo rygorystyczny. Odrzuca powielone klucze obiektów, brakujące
lub nieznane pola, nieznane wersje schematu, nieznane wartości enum, niepoprawne
identyfikatory i źródła, wartości logiczne tam, gdzie wymagane są liczby, liczby
nieskończone, identyfikatory niezgodne z ich polami tożsamości, powielone
kategorie lub identyfikatory znalezisk oraz znaleziska niezgodne z tekstem
źródłowym.

## Oczekiwania dotyczące kompatybilności

Schemat w wersji 1 jest dokładnym schematem zamkniętym. Producenci muszą emitować
każde udokumentowane pole, a konsumenci nie mogą po cichu ignorować nieznanych
pól. Zmiany dodające, usuwające, zmieniające nazwę lub interpretację pola;
dodające wartość enum; albo zmieniające dane wejściowe tożsamości identyfikatora
wymagają nowej wersji schematu i jawnej ścieżki kompatybilności. Doprecyzowania
dokumentacji i poprawki walidacji, które nie zmieniają przyjmowanych danych,
mogą zachować bieżącą wersję.

Obecny dekoder przyjmuje wyłącznie schemat w wersji 1. Aplikacje utrwalające
wyniki powinny utrwalać `schema_version` i nie mogą zakładać, że przyszły pakiet
odczyta niewspieraną wersję bez udokumentowanej migracji.
