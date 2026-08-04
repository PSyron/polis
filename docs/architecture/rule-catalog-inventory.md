# Inwentarz katalogu reguł

Status: dowód dla issue #148 i dane wejściowe do decyzji o własności w #149.

Maszynowo czytelnym źródłem tego snapshotu jest
[`rule-catalog-inventory.json`](rule-catalog-inventory.json). Test porównuje 12
kandydatów katalogu z domyślnymi i opcjonalnymi rejestracjami runtime'u
standardowego analizatora oraz z każdym wpisem polityki automatycznych poprawek
`1.2`.

Ten inwentarz nie zmienia zachowania runtime'u ani publicznego kontraktu.
Zapisuje obecny composition root, w tym luki polityki fail-closed, przed
rozstrzygnięciem własności katalogu i pierwszeństwa wyboru.

## Obecna granica

Standardowy analizator tworzy domyślnie dziesięć reguł deterministycznych oraz
dwie dodatkowe reguły lokalne tylko wtedy, gdy ich transporty są skonfigurowane
lub wstrzyknięte. Wszystkie 12 używają `SourceKind.RULE`, udostępniają operację
i wersję zachowania, dlatego są obecnymi kandydatami katalogu.

`availability` odróżnia rejestrację domyślną od opcjonalnej. Nie twierdzi, że
lokalna zależność jest zainstalowana, sprawna ani uruchomiona. Obie opcjonalne
reguły mogą współdzielić dołączoną sesję stdio LanguageTool albo używać osobnych
wstrzykniętych lub skonfigurowanych transportów bez zmiany tożsamości źródła.

Obiekt automatycznej korekty zapisuje dowód polityki, zamiast nadawać
uprawnienie. `eligible` oznacza, że obecnie istnieje dokładny wpis źródła,
kategorii, operacji, wersji zachowania, wersji polityki i progu pewności.
`fail_closed_review_only` oznacza, że dokładny wpis polityki nie istnieje;
znalezisko pozostaje tylko do przeglądu. W szczególności dwie reguły składni
szczątkowej i fleksja kontekstowa nie są stosowane automatycznie.

## Rozróżnienie kategorii

Obecnie istnieją dwa różne fakty dotyczące kategorii:

- `category` jest jedyną kategorią, którą może emitować implementacja reguły;
- `registry_categories` jest zakresem wyboru zapisanym w `RuleRegistration`.

Dla wszystkich dziesięciu reguł domyślnych `registry_categories` ma wartość
`null`. Rejestr wybiera je zatem dla każdego niepustego żądania kategorii, a
każda reguła filtruje się samodzielnie. Dwie reguły opcjonalne mają jawne
jednoelementowe zakresy rejestracji. Inwentarz zachowuje oba fakty, ponieważ #149
musi zdecydować, który z nich będzie należeć do przyszłego katalogu.

## Konstrukcja i odbiorcy

`Analyzer` jest composition root, a `polis.analyzer._make_default_registry`
tworzy każdą standardową rejestrację. Analiza runtime'u korzysta z rejestru przez
`find()`. Korekta dodatkowo używa `source_behavior()`, aby podjąć dokładną
decyzję polityki fail-closed. Źródło znaleziska uczestniczy także w tworzeniu
jego stabilnego identyfikatora.

Obecnie nie istnieje produkcyjny odbiorca czytelnego dla człowieka opisu reguły.
Role w snapshotcie JSON są dokumentacją dla #149 i nie wolno traktować ich jako
powodu dodania abstrakcji runtime'u przed powstaniem odbiorcy.

## Jawne wykluczenia

- LLM i backendy znalezisk emitują dynamiczne źródła `llm:`, nie są
  zarejestrowane w `DeterministicRuleRegistry` i zawsze nie kwalifikują się do
  automatycznej korekty.
- Transporty HTTP/stdio i sesje procesów wspierają wykonanie reguł, ale nie
  emitują znalezisk jako niezależne źródła reguł.
- `TypoSpellingRule` i ręcznie przekazane wartości `RuleRegistration` są
  mechanizmami rozszerzeń, a nie konkretnymi źródłami standardowego analizatora.
- Syntetyczne reguły testowe, typowane przykłady i przykłady wyłącznie
  dokumentacyjne nie są produkcyjnymi rejestracjami runtime'u.

## Pytania przekazane do #149

1. Czy katalog jest właścicielem wyłącznie 12 dobranych standardowych źródeł,
   czy także rejestracji niestandardowych?
2. Czy źródłem prawdy jest katalog, każda implementacja reguły, czy rejestracja
   w composition root?
3. Czy metadane kategorii katalogu reprezentują emitowane kategorie, zakres
   wyboru, czy oba fakty?
4. Czy kolejność rejestracji jest gwarancją zgodności?
5. Jak zachować rozróżnienie między `available`, `enabled by default`,
   `configured` i stanem transportu?
6. Czy jedno opcjonalne źródło powinno zachować jeden wpis katalogu dla
   transportów wstrzykniętych, HTTP i dołączonego stdio?
7. Jak katalog może odwoływać się do dowodów polityki, nie stając się allowlistą
   automatycznych poprawek?
8. Czy opisy są stabilnymi metadanymi widocznymi dla użytkownika, czy wyłącznie
   dokumentacją?
9. Jak reprezentować granicę między wersjonowanymi regułami niestandardowymi a
   niewersjonowaną ogólną `TypoSpellingRule`?
10. Czy przyszła inspekcja powinna udostępniać dobrany katalog, efektywny
    skonfigurowany rejestr, czy oba?

## Walidacja i prywatność

`tests/test_rule_catalog_inventory.py` tworzy rejestry z transportami, które
zgłaszają błąd przy każdej próbie analizy tekstu. Porównuje wyłącznie tożsamości
źródeł i metadanych. Test nie używa korpusu, modelu, holdoutu, żądania sieciowego
ani prywatnego tekstu, a awarie zawierają wyłącznie metadane katalogu.
