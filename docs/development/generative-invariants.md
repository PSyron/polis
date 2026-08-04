# Deterministyczne niezmienniki strukturalne

Issue #123 dostarcza wspólny generator przeznaczony wyłącznie do testów,
wymagany przed issue potomnymi #95 dotyczącymi właściwości strukturalnych.
Generator używa należącego do repozytorium wersjonowanego indeksu SHA-256
zamiast mutowalnego strumienia losowego: każdy przypadek syntetyczny wynika z
wersji generatora, ziarna i indeksu przypadku, dzięki czemu można go niezależnie
odtworzyć na każdej wspieranej platformie.

## Kontrakt ograniczonego generatora

Bieżący generator to `unicode-structural-v1`. Jego domyślne ziarno to `95001`,
domyślny budżet wynosi 64 przypadki, a sztywne maksimum — 256 przypadków.
Wspierane rodziny Unicode to:

- `ascii`
- `polish_diacritics`
- `non_bmp`
- `combining_marks`
- `lf`
- `crlf`
- `punctuation`
- `quotes`

Przykładowo błąd właściwości raportujący
`generator=unicode-structural-v1 seed=95001 case=7` identyfikuje przypadek do
wybrania z `generate_unicode_text_cases(seed=95001, count=8)[7]`. Metadane
odtworzenia celowo identyfikują przypadek bez wypisywania jego tekstu.

## Kontrakt szybkiego CI i bezpieczne odtwarzanie

Każde zadanie wspieranej macierzy szybkiego CI dostarcza pełną konfigurację
wygenerowanych niezmienników w istniejącym kroku `Run pytest suite`:

```yaml
env:
  POLIS_GENERATIVE_GENERATOR_VERSION: unicode-structural-v1
  POLIS_GENERATIVE_SEED: 95001
  POLIS_GENERATIVE_CASES: 64
```

Ten krok zachowuje pojedyncze filtrowane polecenie pytest, dlatego testy
badawcze, wolne i modelowe pozostają wykluczone. Bezargumentowy generator
przeznaczony wyłącznie do testów używa tych wartości: bez konfiguracji korzysta
ze swoich istniejących wartości domyślnych; jeśli jakakolwiek wartość jest
obecna, działa fail-closed, chyba że podano wszystkie trzy wartości, wersja jest
dokładna, ziarno jest 64-bitową liczbą całkowitą bez znaku, a budżet mieści się
od 1 do 256. Polityka workflow szybkiego CI dodatkowo przypina akceptowaną
wersję, ziarno i budżet 64 przypadków, odrzuca brakujące, powielone, niewłaściwie
umieszczone, nieprawidłowe lub nadmierne metadane oraz zachowuje istniejący
10-minutowy limit czasu zadania dla każdego elementu wspieranej macierzy.

Aby odtworzyć błąd strukturalny, zachowaj w jego komunikacie wyłącznie bezpieczne
metadane (`generator`, `seed` i `case`) i uruchom właściwy moduł właściwości z tą
samą pełną konfiguracją. Na przykład błąd segmentacji zgłoszony jako
`generator=unicode-structural-v1 seed=95001 case=7` można odtworzyć bez
umieszczania tekstu w poleceniu ani danych wyjściowych:

```console
POLIS_GENERATIVE_GENERATOR_VERSION=unicode-structural-v1 POLIS_GENERATIVE_SEED=95001 POLIS_GENERATIVE_CASES=64 uv run --locked --extra dev pytest tests/test_segmentation_properties.py -v
```

Budżet 64 przypadków jest celowy: obejmuje zgłoszony przypadek, a zarazem
zachowuje pokrycie każdej zadeklarowanej rodziny. Nie zmniejszaj go do indeksu
przypadku ani nie kopiuj wygenerowanego tekstu, fragmentów źródłowych, promptów
lub analizowanych dokumentów do polecenia, logu CI, issue lub raportu.

## Odrzucone alternatywy

Nie wybrano Hypothesis, ponieważ dodałby zależność deweloperską i wymagałby
zarządzania nią, zanim repozytorium będzie miało zastosowanie dla zmniejszania
przypadków albo utrwalonych przykładów. Raportowanie kontrprzykładów jest też
szersze niż kontrakt błędów tego narzędzia pomocniczego, ograniczony do ziarna.

Nie wybrano `random.Random`, ponieważ mutowalny strumień pseudolosowy wymagałby
przypięcia pełnej sekwencji wywołań, aby dryf był jawny. Nie zapewnia on
niezależnie indeksowanego kontraktu odtwarzania oferowanego przez wyprowadzenie
SHA-256.

## Bezpieczne błędy i granica zakresu

Każda wygenerowana właściwość strukturalna musi wywoływać
`assert_structural_invariant(condition, invariant=..., replay=...)` z bezpiecznym
identyfikatorem niezmiennika. Fałszywy warunek raportuje wyłącznie ten
identyfikator i metadane odtworzenia; wygenerowany tekst nie może wystąpić w
reprezentacjach obiektów ani komunikatach błędów.

Wygenerowane niezmienniki strukturalne zapewniają wyłącznie ograniczoną
różnorodność strukturalną. Nie zastępują autorskich testów regresyjnych ani
bramek korpusów i nie stanowią deklaracji jakości języka polskiego. Harness nie
może otrzymywać prywatnego tekstu, uruchamiać ewaluacji modelu lub holdoutu ani
stać się nieograniczonym fuzzingiem CI.

## Ukończone niezmienniki strukturalne i ryzyka rezydualne

Ukończone zestawy issue potomnych #95 używają tego samego syntetycznego źródła
64 przypadków do sprawdzania:

- granic segmentacji akapitów i zdań, ciągłości, wycinków, pokrycia i dokładnej
  rekonstrukcji;
- granic publicznych znalezisk i wyników, oryginalnych wycinków, normalizacji,
  stabilnych identyfikatorów i wierności kanonicznego JSON;
- symetrii konfliktów korekt, deterministycznej normalizacji, stosowania od
  prawej do lewej i odrzucania nieprawidłowych wyborów w trybie fail-closed;
- kolejności rejestru reguł, obsługi duplikatów oraz parytetu rejestracji
  synchronicznej i asynchronicznej;
- parytetu wyniku, translacji offsetów i kontrolowanych błędów synchronicznego i
  asynchronicznego pipeline'u analizy.

Łącznie kontrole te dostarczają dowodów strukturalnych dla wszystkich ośmiu
skatalogowanych rodzin: `ascii`, `polish_diacritics`, `non_bmp`,
`combining_marks`, `lf`, `crlf`, `punctuation` i `quotes`. Nie ustanawiają
wyczerpującego pokrycia Unicode, gramatyki, ortografii lub stylu języka polskiego,
recall, precision ani wydajności na korpusie. Autorskie regresje i wersjonowane
bramki korpusów pozostają autorytatywnymi dowodami językowymi. Ograniczony
generator nie zmniejsza przypadków, nie używa aktywnych modeli ani holdoutów i
może pominąć interakcje poza swoim syntetycznym katalogiem; każda odkryta wada
wymaga osobnego issue zaczynającego od regresji.

## Właściwości korekty

Issue #129 stosuje to samo syntetyczne źródło 64 przypadków do właściwości
konfliktów i stosowania korekt. Jego niezależna wyrocznia ADR-0003 sprawdza
symetryczne konflikty dla nakładających się zastąpień, powielonych wstawek i
wstawki na każdej domkniętej granicy zastąpienia. Skrót wyprowadzony z każdej
tożsamości odtworzenia zmienia zgodne pozycje zastąpień, usunięć i wstawek,
jednocześnie utrzymując wstawki ściśle poza zastąpieniami. Każdy niepusty
wybrany podzbiór musi normalizować się deterministycznie, stosować niezależnie od
każdej kolejności wybranych identyfikatorów i być równy osobno wyprowadzonej
rekonstrukcji od prawej do lewej.

Właściwość przekazuje również wybory konfliktowe, nieaktualne, nieznane,
powielone i niemożliwe do poprawienia. Każdy z nich musi zakończyć się błędem
przed utworzeniem wyjścia, pozostawić niezmienny wynik bez zmian i raportować
niezaliczoną właściwość wyłącznie przez jej niezmiennik oraz metadane odtworzenia
z #123. Jest to ograniczone pokrycie kontraktu strukturalnego, a nie deklaracja
jakości korekt, wydajności korpusu, modeli lub ewaluacji.
