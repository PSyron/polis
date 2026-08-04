# Projekt konserwatywnego zakresu v1 i sprzątania repozytorium

**Issue:** #185
**Status:** zatwierdzony kierunek, oczekuje na przegląd zapisanej specyfikacji
**Data:** 2026-08-04

## Cel

Polis v1 jest biblioteką do konserwatywnej, lokalnej korekty formy polskiego
tekstu. Wydanie ma skupiać się na błędach, dla których minimalna poprawka
wynika jednoznacznie z lokalnej postaci tekstu. Biblioteka nie interpretuje
intencji autora i nie modyfikuje znaczenia wypowiedzi.

Repozytorium zostanie odchudzone tak, aby opcjonalne badania, modele, szerokie
integracje LanguageTool i przyszłe abstrakcje architektoniczne nie przesłaniały
wspieranego produktu ani nie blokowały v1. Pełny stan sprzed sprzątania zostanie
najpierw zachowany na osobnej gałęzi w tym samym repozytorium.

## Nadrzędna zasada zachowania

Polis może zaproponować zmianę tylko wtedy, gdy spełnione są wszystkie warunki:

1. problem należy do jawnie wspieranej kategorii v1;
2. błąd i minimalna poprawka wynikają z lokalnej formy tekstu;
3. poprawka nie wymaga odgadnięcia czasu, faktów, intencji, stylu ani sensu;
4. reguła zachowuje oryginalny zakres `[start, end)` i nie zmienia tekstu poza
   wskazanym fragmentem;
5. źródło i wersja zachowania mają uprawnienie odpowiednie do rodzaju wyniku;
6. niepewność, brak danych albo konflikt prowadzą do braku sugestii.

Zasada bezpieczeństwa brzmi: **zmień formę, nigdy znaczenie; w razie
wątpliwości nie sugeruj zmiany**.

Przykład:

> Gdy wrócisz, zadzwoń do mnie wczoraj.

Zdanie jest znaczeniowo lub czasowo podejrzane, ale poprawka wymagałaby
odgadnięcia intencji autora. Polis v1 pozostawia je bez zmian. Ten przypadek
powinien być negatywnym testem bezpieczeństwa, a nie materiałem do uczenia lub
oceny poprawiania zgodności czasów.

## Zakres funkcjonalny v1

### Wspierane kategorie

- fleksja;
- rekcja;
- zgoda rodzaju, liczby, osoby i przypadka;
- literówki, pisownia i typowe błędy ortograficzne;
- podstawowa ortotypografia;
- bezpieczne, lokalne problemy interpunkcyjne;
- nieliczne lokalne problemy składniowe, jeżeli wykrycie i minimalna poprawka
  nie wymagają interpretacji znaczenia całego zdania.

Nie każda reguła należąca nominalnie do jednej z tych kategorii automatycznie
wchodzi do v1. Każda reguła musi osobno spełniać zasadę konserwatywnej korekty i
mieć regresyjne przypadki pozytywne oraz negatywne.

### Poza zakresem v1

- zgodność czasów i aspektu;
- logiczna, faktyczna albo semantyczna poprawność wypowiedzi;
- wnioskowanie o intencji autora;
- swobodne przepisywanie zdań;
- korekta stylu, tonu i dyskursu;
- analiza wymagająca szerokiego kontekstu dokumentu;
- lokalny LLM, ranker modelowy i fine-tuning jako część wspieranego produktu;
- szerokie uruchamianie LanguageTool lub procesu Java jako część ścieżki v1;
- benchmarki większościowego pokrycia zdań jako bramka wydania;
- przyszłe abstrakcje katalogu i konfiguracji bez bieżącego konsumenta v1.

Badania nad tymi obszarami mogą wrócić w v2. Nie stanowią zależności produktu,
pakowania, CI ani terminu wydania v1.

Pochodzenie pomysłu na regułę nie rozstrzyga o jej przynależności. Zachowanie
odkryte podczas badań LanguageTool może wejść do v1 tylko jako mała,
deterministyczna reguła produktu, jeżeli nie wymaga procesu Java, szerokiego
silnika ani interpretacji znaczenia i przechodzi pełną bazę regresyjną v1.

## Model archiwizacji

### Gałąź archiwalna

Przed pierwszym usunięciem z `main` należy utworzyć z aktualnego, pełnego
`origin/main` gałąź:

`feature/v2-research-archive`

Gałąź pozostaje w tym samym repozytorium i zachowuje pełny kod badań, vendor,
raporty, manifesty oraz implementacje opcjonalne istniejące przed sprzątaniem.
Nie jest gałęzią wydawniczą i nie podlega aktywnemu CI v1.

Utworzenie gałęzi musi zostać zweryfikowane przez:

- zapisanie bazowego SHA commita;
- wypchnięcie gałęzi do zdalnego repozytorium;
- sprawdzenie zdalnego refa i zgodności SHA;
- sprawdzenie obecności chronionych katalogów oraz zamrożonych artefaktów;
- sprawdzenie obecności i niezmienionych hashy trzech zamrożonych checklist
  przeglądu: `docs/evaluation-corpus-v3-review-checklist.md`,
  `docs/evaluation-safety-corpus-v1-review-checklist.md` i
  `docs/evaluation-safety-corpus-v2-review-checklist.md`;
- dodanie do żywej dokumentacji odsyłacza do gałęzi i zasad jej użycia.

Usuwanie z `main` nie może rozpocząć się przed wykonaniem tych kontroli.

### Chronione zapisy historyczne

Zaakceptowanych ADR-ów, opublikowanych release notes, zużytych holdoutów,
zamrożonych raportów, manifestów i dowodów wydania nie wolno regenerować,
dostrajać ani przepisywać. Domyślnie pozostają na `main` w istniejącej postaci.

Pliki `docs/evaluation-corpus-v3-review-checklist.md`,
`docs/evaluation-safety-corpus-v1-review-checklist.md` i
`docs/evaluation-safety-corpus-v2-review-checklist.md` są chronionym,
zamrożonym dowodem ręcznego przeglądu. Pozostają na `main` niezmienione,
nie są elementami usuwania dokumentacji i muszą być wymienione po dokładnej
ścieżce w inwentaryzacji chronionych dowodów wraz z kontrolą ich obecności oraz
hashy.

Przeniesienie chronionego artefaktu wyłącznie na gałąź archiwalną wymaga
osobnego ADR-u określającego trwałość odwołania, manifest zawartości i sposób
audytu. Zwykłe issue porządkowe nie może podjąć tej decyzji.

Historyczne plany w `docs/superpowers/` pozostają zapisem wykonanej pracy. Nie
aktualizuje się ich tak, aby udawały obecny zakres produktu.

## Dyspozycja otwartych issue

Po zaakceptowaniu specyfikacji i utworzeniu gałęzi archiwalnej należy zamknąć
poniższe issue jako niewchodzące do v1:

- opcjonalne badania i modele: #76, #85, #86, #87, #88, #89 i #90;
- benchmarki powstałe po zmianie kierunku: #180 i #183;
- przyszła architektura M6: #96, #97, #98, #99 i #100;
- niewymagana migracja katalogu: #151, #152, #153, #154 i #155.

Każdy komentarz zamykający musi:

- wskazać decyzję #185;
- wyjaśnić, że issue nie jest ukończone, lecz usunięte z zakresu v1;
- podać gałąź archiwalną;
- nie zmieniać historycznych wyników ani nie sugerować zaliczenia bramki;
- wskazać jeden tracker v2 jako miejsce ewentualnego powrotu.

Powstanie dokładnie jeden nieblokujący tracker v2. Ma zawierać odnośniki do
zamkniętych issue, ale nie odtwarzać ich grafu zależności jako aktywnego
backlogu. Ponowne otwarcie konkretnego tematu wymaga nowego uzasadnienia,
zakresu i kryteriów odpowiednich dla v2.

## Sekwencja sprzątania `main`

Sprzątanie nie będzie jednym dużym usunięciem. Po #185 powstaną atomowe issue w
następującej kolejności:

1. **Archiwum i inwentaryzacja.** Utworzenie oraz weryfikacja gałęzi
   `feature/v2-research-archive`; klasyfikacja każdego elementu jako produkt,
   chroniony dowód albo materiał v2.
2. **Decyzja architektoniczna i żywa specyfikacja.** Nowy ADR zastępujący
   sprzeczne założenia produktowe bez edycji zaakceptowanych ADR-ów;
   aktualizacja `PROMPT.md`, roadmapy i dokumentów zakresu.
3. **Powierzchnia badawcza.** Usunięcie z aktywnego `main` niechronionych
   runnerów, vendorowych źródeł, dokumentów operacyjnych i zadań CI służących
   wyłącznie modelom, pełnemu LanguageTool albo nieważnym benchmarkom.
4. **Powierzchnia runtime.** Usunięcie z domyślnego analizatora i publicznej
   konfiguracji niewspieranych ścieżek LLM, szerokiego LanguageTool,
   kontekstowej korekty wymagającej interpretacji oraz hybrydowego rankingu.
5. **Nieużywane abstrakcje.** Usunięcie kontraktów katalogu dodanych przez #150,
   jeżeli po inwentaryzacji nadal nie mają konsumenta wymaganego przez v1.
6. **Ewaluacja i kompatybilność.** Osobna decyzja dotycząca
   `polis.evaluation` zgodna z ADR-0019. Namespace nie znika przypadkowo w
   porządkowym PR-ze; przed 1.0 trzeba jawnie zdecydować o jego zachowaniu,
   wyłączeniu z dystrybucji albo usunięciu.
7. **Baza jakości v1.** Zastąpienie testów usuniętych mechanizmów testami
   kontraktu v1, przypadkami abstencji i kontrolami zawartości dystrybucji.
8. **Końcowa zgodność dokumentacji i wydania.** Pełne wyszukanie osieroconych
   odwołań, weryfikacja paczek i potwierdzenie, że aktywna dokumentacja opisuje
   wyłącznie faktycznie wspierane zachowanie.

Każdy krok ma osobne issue, jeden skupiony commit i osobny PR. Usunięcia nie
mogą być łączone z implementacją nowych reguł językowych.

## Macierz obowiązkowej synchronizacji

Usunięcie albo ograniczenie mechanizmu jest ukończone dopiero po sprawdzeniu
wszystkich odpowiadających mu powierzchni:

| Powierzchnia | Wymagana czynność |
| --- | --- |
| Kod runtime | Usunąć implementację, importy, adaptery i ścieżki wykonania. |
| Rejestr reguł | Usunąć źródło, metadane i możliwość przypadkowej rejestracji. |
| Konfiguracja | Usunąć opcje albo odrzucać je jawnym, stabilnym błędem migracyjnym. |
| Publiczne API | Usunąć eksport dopiero zgodnie z decyzją kompatybilności. |
| Pakowanie | Wykluczyć moduły, vendor, dane i dokumenty niezatwierdzone dla v1. |
| CI | Usunąć nieaktualne zadania i zachować kontrolę offline oraz jakości v1. |
| Dokumentacja | Zaktualizować README, szybki start, API, reguły, ograniczenia i roadmapę. |
| Testy | Usunąć testy implementacyjne starej funkcji, lecz zastąpić je testami granicy v1. |
| Przykłady i fixture'y | Usunąć obietnice starego zachowania i zachować tylko potrzebne regresje. |

Samo skasowanie testów nie jest wystarczające. Każde usunięcie zachowania musi
pozostawić test dowodzący nowej granicy produktu.

## Reguły i baza testów v1

### Klasyfikacja reguł

Każde aktywne źródło i każda reguła zostaną sklasyfikowane jako:

- `v1-supported` — spełnia zakres oraz zasadę konserwatywnej korekty;
- `review-only` — może wskazać lokalny problem, ale nie ma prawa do
  automatycznej poprawki;
- `v2-archived` — wymaga znaczenia, szerokiego kontekstu, modelu, Javy albo
  nie ma wystarczającego uzasadnienia;
- `historical-evidence` — pozostaje wyłącznie jako niezmienny dowód.

Metadane katalogowe nie mogą same przyznać prawa do automatycznej korekty.
Nieznane źródło, wersja lub klasyfikacja prowadzi do `review-only` albo braku
wyniku, zgodnie z istniejącą polityką fail-closed.

### Minimalna baza regresyjna

Dla każdej wspieranej reguły baza testów musi zawierać:

- co najmniej jeden rzeczywisty przypadek błędny;
- dokładną minimalną poprawkę;
- poprawny zakres `[start, end)` względem oryginalnego tekstu;
- co najmniej jeden bliski przypadek poprawny;
- przypadek dowodzący abstencji, jeśli podobna konstrukcja może wymagać
  interpretacji sensu;
- test interakcji z konfliktem i deterministycznym zastosowaniem poprawki,
  jeśli reguła może nakładać się z inną.

Przypadki zgodności czasów mogą występować wyłącznie jako testy braku sugestii.
Nie wolno używać mechanicznie wygenerowanych zdań jako dowodu zerowej liczby
fałszywych alarmów bez ręcznego przeglądu ich poprawności.

### Kontrole po sprzątaniu

Po każdym issue należy uruchomić testy właściwe dla zmienianej powierzchni oraz:

- `ruff check .`;
- `ruff format --check .`;
- `mypy .`;
- odpowiedni zestaw `pytest`;
- test budowy wheel i sdist, jeśli zmieniło się pakowanie;
- test instalacji offline, jeśli zmienił się runtime lub zależności;
- wyszukiwanie osieroconych nazw modułów, flag, źródeł i dokumentów.

Końcowy przegląd ma porównać deklarowany zakres w dokumentacji z faktycznie
zarejestrowanymi regułami, publiczną konfiguracją, zawartością paczek i bazą
testów.

## Obsługa kompatybilności i błędów

Usunięta opcja konfiguracyjna nie może zostać po cichu zignorowana. Parser ma
zwrócić jasny błąd wskazujący, że funkcja nie należy do wspieranej konfiguracji
v1 i gdzie znaleźć stan archiwalny lub instrukcję migracji.

Przed usunięciem opcjonalnej powierzchni runtime nowy ADR musi osobno
rozstrzygnąć kompatybilność i migrację każdego publicznego pola konstruktora
`AnalyzerConfig`: `use_local_heuristic_backend`, `language_tool_url`,
`language_tool_timeout_seconds`, `contextual_inflection_stdio_path`,
`contextual_inflection_timeout_seconds`, `vendored_language_tool_stdio_path`
i `vendored_language_tool_timeout_seconds`. Musi też rozstrzygnąć zachowanie
`from_toml` i `from_config` oraz każdej odpowiadającej im historycznej sekcji
TOML: `backend`, `language_tool`, `contextual_inflection` i
`vendored_language_tool`. Jeżeli sekcja zostaje usunięta, jej obecność musi
zawsze zwrócić stabilny `ConfigurationError` z nazwą sekcji i frazą
`is not supported in Polis v1`, zamiast być ignorowana albo interpretowana jako
domyślna konfiguracja.

Publiczne eksporty objęte dotychczasową gwarancją kompatybilności wymagają
osobnej decyzji wersjonowania. Kod wewnętrzny i nieudokumentowane ścieżki mogą
zostać usunięte wcześniej tylko wtedy, gdy testy dystrybucji potwierdzą brak
wspieranego konsumenta.

Nieobecność modelu, Javy, sieci albo materiałów badawczych nie jest błędem
instalacji ani działania v1.

## Praca równoległa

Po utworzeniu i zweryfikowaniu gałęzi archiwalnej dwa niezależne tory mogą być
prowadzone równolegle w osobnych worktree:

- tor A: zamknięcie backlogu i uporządkowanie metadanych GitHub;
- tor B: inwentaryzacja niechronionej powierzchni badawczej oraz vendorowej.

Po przyjęciu nowego ADR-u można równolegle realizować:

- usunięcie powierzchni badawczej i jej CI;
- audyt reguł oraz przygotowanie nowej bazy testów v1.

Usuwanie runtime, aktualizacja `README.md`, `PROMPT.md`, roadmapy,
`pyproject.toml` i testów pakowania są punktami integracyjnymi. Mają jednego
właściciela i nie mogą być jednocześnie edytowane przez dwie instancje.

## Warunki zakończenia całego sprzątania

Sprzątanie jest zakończone, gdy:

- gałąź archiwalna istnieje zdalnie i przeszła kontrolę kompletności;
- zbędne issue są zamknięte z prawdziwym powodem, bez udawania realizacji;
- istnieje tylko jeden nieblokujący tracker v2;
- domyślny runtime nie uruchamia modelu, Javy, sieci ani badań;
- aktywne reguły mieszczą się w zatwierdzonym zakresie v1;
- aktywna dokumentacja nie obiecuje zachowań usuniętych lub odłożonych;
- baza testów dowodzi zarówno wspieranych korekt, jak i abstencji;
- wheel i sdist zawierają wyłącznie jawnie zatwierdzone składniki;
- pełny zestaw jakości przechodzi;
- chronione dowody historyczne pozostają niezmienione i audytowalne.

## Ryzyka i zabezpieczenia

- **Sprzątanie opóźnia v1.** Ograniczenie: małe issue, najpierw powierzchnie o
  największym wpływie na produkt i paczkę, bez nowych funkcji.
- **Przypadkowa utrata dowodów.** Ograniczenie: zdalna gałąź archiwalna,
  zapisany SHA, inwentaryzacja i zakaz usuwania chronionych danych bez ADR-u.
- **Ciche zerwanie kompatybilności.** Ograniczenie: osobne decyzje dla
  publicznych namespace'ów i jawne błędy migracyjne.
- **Dokumentacja odbiega od kodu.** Ograniczenie: macierz synchronizacji,
  wyszukiwanie osieroconych nazw i końcowe porównanie dokumentacja–runtime–testy.
- **Testy znikają razem z funkcją.** Ograniczenie: obowiązkowe zastąpienie ich
  testami granicy v1 i przypadkami abstencji.
