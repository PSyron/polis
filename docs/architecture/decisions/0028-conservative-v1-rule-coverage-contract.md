# ADR-0028: Kontrakt pokrycia reguł konserwatywnego v1

- Status: Accepted
- Data: 2026-08-18
- Decydent: Paweł Cyroń
- Issue: #364
- Rodzic: #363

## Kontekst

Polis ma obecnie 59 deterministycznych tożsamości źródeł. Ta liczba mówi, ile
źródeł jest zarejestrowanych, ale nie mówi, ile zjawisk językowych jest
obsługiwanych ani czy każda kategoria ma wystarczające dowody. Publiczne v3 ma
nierówne mianowniki kategorii, więc wynik zbiorczy może ukryć kategorię
niezbadaną albo zdominowaną przez inną. Kontrakt pokrycia musi rozdzielić
istnienie źródła, jego obserwowalne zachowanie, zjawisko, dowód i roszczenie
o zdolności kategorii.

Ten ADR definiuje decyzję dla przyszłych audytów RJP, zbioru public-v4,
baseline'ów i kwalifikacji rodzin. Nie rejestruje reguły, nie tworzy przypadku
v4 i nie ustala liczbowych progów jakości v4.

Wykonywalne wartości kontraktu znajdują się w
[`docs/project/rule-coverage-contract-v1.json`](../../project/rule-coverage-contract-v1.json),
a repozytoryjny validator schematu w
[`scripts/rule_coverage_contract.py`](../../../scripts/rule_coverage_contract.py). Zmiana
znaczenia kontraktu wymaga nowego ADR-u; edycja zaakceptowanego ADR-u jest
zabroniona.

Źródła decyzji mają następującą kolejność pierwszeństwa: bieżące issue i
zaakceptowane doprecyzowania maintainera, zaakceptowane ADR-y, `PROMPT.md`,
`docs/project/ROADMAP.md`, `docs/rules.md`, a następnie publiczne artefakty
jakości v3 i izolowanego pomiaru wydajności. Artefakt niższego rzędu nie może
po cichu zmienić decyzji wyższego rzędu.

## Decyzja

### Jednostki pokrycia i ich relacje

Kontrakt używa następujących jednostek:

| Jednostka | Znaczenie | Czego nie dowodzi |
| --- | --- | --- |
| `source-identity` | Dokładny klucz `rule:*` z publicznego composition root. | Nie dowodzi szerokiego pokrycia języka. |
| `behavior-version` | Dokładna wersja obserwowalnego zachowania źródła. | Nie dziedziczy kwalifikacji po podobnym źródle. |
| `rule-family` | Ograniczona rodzina o wspólnej, deterministycznej granicy i operacji. | Nie scala tożsamości ani ich polityki. |
| `linguistic-phenomenon` | Obserwowalne zjawisko polskiej ortografii, interpunkcji, zgody, fleksji lub składni. | Nie jest etykietą wyprowadzoną wyłącznie z częstości korpusu. |
| `public-evaluation-case` | Publiczny, projektowy, licencjonowany przypadek z określonym rodzajem i cechami. | Nie jest prywatnym tekstem ani holdoutem. |
| `expected-finding` | Dokładna minimalna poprawka z kategorią, zakresem `[start, end)`, oryginałem, sugestią i uzasadnieniem. | Nie dopuszcza równoważnej poprawki bez jawnej decyzji normatywnej. |
| `positive-hard-negative-pair` | Para przypadków różniących się jedną kontrolowaną cechą: jeden wymaga poprawki, drugi pozostaje bez zmiany. | Nie może być samym zestawem atrakcyjnych pozytywów. |
| `category-capability-claim` | Ograniczone twierdzenie o jednej kategorii i profilu, oparte na wymaganych stratach. | Nie jest twierdzeniem o kompletności polszczyzny. |

Relacja jest skierowana: źródło ma jedną wersję zachowania; rodzina mapuje się
na dokładne źródła; zjawisko mapuje się na rodziny; przypadek może mieć
oczekiwane znaleziska; para wiąże dwa przypadki; roszczenie kategorii agreguje
wyłącznie przypadki z tej kategorii i profilu. Żaden poziom nie zastępuje
dowodu poziomu niższego.

### Profile runtime'u

Raport zawsze rozdziela co najmniej dwa profile:

1. `provider-absent` wykonuje źródła niezależne od dostawcy. Brak opcjonalnej
   morfologii nie jest błędem produktu; źródła zależne od morfologii zwracają
   abstencję bez sugestii.
2. `qualified-morphology` wykonuje źródła niezależne oraz zależne tylko przy
   dokładnej tożsamości `morfeusz2` 1.99.15, słownika
   `pl.sgjp.sgjp-2026.06.01` oraz noty o SHA-256
   `84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`.
   Drift dowolnego elementu unieważnia wynik zależnej rodziny i prowadzi do
   abstencji.

Brak dostawcy, brak obsługiwanej konstrukcji, niepełna analiza, wieloznaczność
i drift nie są zastępowane domysłem, innym providerem ani obniżeniem progu.
Metryki wspólnego podzbioru można porównywać między profilami; metryki rodziny
zależnej są porównywalne tylko wewnątrz profilu z tym samym providerem,
słownikiem, środowiskiem i protokołem. Opcjonalna morfologia nigdy nie staje
się niejawną zależnością profilu domyślnego.

### Metryki i mianowniki

Kontrakt wymaga osobnego raportu dla profilu, kategorii i każdej stosowalnej
straty. Obowiązują następujące definicje:

- `TP` to dokładna zgodność kategorii, `[start, end)`, oryginału i sugestii;
- `FP` to predykcja bez odpowiadającego jej oczekiwanego znaleziska;
- `FN` to oczekiwane znalezisko bez dokładnej predykcji;
- precision to `TP / (TP + FP)`;
- recall to `TP / (TP + FN)`;
- F1 to `2*TP / (2*TP + FP + FN)`;
- exact-span accuracy to zgodne zakresy półotwarte podzielone przez liczbę
  oczekiwanych znalezisk;
- exact-suggestion accuracy to zgodne sugestie podzielone przez liczbę
  zgodnych zakresów;
- correct-sentence false-alarm rate to liczba poprawnych przypadków z dowolnym
  alarmem podzielona przez liczbę poprawnych przypadków.

Zero w mianowniku oznacza `null` i bramkę niedostępną, a nie zero jakości.
Brak pola, nieznana tożsamość albo nieporównywalne środowisko oznacza błąd
walidacji, nie pass. `conflict` i `abstain` nie wchodzą do zwykłego mianownika
TP/FP/FN; mają osobne wymagania abstencji. Predykcja w przypadku konfliktu,
abstencji lub nieobsługi jest naruszeniem abstencji. Przypadek `ambiguous`
może zostać dodany w kolejnej wersji schematu, ale nie może otrzymać arbitralnej
poprawki w wersji 1.

Metryki kategorii i strata są liczone po ograniczeniu tego samego algorytmu do
odpowiedniego podzbioru. Wynik zbiorczy jest informacją pomocniczą: nie może
wyłączyć bramki kategorii ani naprawić brakującego mianownika.

### Bramki i progi

Regresja precision albo correct-sentence false-alarm rate jest fail-closed.
Agregat recall nie może znieść fałszywego alarmu, niespełnionej kategorii,
braku straty ani niepełnego dowodu. Każdy przyszły próg liczbowy musi zapisać:

- zmierzony, przejrzany baseline i jego pełną tożsamość;
- mianownik, profil i zakres obowiązywania;
- uzasadnienie oraz decyzję maintenera;
- procedurę zmiany i dowód regresji.

Ten ADR nie wybiera progów v4. Protocol-v2 pozostaje wymaganym izolowanym
pomiarem runtime'u tam, gdzie profil jest stosowalny, lecz pass wydajności nie
może przykryć niepowodzenia jakości, kategorii lub parity.

### Minimalne próbkowanie public-v4

Każda z pięciu kategorii ma własny mianownik i musi mieć co najmniej:

- 8 oczekiwanych pozytywnych znalezisk;
- 16 poprawnych hard negatives;
- 3 różne zjawiska lub rodziny;
- 4 kontrolowane pary positive/hard-negative.

W każdej kategorii i w każdej stosowalnej stracie musi być co najmniej jeden
pozytyw i jeden hard negative. Wymagane straty to:

1. `simple-local` — najmniejsza lokalna konstrukcja;
2. `sentence-internal` — konstrukcja wśród otoczenia jednego zdania;
3. `multi-sentence` — sąsiednie zdania i mapowanie offsetów do dokumentu;
4. `repeated-occurrence` — co najmniej dwa niezależne wystąpienia;
5. `unicode-and-case` — polski Unicode, casing lub znaki łączące;
6. `quotation-or-literal` — cytat, literal, wzmianka lub kodopodobny tekst;
7. `conflict-or-abstention` — konflikt, wieloznaczność, brak providera lub
   nieobsługiwane wejście.

Każda para opisuje kontrolowaną różnicę, oba przypadki mają proweniencję,
a pozytyw ma dokładne zakresy i sugestie. Dla rodziny provider-dependent
potrzebne są co najmniej dwa przypadki z providerem nieobecnym i dwa z dokładnie
zakwalifikowanym providerem. Jeżeli strata lub rozróżnienie providera nie ma
zastosowania, raport musi podać powód; pominięcie bez powodu jest błędem.

Minimalne liczby są warunkiem reprezentacji, nie gwarancją jakości. Zwiększenie
próby lub wybór progu wymaga osobnego baseline'u. Ten kontrakt nie authoruje
przeniesienia przypadków z chronionych zbiorów ani ponownego uruchomienia
zużytych dowodów.

Poza zakresem pozostają rejestracja lub uogólnianie runtime'u, kwalifikowanie
nowych rodzin, zmiana eligibility correction policy, automatyczna promocja,
opcjonalne badania i implementacja research-only, release/packaging, modele,
sieć, Java, szeroki LanguageTool, styl, semantyka oraz prywatne i chronione
dane.

### Ambiguity, overlap i abstencja

- Nakładające się oczekiwane znaleziska są jawnym przypadkiem konfliktu.
- Wiele możliwych poprawek wymaga jednej normatywnej, deterministycznej decyzji;
  bez niej przypadek pozostaje niejednoznaczny i wymaga abstencji.
- Konflikt rodzin nie jest rozstrzygany aggregate score ani kolejnością źródeł.
- Powtórzenia ocenia się niezależnie, z offsetami względem oryginalnego tekstu.
- Ten sam span różnych źródeł zachowuje obie tożsamości; nie wolno cicho
  deduplikować dowodu.
- Wieloznaczność morfologiczna, brak cech, niepełność i drift providera kończą
  się abstencją zależnej rodziny.
- Tekst poprawny, choć podobny do szablonu, pozostaje hard negative, dopóki
  lokalna granica i normatywne uzasadnienie nie są jednoznaczne.
- Wejście uszkodzone lub poza zakresem nie otrzymuje sugestii.

### Review-only i korekta automatyczna

Nowa zakwalifikowana rodzina zaczyna jako `review-only`. To kontrakt widocznej
sugestii, nie prawo do automatycznego zastosowania. Automatyczna korekta jest
oddzielną decyzją i wymaga dokładnego klucza:

`(source, category, operation, behavior_version, source_policy_version)`.

Wymagane są również bezpieczeństwo konfliktów, dowód idempotencji i osobna
akceptacja. Zmiana któregokolwiek elementu klucza odbiera uprawnienie do czasu
nowej kwalifikacji. Brak wpisu polityki nie może być interpretowany jako
automatyzacja ani jako ciche dziedziczenie.

### Governance źródeł i artefaktów

Źródłem ordered snapshotu jest
`Analyzer(AnalyzerConfig()).source_identity_snapshot`, nigdy ręcznie wpisany
count ani `set`. Snapshot zawiera dokładnie `source`, `operation` i
`behavior_version`, zachowuje kolejność rejestracji i ma SHA-256 z kanonicznego
UTF-8 JSON. `docs/rules.md`, wersje zachowania, polityka korekty i publiczne
artefakty jakości muszą wskazywać ten sam source/baseline. Brak, nadmiar,
duplikat, zmiana kolejności lub drift wersji kończy walidację.

Stan `automatic` pochodzi z pełnego klucza polityki i wersji polityki; nie wolno
go wywnioskować z samego source, kategorii, confidence albo podobieństwa do
innej reguły. Publiczny raport ma wiązać pełny SHA, digest ordered snapshotu,
dataset, profil, identity providera oraz wersje zachowania, jeśli są stosowalne.

## Konsekwencje

Pozytywne:

- raporty pokazują różnicę między istniejącym źródłem a dowiedzionym zjawiskiem;
- pięć kategorii ma niezależną reprezentację i bramkę;
- brak providera i ambiguity są mierzalnymi abstencjami, a nie ukrytymi FP;
- przyszłe issue mogą korzystać z jednego schematu bez lokalnej reinterpretacji;
- parity i exact offsets są sprawdzalne z publicznych artefaktów.

Koszty:

- v4 musi zebrać więcej przypadków niż obecne pięć pozytywów interpunkcyjnych;
- każdy nowy family/candidate wymaga pełnego hard-negative i boundary evidence;
- raportowanie jest większe, bo profile, kategorie i straty nie mogą być scalone;
- zmiana źródła, wersji zachowania albo polityki wymaga odrębnej kwalifikacji.

## Odrzucone alternatywy

- **Uznanie 59 źródeł za 59 zjawisk.** Odrzucono, bo źródła mogą dzielić
  zjawisko, a jedno zjawisko może mieć kilka granic.
- **Jeden aggregate precision/recall dla v1.** Odrzucono z powodu nierównych
  mianowników i ryzyka ukrycia słabej kategorii.
- **Wybór progów v4 przed baseline'em.** Odrzucono jako nieaudytowalne i
  sprzeczne z `PROMPT.md` oraz roadmapą.
- **Promowanie nowej rodziny do automatic po samym wyniku jakości.** Odrzucono,
  bo polityka wymaga dokładnej tożsamości i osobnej decyzji.
- **Wykorzystanie korpusu, LanguageTool lub słownika jako normy.** Odrzucono;
  mogą dostarczać kandydatów i przykładów, ale normę dla ortografii i
  interpunkcji ustanawia RJP.

## Zakres i niezmienniki

ADR nie zmienia runtime'u, API, kohorty, polityki korekty, datasetu, progów,
providerów, zależności, release/packaging ani żadnego chronionego dowodu.
Aktualne 59 źródeł jest wyłącznie planning baseline'em do parity. Każda późniejsza
zmiana runtime'u musi podać nowy full SHA i nowy digest w swoim artefakcie;
nie wolno aktualizować tego ADR-u w miejscu.
