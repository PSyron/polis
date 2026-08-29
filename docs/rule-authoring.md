# Autorstwo reguł deterministycznych v1

Ten przewodnik prowadzi od udokumentowanego przypadku błędu do małej,
bezpiecznej reguły. Jest przeznaczony dla bieżącego runtime'u v1, a nie dla
rozbudowy katalogu językowego.

## Najpierw potwierdź granicę

Reguła v1 może wykryć wyłącznie **lokalną i jednoznaczną formę** oraz zaproponować
minimalną zmianę. Nie wnioskuje o znaczeniu, intencji, faktach, czasie, aspekcie,
stylu ani tonie. Jeżeli potrzebuje takiej interpretacji, ma abstynować. Pojedyncza
reguła nie dowodzi kompletności kategorii ani języka polskiego.

Runtime v1 nie korzysta z modelu, w tym Qwen3.8 27B, z serwera modelowego,
LanguageTool ani procesu Java. Nie dodawaj ich jako obejścia niejednoznaczności.
Nowy provider lub rodzina zależna od providera wymaga osobnego issue i decyzji;
brak, niepełne dane, wieloznaczność albo dryft kwalifikowanego providera kończą
się brakiem sugestii.

Nie implementuj reguły tylko dlatego, że potrafisz napisać wzorzec. Zacznij od
atomowego issue z publicznym normatywnym uzasadnieniem, dokładnym zakresem i
bieżącym konsumentem v1. Nie rozszerzaj katalogu historycznego M6.

## Kontrakt i miejsce w kompozycji

Implementacja spełnia `Rule`; dla źródła kwalifikowanego do polityki automatycznej
spełnia także `VersionedRule`. Ma stabilne `Source` rodzaju `rule`, deklaruje
`operation` i `behavior_version`, zwraca `Finding` w stałej kolejności i nie
mutuje wejścia. `RuleRegistration` może zawęzić kategorie źródła. Bieżącym
composition root jest `_make_default_registry()` w `src/polis/analyzer.py`;
to on ustala kolejność, rejestrację i metadane źródeł. Nie rejestruj przykładu
ani nowej reguły bez osobnego zaakceptowanego issue.

Stabilna tożsamość zachowania to co najmniej:

```text
(source, category, operation, behavior_version, source_policy_version)
```

Zmiana `source`, kategorii, operacji albo wersji zachowania jest zmianą
obserwowalnego kontraktu. `source_policy_version` pochodzi z polityki korekty,
nie z implementacji reguły. Źródło zaczyna jako `review-only`; sama pewność lub
kategoria nie daje prawa do automatycznej korekty. Promocja wymaga oddzielnej
kwalifikacji pełnego klucza, dowodu bezpieczeństwa konfliktów i idempotencji
oraz jawnego wpisu polityki.

`Finding.start` i `Finding.end` są indeksami Unicode względem niezmienionego
tekstu wejściowego w zakresie półotwartym `[start, end)`. Zawsze zachodzi
`text[start:end] == original`. Sugestia obejmuje wyłącznie najmniejszy zmieniany
fragment; jeśli bezpieczna poprawka wymaga szerszego kontekstu, reguła abstynuje.

## Mały przykład, który nie jest rejestrowany

Poniższy przykład ilustruje lokalny, deterministiczny kontrakt dla podwójnej
spacji między dwoma niebiałymi znakami. Nie jest plikiem produkcyjnym, nie jest
dodany do `_make_default_registry()` i nie jest propozycją nowej reguły.

```python
import re

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)


class ExampleDoubleSpaceRule:
    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "example.double_space")

    @property
    def operation(self) -> str:
        return "normalize.double_space"

    @property
    def behavior_version(self) -> str:
        return "example-double-space/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = re.search(r"(?<=\S) {2}(?=\S)", text)
        if match is None:
            return ()
        start, end = match.span()
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Podwójna spacja.",
                explanation="Między wyrazami pozostaw jedną spację.",
                original=text[start:end],
                suggestion=" ",
                start=start,
                end=end,
                confidence=Confidence(0.99),
                source=self.source,
            ),
        )
```

Test regresyjny pisz najpierw (RED), uruchom go i sprawdź, że zawodzi z powodu
braku zachowania, a nie błędu importu. Dopiero potem dodaj najmniejszą
implementację (GREEN). Przykładowe asercje dotyczą obserwowalnego kontraktu,
a nie prywatnej metody:

```python
def test_double_space_emits_a_minimal_unicode_span() -> None:
    # Given
    text = "Żółć  ma barwę."
    rule = ExampleDoubleSpaceRule()

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert [
        (item.original, item.suggestion, item.start, item.end)
        for item in findings
    ] == [
        ("  ", " ", 4, 6),
    ]
    assert text[findings[0].start : findings[0].end] == findings[0].original


def test_double_space_abstains_outside_its_local_shape() -> None:
    # Given
    rule = ExampleDoubleSpaceRule()

    # When / Then: hard negative and category filter
    assert rule.find("Żółć ma barwę.", options=AnalysisOptions()) == ()
    assert rule.find(
        "Żółć  ma barwę.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    ) == ()
```

W prawdziwym teście rozdziel każde `When` na osobny przypadek. Przed GREEN
udokumentuj i uruchom przynajmniej jeden pozytyw, hard negative oraz controlled
pair różniący się jednym istotnym warunkiem. Dołóż testy dla wielkości liter,
powtórzeń, wielu zdań, cytatów i literałów/kodu, granic segmentacji, konfliktów
z innymi źródłami oraz braku providera. Dla reguły zależnej od providera testuj
także niepełne, wieloznaczne i zdryfowane dane. Każdy taki przypadek ma kończyć
się abstencją, gdy nie spełnia ścisłej lokalnej granicy.

## Inwentarz, pokrycie i bramki

[Inwentarz reguł](rules.md) jest uporządkowanym snapshotem composition root.
Po zmianie zarejestrowanego źródła aktualizuj jego wiersz, opis zakresu i
powiązane testy. Nie odświeżaj rutynowo baseline'u ani snapshotu pokrycia:
postępuj zgodnie z [kontraktem pokrycia reguł v1](project/rule-coverage.md) i
[ADR-0028](architecture/decisions/0028-conservative-v1-rule-coverage-contract.md).

Rozróżniaj trzy twierdzenia:

- **source existence**: źródło jest stabilnie skomponowane w runtime;
- **behavior coverage**: publiczne przypadki dowodzą dokładnego zachowania
  źródła i jego abstencji;
- **category completeness**: osobne, znacznie silniejsze twierdzenie o
  pokryciu kategorii, którego sam rejestr źródeł nie ustanawia.

Liczba `Source` identities nie jest miarą kompletności języka. Nie zmieniaj
żadnego chronionego, zamrożonego ani zużytego holdoutu, nie uruchamiaj go i nie
dostrajaj na nim reguły. Wydajność mierz osobno, na opisanym publicznym wejściu,
po ustaleniu poprawności; wynik pomiaru nie zastępuje jakościowej kwalifikacji.

## Checklista issue i PR

Przed wysłaniem jednego atomowego commitu/PR sprawdź:

- [ ] issue zawiera lokalny zakres, normatywne uzasadnienie, pozytywy, hard
  negatives, controlled pairs oraz warunki abstencji;
- [ ] reguła ma stabilne `rule:` source, kategorię, operację i wersję
  zachowania, a jej sugestie mają minimalne zakresy `[start, end)`;
- [ ] testy obejmują casing, powtórzenia, wiele zdań, cytaty/literały,
  segmentację, konflikty, filtry kategorii i pewności oraz wariant bez
  providera; nie kwalifikują automatyzacji przez przypadek;
- [ ] źródło pozostaje review-only, chyba że osobne issue zakwalifikowało
  pełny klucz polityki automatycznej;
- [ ] zaktualizowano tylko odpowiedni wiersz [inwentarza](rules.md) i wymagane
  kontrakty, bez nieuzasadnionego odświeżenia snapshotu lub baseline'u;
- [ ] uruchomiono `uv run --locked --extra dev python
  scripts/validate_documentation_inventory.py`, właściwe testy reguł,
  `ruff check .`, `ruff format --check .`, `mypy .` oraz budowę i weryfikację
  artefaktów dystrybucji;
- [ ] niezależne review potwierdziło brak zmian registry, correction policy,
  providera, modelu i chronionych danych, jeśli taki zakres nie był celem issue.
