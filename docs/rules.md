# Dodawanie reguł deterministycznych

`polis.rules` odpowiada za rejestrowanie i wykonywanie reguł deterministycznych.

Wpis rejestru to `RuleRegistration` zawierający:

- `rule`: obiekt implementujący protokół `polis.core.Rule`;
- `categories`: jawne kategorie, które ta reguła może emitować.

Rejestr wymusza:

- jedną rejestrację dla każdego unikatowego `rule.source`;
- stabilną kolejność wykonywania reguł zgodną z kolejnością rejestracji;
- filtrowanie reguł według kategorii;
- walidację wyjścia względem zadeklarowanych kategorii;
- wykrywanie powielonych identyfikatorów znalezisk.

Użyj następującego minimalnego wzorca:

```python
from polis.core import Category, AnalysisOptions
from polis.rules import DeterministicRuleRegistry, RuleRegistration

registry = DeterministicRuleRegistry(
    [
        RuleRegistration(
            rule=MyRule(),
            categories=frozenset({Category.AGREEMENT, Category.SPELLING}),
        )
    ]
)

findings = registry.find("Tekst do analizy", options=AnalysisOptions(categories=None))
```

`source` musi być stabilne i unikatowe dla każdej zarejestrowanej reguły (na
przykład `rule:agreement`), ponieważ identyfikatory znalezisk powstają z
`category`, `source`, `start`, `end` oraz `original`.

## Reguły pomocnicze pisowni

Pierwsze deterministyczne reguły pisowni są zaimplementowane jako niewielkie
reguły pomocnicze z dokładnym dopasowaniem wzorca w `polis.rules.spelling`.

- `SpellingZebyRule` poprawia `zeby` -> `żeby`.
- `SpellingWlasnieRule` poprawia `wlasnie` -> `właśnie`.
- `SpellingJestesRule` poprawia `jestes` -> `jesteś`.

Reguły te są celowo konserwatywne: dopasowują wyłącznie pełne granice wyrazów,
korzystają z bramkowania kategorią (`Category.SPELLING`) i zachowują wielkość
liter dla tokenów zapisanych od wielkiej litery oraz samymi wielkimi literami.

Trudne przypadki negatywne są udokumentowane w testach i obejmują poprawne słowa
(`właśnie`, `jesteś`) oraz dłuższe napisy, które jedynie zawierają fragment
literówki (`wlasniew`, `zebyj`).

## Reguły zgodności

`AgreementCopulaRule` wykonuje ukierunkowaną kontrolę o wysokiej precyzji dla
częstych niezgodności łącznika w stałych wzorcach zaimek+czasownik.

- `AgreementCopulaRule` (`Category.AGREEMENT`) poprawia oczywiste przypadki,
  takie jak `ona jestem` -> `ona jest`.

Reguła celowo przedkłada precyzję nad szerokie pokrycie: jest ograniczona do
niewielkiego zestawu podmiotów i wariantów czasownika w pierwszej osobie, dzięki
czemu jej zachowanie pozostaje przewidywalne.

## Reguły składni i interpunkcji

Wybrane reguły pomocnicze składni i interpunkcji znajdują się w
`polis.rules.syntax` i są podzielone według kategorii:

- `SyntaxCommaSpacingRule` (`Category.PUNCTUATION`) wstawia brakujące spacje po
  przecinkach i pomija częste fragmenty skrótów, takie jak `itp,` i `m.in,`.
- `SyntaxListSpacingRule` (`Category.SYNTAX`) wstawia brakującą spację po znaczniku
  listy na początku wiersza (`1.`, `-`, `*`), gdy kolejny token zaczyna się
  bezpośrednio po nim.
- `SyntaxQuoteSpacingRule` (`Category.PUNCTUATION`) dodaje brakującą spację po
  otwierającym cudzysłowie bezpośrednio połączonym ze słowem.
- `SyntaxMissingReflexiveRule` (`Category.SYNTAX`) sugeruje minimalne wstawienie
  `się` w rozpoczynających zdanie konstrukcjach `On/Ona/Ono boi …` oraz
  `Nie spodziewaliśmy …`.
- `SyntaxMissingCorrelativeRule` (`Category.SYNTAX`) sugeruje minimalne wstawienie
  `tym` w rozpoczynających zdanie konstrukcjach `Im …, bardziej …`.

Obie rezydualne reguły składni wymagają dokładnie jednego zdania, nie sprawdzają
modelu ani danych wzorcowych i wstrzymują się dla wejścia wielozdaniowego. Ich źródła
to `rule:syntax.missing_reflexive` i `rule:syntax.missing_correlative`. Ich
jednorazowy holdout nie zawierał żadnej kwalifikującej się konstrukcji, więc nie
mógł wykazać nietrywialnej precyzji. Oba znaleziska pozostają do przeglądu i są
wyłączone z automatycznego kontraktu source-policy `1.2`.

Wszystkie reguły składni obsługują filtrowanie kategorii przez wspólny mechanizm
`options.categories` i zwracają deterministyczne znaleziska ze stabilnymi
identyfikatorami.

## Opcjonalna reguła interpunkcyjna LanguageTool

`LocalLanguageToolRule` jest rejestrowana tylko po skonfigurowaniu
`[language_tool]`. Przyjmuje osobno zainstalowany lokalny serwer LanguageTool 6.8
i mapuje wyłącznie
`BRAK_PRZECINKA_KTORY`, `BRAK_PRZECINKA_SPOJNIK_PROSTY`,
`BRAK_PRZECINKA_ZE`, `BRAK_PRZECINKA_ZEBY` oraz `WOLACZ_BEZ_PRZECINKA`
na minimalne wstawienia przecinka ze źródłem `rule:languagetool.pl` i pewnością
`0.85`. Aktywny kontrakt source-policy `1.2` zezwala na automatyczne stosowanie
tych znalezisk tylko wtedy, gdy zainstalowane zachowanie to
`check.allowlisted_comma` / `pl-6.8-five-rule-comma/1.0`, pełny klucz polityki
jest zgodny i znaleziska nie kolidują. Kontrakt source-policy `1.1` pozostaje
historycznym zapisem kwalifikacji tej listy dozwolonych pięciu identyfikatorów.

Reguła przelicza przesunięcia Java UTF-16 na przesunięcia punktów kodowych
Pythona, minimalizuje szerokie zastąpienia, odrzuca niejednoznaczne alternatywy
i kolidujące znaleziska oraz porzuca każdą nieznaną regułę lub zmianę inną niż
przecinek. Wybór czterech reguł z #70 (trzy nowo udostępnione identyfikatory oraz
już włączony `BRAK_PRZECINKA_ZE`) zachował precyzję `1.00`: 5 prawdziwie
pozytywnych edycji i zero zmian chronionych przypadków negatywnych na
142-zdaniowym holdoucie. Ogólne znaleziska LanguageTool dotyczące pisowni,
gramatyki, stylu i morfologii są celowo wyłączone.

Dla dwóch zweryfikowanych konstrukcji z parą przecinków zaakceptowane znalezisko
otwierające może również utworzyć przecinek zamykający. Domknięcie zdania
względnego wymaga dokładnej kotwicy leksykalnej `Name która mieszka obok`, po
której występuje osobny żeński predykat zdania głównego w czasie przeszłym.
Domknięcie wtrącenia wymaga `Name proszę`, po którym występuje jedna z wcześniej
zweryfikowanych kotwic trybu rozkazującego: `zamknij` lub `zadzwoń`. Oba kształty
muszą obejmować jedno pełne zdanie i wymagają odpowiadającej zakwalifikowanej
reguły LanguageTool; żaden nie działa jako samodzielne wyszukiwanie w korpusie.
Inne zdania względne, wtrącenia, cytaty, adresy URL, liczby i kształty
wielozdaniowe wstrzymują się do osobnej kwalifikacji. Oba wstawienia zachowują
oryginalne przesunięcia Unicode w konwencji półotwartej oraz kanał source-policy
`rule:languagetool.pl`.

## Reguła sugestii fleksji kontekstowej

`ContextualInflectionRule` implementuje cztery rodzaje dowodów zamrożone przez
ADR-0015: zgodność sąsiadujących nazw własnych, dopełniacz po `bez`, celownik po
`przygląd… się` oraz celownik po `podzięk…`. Wywołuje wstrzyknięty
`ContextMorphologyTransport`, waliduje każdy kompletny tag i pochodzący z treści
identyfikator kandydata `ltpl:` oraz emituje wyłącznie unikatową formę ze
skończonego zbioru. Niejednoznaczność, niewspierana morfologia, konflikty,
niepoprawne odpowiedzi i awarie transportu nie zwracają znaleziska. Wejście
zawierające zero lub wiele zdań jest odrzucane przed wywołaniem lokalnego
transportu.

Znaleziska używają `Category.INFLECTION`, źródła
`rule:languagetool.contextual_inflection`, pewności `0.95` oraz oryginalnych
przesunięć Unicode `[start, end)`. Są wyłącznie sugestiami i są wyłączone
z automatycznego kontraktu source-policy `1.2`.

## Tożsamości zachowań polityki automatycznej

Aktywny kontrakt source-policy automatycznej korekty ma wersję `1.2`. Zachowuje
dziewięć zachowań zakwalifikowanych według historycznego kontraktu source-policy
`1.1`, lecz każde
identyfikuje pełnym kluczem `(source, category, operation, behavior_version,
source_policy_version)`. Sama nazwa źródła, kategoria lub wartość pewności nie
wystarcza. Polityka odczytuje metadane operacji i wersji zachowania
z zarejestrowanej reguły deterministycznej; brakujące lub zmienione metadane
pozostawiają znalezisko do przeglądu. Każda zmiana wersji zachowania wymaga nowego
bezpośredniego dowodu i nowego dokładnego wpisu polityki. Znaleziska modelu
zawsze podlegają przeglądowi.

| Źródło | Kategoria | Operacja | Wersja zachowania | Wersja source-policy |
| --- | --- | --- | --- | --- |
| `rule:agreement.copula` | `agreement` | `replace.copula_form` | `agreement-copula/1.0` | `1.2` |
| `rule:spelling.jestes` | `spelling` | `replace.common_typo` | `spelling-jestes/1.0` | `1.2` |
| `rule:spelling.wlasnie` | `spelling` | `replace.common_typo` | `spelling-wlasnie/1.0` | `1.2` |
| `rule:spelling.zeby` | `spelling` | `replace.common_typo` | `spelling-zeby/1.0` | `1.2` |
| `rule:syntax.comma_space` | `punctuation` | `normalize.comma_spacing` | `syntax-comma-space/1.0` | `1.2` |
| `rule:syntax.list_space` | `syntax` | `normalize.list_marker_spacing` | `syntax-list-space/1.0` | `1.2` |
| `rule:syntax.quote_space` | `punctuation` | `normalize.quote_spacing` | `syntax-quote-space/1.0` | `1.2` |
| `rule:syntax.sentence_space` | `punctuation` | `normalize.sentence_spacing` | `syntax-sentence-space/1.0` | `1.2` |
| `rule:languagetool.pl` | `punctuation` | `check.allowlisted_comma` | `pl-6.8-five-rule-comma/1.0` | `1.2` |

## Normalizacja analizy

Normalizacja jest wykonywana w `polis.analysis` przez następujące
deterministyczne kroki:

1. `filter_findings` usuwa znaleziska spoza żądanego zestawu kategorii oraz
   poniżej `minimum_confidence`.
2. `deduplicate_findings` zachowuje jednego kanonicznego reprezentanta dla
   każdego stabilnego identyfikatora znaleziska.
3. `prioritize_findings` sortuje znaleziska według pozycji w tekście źródłowym,
   następnie według pewności i kryteriów rozstrzygających remisy, aby wyjście
   było deterministyczne.
4. `normalize_findings` uruchamia cały potok i jest standardową funkcją pomocniczą
   dla ścieżki publicznej.

Te same reguły mają zastosowanie do każdego wyjścia analizatora przed jego
prezentacją.

## Deterministyczne stosowanie korekt

`polis.analysis` i `polis.core` walidują identyfikatory wybranych znalezisk
i stosują zastąpienia od prawej do lewej za pomocą funkcji pomocniczych
z `polis.correction`.

- `findings_conflict` koduje kompatybilność na poziomie zakresów.
- `validate_non_conflicting_corrections` zgłasza wyjątek dla niepoprawnych
  zestawów wyboru.
- `sort_findings_for_application` stosuje kompatybilne znaleziska w stabilnej
  kolejności od prawej do lewej.

`AnalysisResult.apply` jest publicznym API korekty wyłącznie przez jawny wybór.
