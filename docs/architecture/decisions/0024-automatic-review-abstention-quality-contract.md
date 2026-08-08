# ADR-0024: Kontrakt automatycznej korekty, przeglądu i abstencji dla jakości v1

- Status: Accepted
- Data: 2026-08-08
- Właściciel: Paweł Cyroń
- Issue: #237

## Kontekst

ADR-0022 ograniczył Polis v1 do konserwatywnego runtime'u offline, ale jego
ogólne sformułowanie o fleksji i rekcji nie rozdziela obecnego, zamkniętego
pokrycia od docelowej zdolności rozwijanej w kolejnych issue. Brakowało też
jednego obserwowalnego kontraktu odróżniającego automatyczną korektę,
znalezisko do przeglądu i abstencję.

Issue #237 powstało, gdy domyślny `Analyzer` rejestrował dziesięć reguł. Później
issue #230–#235 dodały sześć zatwierdzonych, zamkniętych zachowań. W chwili
przyjęcia tej decyzji composition root w `src/polis/analyzer.py` i bieżący
wykaz `docs/rules.md` zawierają 16 źródeł. Liczba dziesięć opisuje więc migawkę
z chwili utworzenia issue, a nie aktualny kontrakt runtime'u.

Umbrella #236 wyznacza opcjonalną, uporządkowaną ścieżkę rozwoju lokalnej
morfologii. Nie wybiera dostawcy, nie zatwierdza nowej zależności produkcyjnej
i dopuszcza negatywny wynik kwalifikacji.

## Decyzja

### Trzy obserwowalne wyniki

Polis v1 rozróżnia dokładnie trzy wyniki oceny potencjalnej poprawki:

1. **Automatyczna korekta.** `Analyzer.correct()` umieszcza znalezisko w
   `CorrectionResult.applied_findings` i zmienia `corrected_text` w jego
   półotwartym zakresie `[start, end)` bez osobnego wyboru użytkownika.
   Zachowanie jest dopuszczalne tylko wtedy, gdy ma jednoznaczną minimalną
   poprawkę, nie koliduje z wcześniej wybraną poprawką i jego pełna tożsamość
   znajduje się w aktywnej polityce źródeł.
2. **Znalezisko do przeglądu.** `Analyzer.analyze()` zwraca `Finding`, ale
   `Analyzer.correct()` nie zmienia z jego powodu tekstu i umieszcza je w
   `CorrectionResult.skipped_findings`. Użytkownik może zastosować je jawnie
   przez `CorrectionResult.apply_suggestions()`. Sama obecność sugestii,
   kategoria ani wartość `confidence` nie nadają prawa do automatycznej
   korekty.
3. **Abstencja.** `Analyzer.analyze()` nie zwraca `Finding` dla rozważanego
   problemu, a `Analyzer.correct()` pozostawia odpowiadający mu tekst bez
   zmiany. Abstencja nie jest błędem operacyjnym ani częściową sugestią; oznacza,
   że runtime nie ma dostatecznych danych do uzasadnienia minimalnej poprawki.

Poprawne znalezisko, które koliduje z inną wybraną poprawką, pozostaje do
przeglądu zamiast być zastosowane automatycznie. Nie zmienia to wymagań
abstencji dla nieuzasadnionego wyniku morfologicznego.

### Fleksja i rekcja w v1

Fleksja i rekcja są wspieranymi, docelowymi obszarami jakości v1, wdrażanymi
iteracyjnie i konserwatywnie. Nie stanowi to deklaracji ogólnej poprawności
morfologicznej języka polskiego. Wspierane zachowanie w danym wydaniu obejmuje
wyłącznie dokładne reguły wymienione w bieżącym wykazie oraz zakwalifikowane
wersje ich zachowania.

Aktualne zamknięte pokrycie związane z morfologią obejmuje między innymi:

- `rule:agreement.copula` dla ograniczonych wzorców zgody łącznika;
- `rule:agreement.te_zdanie` dla dokładnego wzorca `Te zdanie` → `To zdanie`;
- `rule:inflection.negated_widziec` dla dokładnej konstrukcji rekcji po
  zaprzeczonym `widzieć`;
- `rule:syntax.missing_destination_preposition` dla dokładnej konstrukcji
  z brakującym `do` przed celem ruchu.

Pierwsza reguła może działać automatycznie wyłącznie pod swoim dokładnym
kluczem polityki. Pozostałe trzy są znaleziskami do przeglądu. Żadna z nich nie
uprawnia do ekstrapolacji na inne czasowniki, rzeczowniki, przypadki,
przyimki, szyk zdania ani znaczenie wypowiedzi.

Szersza zdolność morfologiczna może wejść do v1 wyłącznie przez kolejne bramy
umbrella #236:

1. kwalifikację konkretnego dostawcy offline na aktywnym protokole jakości;
2. pierwszy rzeczywisty konsument jako jedna reguła fleksyjna review-only;
3. osobne, zamknięte piony dla zgody i wybranej rekcji;
4. prerejestrowany, jednorazowy holdout zamrożonego runtime'u;
5. osobną promocję wyłącznie tych dokładnych zachowań, które spełniły bramę
   automatycznej korekty.

Negatywny wynik dowolnej kwalifikacji jest pełnoprawnym wynikiem: dostawca nie
wchodzi do runtime'u, a niezakwalifikowane zachowanie pozostaje review-only
albo kończy się abstencją. Polis v1 pozostaje kompletnym produktem bez takiego
dostawcy.

### Obowiązkowa abstencja morfologiczna

Wynik dostawcy morfologii jest niezaufanymi danymi. Runtime musi wstrzymać się
od utworzenia `Finding`, gdy analiza potrzebna do danej reguły jest:

- nieznana lub zawiera wartość spoza jawnie obsługiwanego schematu;
- niepełna, w tym pozbawiona wymaganych cech, formy albo zakresu;
- wieloznaczna, czyli dopuszcza więcej niż jedną uzasadnioną analizę lub
  minimalną poprawkę bez deterministycznego rozstrzygnięcia;
- niespójna z oryginalnym tekstem, jego zakresem `[start, end)` albo pozostałymi
  cechami wymaganymi przez regułę;
- opisana inną wersją zachowania dostawcy niż dokładnie zakwalifikowana wersja.

Brak dostawcy, brak obsługi konstrukcji i brak unikalnego kandydata również
prowadzą do abstencji. Nie wolno zastąpić brakujących danych domysłem, obniżyć
progu przez `confidence`, częściowo zastosować propozycji ani zdegradować
nieznanego wyniku do pozornie bezpiecznej reguły ogólnej.

### Tożsamość polityki automatycznej

Prawo do automatycznej korekty nadal jest związane z dokładną krotką:

`(source, category, operation, behavior_version, source_policy_version)`

Każdy element należy porównać dokładnie. Zmiana źródła, kategorii, operacji,
wersji zachowania reguły lub wersji polityki odbiera prawo do automatycznej
korekty do czasu osobnej kwalifikacji tej nowej tożsamości. Zgodność samego
`source`, kategorii, poziomu pewności albo podobieństwo do wcześniej
zakwalifikowanego zachowania nie wystarczają.

Wersja dostawcy morfologii oraz wersja jego danych muszą być częścią
kwalifikowanej wersji zachowania reguły albo jej reprodukowalnej tożsamości.
Każdy drift wykryty przed utworzeniem znaleziska prowadzi do abstencji; drift
wykryty przy kontroli polityki nie może prowadzić do automatycznej korekty.

### Granice produktu

Rozwój fleksji i rekcji nie zmienia granic ADR-0022:

- cały analizowany tekst i wszystkie dane pośrednie pozostają na urządzeniu;
- wspierany runtime nie wykonuje żądań sieciowych i nie wymaga usługi
  zewnętrznej;
- dostawca nie może wymagać modelu językowego, modelowego rankera, Java ani
  pełnego LanguageTool;
- wynik dostawcy jest danymi, nigdy instrukcją;
- korekta nie obejmuje stylu, tonu, dyskursu, faktów, intencji, znaczenia,
  zgodności czasów ani aspektu;
- niejednoznaczność semantyczna zawsze kończy się abstencją;
- żadna nowa zależność produkcyjna nie jest dopuszczona przed osobną
  kwalifikacją, decyzją i przeglądem licencji.

### Relacja do wcześniejszych decyzji

ADR-0024 nie zmienia treści ADR-0001–ADR-0023 ani chronionych dowodów. Zastępuje
jedynie interpretację wcześniejszych zapisów, według której liczba dziesięciu
lub trzynastu źródeł jest trwałym kontraktem bieżącego runtime'u, oraz
doprecyzowuje ogólne sformułowanie ADR-0022 o fleksji i rekcji.

Bieżącym źródłem liczby i kolejności reguł pozostają composition root oraz
`docs/rules.md`. Zmiana tej listy wymaga własnego issue, testów regresyjnych i
aktualizacji dokumentacji; sama zmiana liczby nie rozszerza automatycznych
uprawnień żadnej reguły.

## Konsekwencje

- Użytkownik może odróżnić automatyczną zmianę, sugestię wymagającą wyboru i
  brak uzasadnionej sugestii wyłącznie na podstawie publicznych wyników API.
- Aktualne 16 źródeł pozostaje bez zmian; ten ADR nie implementuje reguły ani
  dostawcy morfologii i nie zmienia polityki `1.2`.
- B1 i dalsze etapy #236 pozostają dozwoloną ścieżką rozwoju v1, ale żaden etap
  nie może pominąć kwalifikacji ani promować całej kategorii naraz.
- Nowe pokrycie fleksji, zgody lub rekcji zaczyna jako dokładne zachowanie
  review-only. Automatyzacja jest późniejszą, odrębną decyzją dla pojedynczej
  tożsamości polityki.
- Brak kwalifikacji lub drift wersji nie obniża jakości runtime'u: skutkuje
  abstencją, a nie zgadywaniem.

## Rozważone alternatywy

- **Zawęzić v1 do obecnych reguł i uznać ogólną fleksję oraz rekcję za
  aspiracyjne.** Odrzucono, ponieważ utraciłoby to zaakceptowany cel jakości v1
  i bez potrzeby zamknęłoby bezpieczną, etapową ścieżkę #236.
- **Uznać całą kategorię fleksji lub rekcji za automatyczną po kwalifikacji
  dostawcy.** Odrzucono, ponieważ dostawca nie nadaje uprawnień; kwalifikacji
  podlega każde dokładne zachowanie i jego pełna tożsamość polityki.
- **Zwracać review-only dla każdego niepełnego lub wieloznacznego wyniku
  morfologicznego.** Odrzucono, ponieważ widoczna sugestia bez unikalnego
  uzasadnienia przenosi ryzyko na użytkownika i narusza zasadę fail-closed.
- **Przywrócić runtime do dziesięciu reguł, aby zgadzał się z pierwotnym opisem
  #237.** Odrzucono, ponieważ liczba była migawką, a sześć późniejszych zachowań
  zostało dostarczonych i scalonych w osobnych, zatwierdzonych issue.
