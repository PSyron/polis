# Polski zbiór ewaluacyjny

Dane do dostrajania są utrzymywane osobno w
`data/finetuning/bielik_1_5b_v1`. Korpus v3 pozostaje przeznaczony wyłącznie do
ewaluacji, a użycie jego rekordów, znormalizowanych szablonów, encji
i oczekiwanych wyjść w treningu jest zabronione. Kontrakt izolacji opisuje
`docs/architecture/finetuning-dataset.md`.

Moduły ewaluatora, walidatory, metryki i zapisane w repozytorium korpusy opisane
w tym dokumencie są narzędziami deweloperskimi repozytorium oraz zasobami
proweniencji. Wspierają pomiar jakości, przegląd i bramki wydania; nie są głównym
interfejsem runtime'owym produktu. Wspierany runtime korzysta z typowanych,
publicznych modeli wyniku analizy z `polis` / `polis.core` i nie zależy od
dostępu do holdoutu w pracy deweloperskiej.

To rozdzielenie stanowi część granicy runtime-first linii 0.x. Domyślny produkt
działa offline, jest konserwatywny i nie wymaga zakwalifikowanego modelu
lokalnego ani LanguageTool. Opcjonalne pokrycie LanguageTool pozostaje wąskie
i wyłącznie zdaniowe; adaptery DOCX/ODT/RTF, GUI i przepisywanie stylistyczne są
poza zakresem. Duże korpusy, holdouty, raporty, eksperymenty i zasoby treningowe
pozostają w repozytorium i są wyłączone z artefaktów wheel oraz dystrybucji
źródłowej. Istniejące importy `polis.evaluation` zachowują kompatybilność dla
bieżącej linii 0.x zgodnie z
[ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md);
tej przestrzeni nazw nie należy mylić z głównym API analizy.

`src/polis/evaluation/datasets/v1/cases.json` jest początkowym, niewielkim
i wersjonowanym zbiorem jakościowym dla Polis. Jest zbiorem wzorcowym podlegającym
przeglądowi, a nie korpusem ani deklaracją pokrycia produkcyjnego. Walidator
w `polis.evaluation.dataset` przyjmuje wyłącznie wersję 1 schematu i odrzuca
nieznane pola, dlatego zmiany kontraktu wymagają jawnej wersji schematu.

Raporty ewaluacji identyfikują rzeczywiście wczytane źródło, zamiast zakładać
ścieżkę domyślną. Wyliczają skrót zwalidowanego zbioru danych zapisanego jako
kanoniczny JSON UTF-8
z posortowanymi kluczami obiektów i bez nieistotnej białej spacji. Zmiany
wyłącznie formatowania zachowują zatem ten sam SHA-256, natomiast każda zmiana
treści kanonicznej, w tym proweniencji, tworzy nowy skrót.

## Schemat i interpretacja

Obiekt zbioru danych ma `schema_version`, stabilne `id`, `provenance` zbioru
oraz `cases`. Każdy przypadek ma zapisane małymi literami `id` w konwencji
snake-case, `outcome`, źródłowy `text`, własne `provenance` oraz
`expected_findings`. Zamknięty kształt znaleziska to:

```json
{
  "category": "spelling",
  "start": 8,
  "end": 15,
  "original": "napewno",
  "suggestion": "na pewno",
  "rationale": "The standard Polish expression is written as two words."
}
```

Przesunięcia są indeksami punktów kodowych Unicode Pythona w niezmodyfikowanym
wejściu i używają półotwartego przedziału `[start, end)`. Walidator wymaga, aby
`text[start:end]` było równe `original`. Niepusta sugestia jest wstawieniem, gdy
`start == end`; pusta sugestia jest usunięciem tylko wtedy, gdy `original` jest
niepuste. Każda korekta musi dokładnie różnić się od oryginalnego fragmentu.

Oczekiwane znaleziska muszą być deterministyczne przy stosowaniu od prawej do
lewej względem oryginalnych przesunięć. Niepuste zakresy zastąpień nie mogą się
nakładać. Dwa wstawienia w tym samym przesunięciu są odrzucane, ponieważ ich
kolejność jest niejednoznaczna. Wstawienie jest również odrzucane na początku,
wewnątrz lub na końcu niepustego zakresu zastąpienia. Wstawienia są dozwolone
wyłącznie w przesunięciach znajdujących się ściśle poza zakresami zastąpień.

`outcome: "incorrect"` wymaga co najmniej jednego oczekiwanego znaleziska.
`outcome:
"correct"` jest jawnym trudnym przypadkiem negatywnym i musi zawierać
dokładnie `"expected_findings": []`; nie oznacza to, że dowolne preferencje
stylistyczne są błędami. Kategorie są dokładnie publicznymi wartościami
`Category`: `inflection`, `agreement`, `syntax`, `spelling`, `punctuation` oraz
`style`.

## Proweniencja, licencjonowanie i przegląd

Każdy obiekt proweniencji zbioru danych i przypadku zapisuje źródło, licencję
`CC0-1.0`, datę utworzenia, stan przeglądu i notatki. Zapisane przypadki są
autorskimi, syntetycznymi polskimi przykładami projektu i mają oznaczenie
`human-reviewed`. CC0-1.0 pozwala dalszym ewaluatorom ponownie wykorzystywać
przykłady, a proweniencja nadal umożliwia audyt ich pochodzenia i granicy przeglądu.

Nigdy nie dodawaj tekstu prywatnego, poufnego, dostarczonego przez użytkownika,
pozyskanego automatycznie z sieci, skopiowanego ani pochodzącego z korpusu, jeśli jego proweniencja
i warunki redystrybucji nie zostały sprawdzone w dedykowanej zmianie. Przed
zaproponowaniem materiału z rzeczywistego świata usuń bezpośrednie
identyfikatory i quasi-identyfikatory przez anonimizację, lecz zawsze, gdy to
możliwe, preferuj nowe przykłady syntetyczne. Nie umieszczaj tekstu wygenerowanego
przez model jako danych wzorcowych: nie może on ustanowić niezależnego celu jakości.
Przed zmianą tego zbioru opiekun musi przeprowadzić ludzki przegląd gramatyki,
kategorii, dokładnych przesunięć Unicode, fragmentu, minimalnej korekty oraz
stanu trudnego przypadku negatywnego.

Zmiany muszą zachowywać rygorystyczny schemat i dodawać kontradyktoryjne testy
walidatora, gdy tylko możliwy staje się nowy niepoprawny stan. Dodawaj trudne
przykłady bez znalezisk obok podobnych przypadków błędnych, aby chronić przed
fałszywie pozytywnymi wynikami. Każdy przypadek utrzymuj na tyle mały, aby
umożliwiał przegląd językowy i licencyjny.

## Granica względem eksperymentu zależności

`experiments/nlp_dependencies/cases.json` pozostaje osobnym, diagnostycznym
benchmarkiem zależności na licencji CC0. Jego próby tokenizacji i morfologii
mierzą możliwości narzędzi kandydackich; nie są tutaj kopiowane i nie wolno ich
traktować jako wzorcowych etykiet ewaluacji ani progów wydania. Ten zbiór danych
dostarcza późniejszym pracom nad jakością niezależnie zweryfikowane oczekiwane
znaleziska, bez utożsamiania tego eksperymentu z dokładnością analizatora.

## Korpus korekt LLM E2E

`tests/fixtures/e2e/polish_correction_corpus.json` i jego odpowiednik XML są
również autorskimi, syntetycznymi polskimi przykładami projektu wydanymi jako
CC0-1.0. Rekordy zaplanowane przez LLM obejmują dokładne minimalne korekty;
rekordy negatywne są trudnymi kontrolami bezpieczeństwa dla poprawnych imion,
nazwisk, interpunkcji i gramatycznego nacechowanego szyku wyrazów. JSON jest
źródłem używanym przez benchmark modelu lokalnego, natomiast dane testowe XML
pozostają równoważne na potrzeby wymiany i testów regresyjnych.

## Kandydaci polskiego korpusu korekt v3

`tests/fixtures/evaluation/polish_correction_corpus_v3.json` jest kanonicznym
zbiorem kandydatów schematu v3. Jego odpowiednik XML jest równoważną
reprezentacją wymiany. Jest fizycznie oddzielony od danych testowych E2E z samymi
regułami oraz od każdego przyszłego zasobu treningowego.

Korpus deklaruje cztery warstwy po 60 przypadków: fleksję, składnię,
interpunkcję i chronione trudne przypadki negatywne. Każda warstwa ma 20
przypadków deweloperskich i 40 przypadków holdout. Po ukończeniu przeglądu
właścicielskiego wszystkich 240 przypadków `holdout_state` najwyższego poziomu
ustawiono na `frozen` przed pierwszym przebiegiem bramki jakości. Oczekujący
kandydaci nie są wzorcowymi danymi ewaluacji, nie mogą trafić do benchmarku ani bramki
jakości i nie mogą być używani do treningu.
Przed tym przejściem każdy przypadek `pending-human-review` wymagał, aby korpus
pozostał w stanie `unfrozen-candidates`; ten stan jest nadal egzekwowany dla
przyszłych wersji korpusu poddawanych przeglądowi.

Każdy przypadek zapisuje proweniencję CC0-1.0, obiekt przeglądu, dokładne zakresy
encji nazw własnych, kanoniczne identyfikatory encji, wyprowadzony
znormalizowany szablon zdania, dokładne edycje Unicode oraz pozytywne oczekiwane
wyjście albo jedno nazwane chronione zjawisko. Szablon jest deterministycznie
odbudowywany z wejścia przez zastąpienie zakresów z kontrolowanego katalogu form
powierzchniowych encji znacznikiem `<entity>`, zastosowanie Unicode NFC,
ujednolicenia wielkości liter i normalizacji białej spacji oraz zastąpienie adresów URL i liczb
stałymi markerami. Każda wykrywalna forma powierzchniowa katalogu musi mieć
zakres. Warianty deklinacyjne jednej osoby mapują się na jeden kanoniczny
identyfikator; dowolne wyrazy pisane wielką literą, markery szablonu,
identyfikatory i pominięte zakresy są odrzucane.

Walidator odrzuca powielone wejście, wyciek encji lub znormalizowanego szablonu
między podziałami, powielone albo niemal identyczne rodziny szablonów w dowolnej
części, w tym krótkie szablony siostrzane rozdzielone jedną edycją tokenu,
niepoprawne przesunięcia, nakładanie się zakresów, błędy rekonstrukcji oraz rozbieżność
JSON/XML.

Izolacja treningu używa zamkniętego kontraktu rekordu zamiast skończonego
katalogu form powierzchniowych korpusu. Każdy rekord musi dostarczyć dokładne,
uporządkowane zakresy dla każdej deterministycznie wykrytej grupy tokenów
o kształcie nazwy. Wykrywanie rozpoznaje formy rozpoczynające się wielką literą
i zapisane samymi wielkimi literami oraz łączy sąsiadujące tokeny o kształcie
nazwy. Znane aliasy ewaluacyjne są wyprowadzane z każdej formy powierzchniowej
encji korpusu oraz z korekt wewnątrz tej formy; są rozpoznawane bez rozróżniania
wielkości liter w każdej pozycji zdania, w tym jako pojedynczy token początkowy.
Porównanie encji stosuje deterministyczną normalizację Unicode i konserwatywną
normalizację polskich końcówek przypadków, dzięki czemu wielkość liter, błędne
formy korpusowe i ich oczekiwane poprawione formy zachowują jedną tożsamość
izolacji. Szablony są odbudowywane z dostarczonych, zweryfikowanych zakresów, co
sprawia, że niewidziana nazwa w zastrzeżonej topologii zdania stanowi kolizję.
Użycie samego korpusu ewaluacyjnego jako danych treningowych pozostaje zabronione.

Pozostaje jedna deterministyczna niejednoznaczność: pojedynczy token
rozpoczynający zdanie wielką literą, który nie jest znanym aliasem korpusu, jest
traktowany jako zwykła wielka litera na początku zdania. Może zatem być nieznaną
jednowyrazową nazwą własną. Wywołujący muszą podać zakres, gdy znają ten fakt
semantyczny, lecz działający offline detektor kształtu nie może wywnioskować go
wyłącznie z wielkiej litery. Sąsiadujące tokeny pisane wielką literą oraz
jednoznaczne tokeny o kształcie nazwy w innych miejscach nadal są obowiązkowe.

Przegląd przez człowieka przebiega zgodnie z
[`evaluation-corpus-v3-review-checklist.md`](evaluation-corpus-v3-review-checklist.md).
Wyłącznie Paweł Cyroń może zmienić stan przypadku na `human-reviewed`. Przypadki
deweloperskie mogą po zatwierdzeniu stawać się indywidualnie dostępne dla
eksperymentów benchmarkowych. Wybór benchmarku nigdy nie ujawnia zamierzonego
holdoutu. Przypadki holdout pozostają dostępne wyłącznie przez jawną ścieżkę
bramki jakości po zatwierdzeniu wszystkich przypadków i zamrożeniu holdoutu.

### Kontrola wycieku i zmian

Przykłady promptów i rekordy do dostrajania nie mogą ponownie używać wejścia
ewaluacyjnego, kombinacji encji ani znormalizowanego szablonu. Przed przyjęciem
takiego zasobu uruchom walidator izolacji treningu względem rekordów zamkniętego
kontraktu. Rekord z brakującymi, dodatkowymi, nakładającymi się, nieuporządkowanymi
albo niezgodnymi z tekstem zakresami encji jest niepoprawny. Nie kopiuj
kandydatów z v3 do katalogu treningowego, nawet po przeglądzie.

Przed pierwszym przebiegiem holdoutu zatwierdź każdy przypadek, ponownie
wygeneruj XML, ustaw stan na `frozen`, zapisz skrót kanonicznego JSON-u i uruchom
wszystkie kontrole integralności. Po ocenieniu zamrożonego holdoutu korekty
wymagają nowego schematu albo nowej wersji korpusu. Ta kontrola zmian zapobiega
naprawom sterowanym benchmarkiem i utrzymuje odtwarzalność raportowanych dowodów.

## Walidacja

Uruchom szybkie kontrole integralności poleceniem:

```console
uv run --locked --extra dev pytest tests/test_evaluation_dataset.py -v
```

Integralność kandydatów korpusu v3 jest sprawdzana osobno poleceniem:

```console
uv run --locked --extra dev pytest tests/test_correction_corpus_v3.py -v
```

## Niezależny korpus bezpieczeństwa zdań v1

`tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json` i jego
odpowiednik XML są nowym korpusem issue #114
`polis_polish_correction_safety_corpus_v1`. Zawiera 240 nowych, autorskich,
syntetycznych polskich kandydatów CC0-1.0: po 60 dla fleksji, składni,
interpunkcji i chronionych trudnych przypadków negatywnych, z 20 przypadkami
deweloperskimi i 40 przypadkami holdout na warstwę.

Katalog encji, wejścia, znormalizowane szablony, kombinacje encji i rodziny
bliskich duplikatów są sprawdzane pod kątem niezależności od korpusu v3,
wszystkich rekordów do dostrajania, przykładów promptów i danych testowych E2E. Ten
korpus nie zastępuje korpusu v3 i nie realizuje pracy nad pokryciem większości
śledzonej w #85. Pliki, wyniki i skróty korpusu v3 pozostają bez zmian.

Zapisany stan to `frozen` po ukończeniu przez Pawła Cyronia przeglądu
właścicielskiego wszystkich 240 przypadków 2026-07-22. Wybór części deweloperskiej
udostępnia wyłącznie 80 przypadków deweloperskich; zwykły kod deweloperski nie może
wczytać wzorcowych danych holdoutu. Wybór bramki jakości jest jedyną ścieżką
udostępniającą 160 przypadków holdout. Użycie treningowe jest zawsze zabronione.

Przegląd właścicielski przebiega zgodnie z
[`evaluation-safety-corpus-v1-review-checklist.md`](evaluation-safety-corpus-v1-review-checklist.md).
Wyłącznie Paweł Cyroń może zapisać `human-reviewed`. Zamrożony skrót SHA-256
kanonicznego JSON-u to
`2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982`.
Osobny manifest `.approval.json` wiąże to przypisanie i zakres zatwierdzenia
`all-cases` ze skrótem niezamrożonego kandydata; generator nie może samodzielnie
utworzyć metadanych przeglądu właścicielskiego. Przed zapisaniem JSON-u lub XML-a
sprawdza korpus v3, dane do dostrajania, przykłady promptów i obie reprezentacje
E2E pod kątem wycieku.
Issue #114 nie uzyskało dostępu przez bramkę. Issue #115 zarezerwowało później
i oceniło 160-przypadkowy holdout dokładnie raz 2026-07-23. Holdout nie
zakwalifikował się i jest trwale zużyty; nie wolno go ponownie uruchamiać ani
używać do tuningu.

Uruchom kontrole integralności kandydatów i wycieku poleceniem:

```console
uv run --locked --extra dev pytest tests/test_safety_corpus.py -v
```

## Kandydaci niezależnego korpusu bezpieczeństwa zdań v2

Issue #119 dodaje korpus kandydacki
`polis_polish_correction_safety_corpus_v2` po zużyciu niezależnego holdoutu v1
z #114 przez poprawny, ale niekwalifikujący przebieg #115. V2 zawiera 240 nowych,
autorskich, syntetycznych polskich przypadków projektu na licencji CC0-1.0: po
60 dla fleksji, składni, interpunkcji i chronionych trudnych przypadków
negatywnych, z 20 przypadkami deweloperskimi i 40 przypadkami holdout na warstwę.

Korpus ma stan `frozen` po wyczerpującym przeglądzie wszystkich 240 przypadków przez
rolę `Polis architecture owner`, zgodnie z zaakceptowanym doprecyzowaniem
w issue #119. Rola jest zapisana bez wskazania osoby. SHA-256 kanonicznego JSON-u
kandydata
`c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53`
jest powiązany z SHA-256 zamrożonego kanonicznego JSON-u
`53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
Zamrożenie nie wytwarza wyniku jakości dla części deweloperskiej ani holdoutu. Nie
tuninguje analizatora i nie zmienia progów ani negatywnego werdyktu #115.

Katalog encji v2, wejścia, znormalizowane szablony, kombinacje encji i rodziny
bliskich duplikatów językowych są mechanicznie sprawdzane pod kątem niezależności
od korpusu v3, korpusu bezpieczeństwa v1, rekordów do dostrajania, przykładów
promptów i danych testowych E2E. Istniejące dane testowe v1, dane zatwierdzenia, markery
#115, raporty i skróty są przypięte bajt w bajt.

Przegląd właścicielski przebiega zgodnie z
[`evaluation-safety-corpus-v2-review-checklist.md`](evaluation-safety-corpus-v2-review-checklist.md).
Manifest zatwierdzenia zapisuje upoważnioną rolę `Polis architecture owner`,
zakres wszystkich przypadków, datę przeglądu, wersję listy kontrolnej i oba skróty.
Osobne kolejne issue może uruchomić jednorazową bramkę zainstalowanego pakietu
dla #76; to zadanie nie upoważnia do tej bramki ani jej nie wykonuje. Korpus v2
nie nakłada się na prace nad pokryciem większości korpusu v4 w #85 i #90.

Issue #146 wykonało swój pojedynczy dozwolony audyt na 80 przypadkach
deweloperskich z dwoma stabilnymi powtórzeniami. Decyzja zagregowana brzmiała: brak
kwalifikacji. SHA-256 raportu to
`7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141`.
Precyzja automatyczna i dokładność korekt wyniosły `1.00`, przy recallu
`0.3333333333333333`; kanał do przeglądu nie zaproponował żadnych edycji, dlatego
nie spełnił nietrywialnej bramki precyzji. Poprawność ustrukturyzowana wyniosła
`1.00`, a obie liczności chronionych przypadków negatywnych były zerowe. Nie ma
zamrożonej bramki, rzeczywisty marker jest nieobecny, a holdout nie został
zarezerwowany, zmaterializowany ani uruchomiony. Audyt części deweloperskiej nie zostanie
uruchomiony ponownie ani użyty do tuningu. #76 pozostaje otwarte, a Task 6 jest
zabroniony. Te opcjonalne badania nie kwalifikują modelu produkcyjnego ani
zachowania akapitowego.

Uruchom kontrole integralności zamrożonego korpusu, zachowanych dowodów
i izolacji poleceniem:

```console
uv run --locked --extra dev pytest tests/test_safety_corpus_v2.py -v
```

Walidator oparty na bibliotece standardowej jest również dostępny dla
wywołujących jako `polis.evaluation.validate_dataset(raw)` oraz
`polis.evaluation.load_dataset()`. Zgodnie z
[ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md)
pozostaje to przestrzeń nazw kompatybilności dla procesów ewaluacyjnych
repozytorium w bieżącej linii 0.x. Waliduje niezaufany kandydacki JSON przed
przyjęciem go jako zasobu projektu; nie jest głównym punktem wejścia analizy dla
biblioteki runtime'owej.
