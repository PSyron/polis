# Polis — żywa specyfikacja projektu

## Instrukcja dla agenta

Ten dokument jest źródłem prawdy dla projektu **Polis**. Traktuj go jako żywą specyfikację: aktualizuj stan realizacji i doprecyzowuj decyzje architektoniczne, ale nie usuwaj niezrealizowanych wymagań. Nie uznawaj punktu za wykonany bez kodu, testów i weryfikacji kryteriów akceptacji.

Najpierw poznaj stan repozytorium, przeczytaj aktualną roadmapę w
`docs/project/ROADMAP.md` i sprawdź wykonywalne kryteria bieżącego GitHub issue.
Planuj oraz implementuj po jednym małym, atomowym issue. Nie próbuj zbudować
całego systemu w jednym kroku.

Aktywnie utrzymywana, autorska dokumentacja projektu powstaje po polsku. Kod,
identyfikatory, importy, schematy, flagi CLI, klucze konfiguracji, literały
protokołów oraz metadane GitHub pozostają po angielsku. Historyczne plany,
zamrożone dowody, raporty oraz materiały upstream zachowują oryginalny język
zgodnie z `docs/project/DOCUMENTATION-ROADMAP.md`.

## Wizja

Polis ma być otwartoźródłową biblioteką programistyczną do analizy i minimalnej korekty tekstu w języku polskim. Biblioteka przyjmuje zwykły tekst i zwraca ustrukturyzowane wyniki analizy oraz opcjonalnie tekst po zaakceptowanych poprawkach.

System ma działać w pełni offline. Polis jest kompletnym produktem bez lokalnego
modelu językowego. Polis v1 nie wymaga także procesu Java ani szerokiego silnika
LanguageTool. Te mechanizmy nie są wspieranymi rozszerzeniami runtime'u v1.
Priorytetami są:

- wysoka jakość oceny polskiej fleksji, składni i zgodności gramatycznej;
- prywatność — tekst nie może opuszczać urządzenia użytkownika;
- przewidywalny, dobrze udokumentowany interfejs;
- minimalne i wyjaśnione sugestie zamiast swobodnego przepisywania tekstu;
- małe, jawne moduły deterministycznego runtime'u;
- szybkość odpowiednia do przetwarzania większej liczby fragmentów tekstu.

## Zakres pierwszej wersji

Biblioteka powinna:

1. Przyjmować tekst jako `str` przez publiczne API Pythona.
2. Segmentować tekst na akapity i zdania z zachowaniem przesunięć znakowych względem wejścia.
3. Uruchamiać niezależne analizatory deterministyczne bez modelu, procesu Java
   ani sieci.
4. Wykrywać co najmniej:
   - podejrzaną odmianę wyrazów;
   - błędy zgody rodzaju, liczby, osoby i przypadka;
   - wybrane problemy składniowe;
   - literówki i typowe błędy ortograficzne;
   - wybrane problemy interpunkcyjne.
5. Zwracać każde znalezisko jako ustrukturyzowaną sugestię zawierającą fragment, pozycję, kategorię, opis, minimalną poprawkę, źródło oraz poziom pewności.
6. Umożliwiać filtrowanie analiz według kategorii i progu pewności.
7. Generować poprawiony tekst wyłącznie przez deterministyczne zastosowanie jawnie wybranych, niekolidujących sugestii.
8. Działać bez dostępu do internetu po zainstalowaniu domyślnych zależności.

Wspierana ścieżka wydania runtime'u wymaga wyłącznie domyślnych zależności i
nie wymaga modelu lokalnego, serwera modeli, procesu Java, sieci, korpusu
badawczego ani zużytego holdoutu.

Każda poprawka v1 wynika jednoznacznie z lokalnej formy tekstu, zachowuje
oryginalny zakres `[start, end)` i nie zmienia znaczenia. Zgodność czasów i
aspektu, fakty, intencja, ton, styl oraz sens wypowiedzi nie są przedmiotem
korekty. Niepewność lub potrzeba interpretacji oznacza, że Polis w razie
wątpliwości nie sugeruje zmiany.

## Poza zakresem

Pierwsza wersja świadomie nie obejmuje:

- odczytu, zapisu ani zachowywania struktury plików DOCX;
- interfejsu graficznego;
- usługi chmurowej i wysyłania tekstu do zewnętrznych API;
- autonomicznego przepisywania całych dokumentów;
- korekty zmieniającej znaczenie, zgodności czasów i aspektu oraz wnioskowania
  semantycznego o intencji autora;
- korekty stylu, tonu i dyskursu;
- lokalnego LLM, modelowego rankera i fine-tuningu jako części wspieranego
  runtime'u;
- pełnego LanguageTool, procesu Java i kontekstowej ścieżki semantycznej;
- rozbudowy katalogu M6 bez bieżącego konsumenta v1;
- tłumaczenia;
- rozpoznawania nazw własnych jako głównego celu produktu;
- trenowania modelu od zera;
- automatycznego fine-tuningu bez przygotowanego i ocenionego zbioru danych.

Integracja z DOCX ma powstać w innym projekcie jako adapter korzystający z publicznego API Polis.

## Proponowane publiczne API

Poniższy interfejs wyznacza kierunek, ale jego ostateczną postać należy zatwierdzić w osobnym issue projektowym:

```python
from polis import Analyzer, AnalysisOptions

analyzer = Analyzer.from_config("polis.toml")
result = analyzer.analyze(
    "Te zdanie zawiera błąd.",
    options=AnalysisOptions(categories={"agreement", "spelling"}),
)

for issue in result.issues:
    print(issue.message, issue.suggestion, issue.confidence)

corrected = result.apply(issue_ids=[result.issues[0].id])
```

Publiczne modele danych powinny być typowane, stabilne i serializowalne do JSON. Minimalny model znaleziska powinien obejmować:

```json
{
  "id": "stabilny-identyfikator",
  "category": "agreement",
  "severity": "error",
  "message": "Niezgodność rodzaju zaimka i rzeczownika.",
  "explanation": "Forma „to” nie zgadza się z rzeczownikiem „zdanie”.",
  "original": "Te zdanie",
  "suggestion": "To zdanie",
  "start": 0,
  "end": 10,
  "confidence": 0.98,
  "source": "rule:agreement"
}
```

Przesunięcia `start` i `end` odnoszą się zawsze do oryginalnego tekstu i używają konwencji półotwartego przedziału `[start, end)`.

## Architektura

Zaprojektuj system jako zestaw małych modułów o jasno określonych odpowiedzialnościach:

- `core` — publiczne modele, konfiguracja, protokoły i orkiestracja;
- `segmentation` — segmentacja oraz mapowanie przesunięć znakowych;
- `rules` — deterministyczne analizatory i rejestr reguł;
- `llm` — historyczna powierzchnia badań, która nie należy do wspieranego
  runtime'u v1 i może pozostać wyłącznie w archiwum v2;
- `analysis` — scalanie, normalizacja, deduplikacja i priorytetyzacja znalezisk;
- `correction` — wykrywanie kolizji i bezpieczne stosowanie wybranych poprawek;
- `evaluation` — zestawy danych, metryki oraz regresje jakościowe;
- `cli` — opcjonalny, cienki interfejs do ręcznego testowania biblioteki.

Rdzeń nie zależy od serwera modeli ani procesu Java. Przywrócenie adaptera
modelu, pełnego LanguageTool albo innej ścieżki v2 wymaga nowego issue, nowego
ADR-u i kwalifikacji dokładnej konfiguracji; nie może zostać dodane jako
niejawna zależność v1.

## Historyczna granica badań modelowych

Poniższe zasady pozostają wymaganiami bezpieczeństwa dla ewentualnych badań
v2, a nie obietnicą ani częścią wspieranego runtime'u v1:

Model lokalny jest opcjonalnym rozszerzeniem badań v2 i nie blokuje wydania
runtime'u, ale nie jest wspieranym rozszerzeniem produktu v1.

- Każda poprawka pochodząca od modelu albo wybrana przez model zawsze pozostaje sugestią wymagającą jawnej akceptacji.
- Model otrzymuje małe, kontrolowane fragmenty tekstu i jednoznaczne zadanie.
- Odpowiedź musi mieć wersjonowany schemat JSON i przechodzić ścisłą walidację.
- Niepoprawna odpowiedź modelu nie może powodować awarii całej analizy.
- Model nie może zmieniać tekstu poza wskazanym zakresem.
- Każda sugestia ma zawierać kategorię, minimalną poprawkę, krótkie uzasadnienie i pewność.
- Wyniki o niskiej pewności powinny być oznaczone jako sugestie, nie błędy.
- Prompty i ustawienia generowania muszą być wersjonowane, testowalne i możliwie deterministyczne.
- Tekst wejściowy należy traktować jako dane, nigdy jako instrukcję dla modelu.

## Jakość i bezpieczeństwo korekt

- Preferuj brak sugestii zamiast sugestii nieuzasadnionej.
- Nie zmieniaj znaczenia, tonu ani stylu. Analiza stylistyczna nie należy do v1.
- Zachowuj wielkość liter i otaczające formatowanie tekstowe, jeśli nie są źródłem błędu.
- Wykrywaj nakładające się poprawki; nie stosuj ich automatycznie bez rozstrzygnięcia konfliktu.
- Nie polegaj wyłącznie na samoocenie pewności przez model. Kalibruj progi na zbiorze ewaluacyjnym.
- Każdy znaleziony błąd regresyjny powinien otrzymać test przed poprawką.

## Zasady programowania

- Używaj aktualnej, wspieranej wersji Pythona i zadeklaruj ją jawnie w `pyproject.toml`.
- Stosuj pełne adnotacje typów w publicznym API oraz rygorystyczne sprawdzanie typów.
- Używaj `ruff` do lintingu i formatowania oraz `mypy` albo równoważnego narzędzia do typów.
- Testuj kod przez `pytest`; oddziel testy jednostkowe, integracyjne i jakościowe.
- Unikaj globalnego stanu i ukrytych efektów ubocznych.
- Wstrzykuj zależności, zwłaszcza backend modelu, system plików i konfigurację.
- Publiczne API dokumentuj przykładami i opisem zachowania w sytuacjach błędnych.
- Nie dodawaj abstrakcji bez aktualnego zastosowania.
- Nie mieszaj dużej refaktoryzacji z nową funkcją w jednym issue.
- Każda zmiana zachowania wymaga testu.
- Zależności produkcyjne ograniczaj do uzasadnionego minimum i zapisuj powód ich dodania.
- Nigdy nie umieszczaj modeli, poufnych tekstów ani dużych zbiorów danych w repozytorium.

## Testowanie i ewaluacja

Zbuduj mały, wersjonowany zestaw ewaluacyjny już na początku projektu. Powinien zawierać poprawne i błędne polskie zdania, różne przypadki gramatyczne oraz trudne przykłady negatywne. Dane muszą mieć jasną licencję albo zostać stworzone na potrzeby projektu.

Mierz co najmniej:

- precision, recall i F1 dla wykrywania problemów;
- poprawność wskazanego zakresu znakowego;
- dokładność proponowanej korekty;
- odsetek fałszywych alarmów dla poprawnych zdań;
- opóźnienie i przepustowość;
- zużycie pamięci dla wspieranych konfiguracji.

Testy zależne od rzeczywistego modelu oznacz jako wolne i uruchamiaj oddzielnie. Szybki zestaw CI ma używać atrap backendu oraz zapisanych, zanonimizowanych odpowiedzi. Nie ustawiaj docelowych progów jakości bez pomiaru baseline'u; pierwszym zadaniem ewaluacyjnym jest wyznaczenie baseline'u i zaproponowanie realistycznych bramek.

## Obsługa błędów

Zdefiniuj stabilną hierarchię wyjątków biblioteki. Rozróżniaj co najmniej błędy konfiguracji, niedostępny backend, przekroczenie czasu, niepoprawną odpowiedź modelu oraz konflikt poprawek. Komunikaty mają być użyteczne, lecz nie mogą ujawniać całego analizowanego tekstu bez wyraźnej opcji diagnostycznej.

## Dokumentacja

Repozytorium powinno zawierać:

- `README.md` z opisem celu, szybkiego startu i ograniczeń;
- dokument architektury i rekordy najważniejszych decyzji;
- opis publicznego API;
- instrukcję uruchomienia offline dla wspieranych backendów;
- przewodnik dodawania deterministycznej reguły v1;
- metodologię benchmarków oraz aktualne wyniki;
- politykę prywatności jasno stwierdzającą, że biblioteka nie wysyła tekstu do sieci.

Nowe i aktywnie utrzymywane dokumenty autorskie pisz po polsku. Nie tłumacz
mechanicznie kontraktów maszynowych, historycznych planów, zamrożonych dowodów,
raportów, zaakceptowanych ADR-ów, opublikowanych release notes ani materiałów
upstream. Każda migracja językowa musi zachować znaczenie kontraktów, linki,
ścieżki, przykłady kodu i niezmienne identyfikatory.

## Planowanie w GitHub

Przed implementacją:

1. Przeanalizuj ten dokument i stan repozytorium.
2. Zapisz otwarte decyzje oraz ryzyka.
3. Zaproponuj roadmapę pogrupowaną w milestone'y.
4. Utwórz atomowe GitHub Issues z zależnościami i kryteriami akceptacji.
5. Sprawdź, czy każde issue można wykonać i zweryfikować niezależnie.

Każde issue powinno zawierać:

- jednoznaczny cel;
- uzasadnienie;
- zakres i elementy poza zakresem;
- kryteria akceptacji możliwe do sprawdzenia;
- wymagane testy i dokumentację;
- zależności od innych issue;
- etykietę rodzaju pracy i przypisany milestone.

Issue powinno zwykle odpowiadać jednej niewielkiej zmianie możliwej do ukończenia w jednym skupionym cyklu pracy. Jeśli opis łączy spójnikiem „i” dwa niezależne rezultaty, rozważ podział.

## Proponowane milestone'y

Poniższe milestone'y są historyczną propozycją początkową. Aktualną kolejność
produktu i badań utrzymuje `docs/project/ROADMAP.md`, a szczegółowe kryteria
realizacji znajdują się w GitHub issues.

### M0 — Fundament i decyzje

- cele jakościowe i jawny zakres MVP;
- szkielet pakietu i narzędzia jakości;
- modele danych oraz kontrakt publicznego API;
- protokół analizatora i opcjonalnego backendu LLM;
- początkowy zestaw ewaluacyjny;
- rekord decyzji dotyczącej licencji i wspieranych wersji Pythona.

### M1 — Deterministyczny rdzeń

- segmentacja z przesunięciami;
- rejestr reguł;
- pierwsze reguły o wysokiej precyzji;
- scalanie i deduplikacja wyników;
- wykrywanie konfliktów oraz stosowanie poprawek;
- serializacja JSON.

### M2 — Opcjonalne badania lokalnego modelu

- adapter pierwszego backendu;
- wersjonowane polecenia i schemat odpowiedzi;
- walidacja, timeouty i kontrolowane ponowienia;
- integracja wyników LLM z rdzeniem;
- benchmark kandydatów na model;
- dokumentacja instalacji i pracy offline.

M2 nigdy nie blokuje dostarczenia runtime'u przez M3 ani M4.

### M3 — Jakość MVP

- rozszerzony zestaw ewaluacyjny;
- baseline i bramki jakościowe;
- testy wydajności i pamięci;
- dokumentacja publicznego API;
- przykłady użycia i cienkie CLI;
- przygotowanie pierwszego wydania przedprodukcyjnego.

### M4 — Stabilizacja wydania

- przegląd kompatybilności i semantycznego wersjonowania;
- audyt prywatności i zależności;
- pełna dokumentacja migracji i ograniczeń;
- pakiet publikowalny w PyPI;
- release notes oraz wersja `0.1.0`.

Milestone'y są propozycją początkową. Zmień je po analizie repozytorium, jeśli potrafisz uzasadnić prostszy lub bezpieczniejszy podział.

## Aktualny workflow

Każde issue jest realizowane na krótkotrwałej gałęzi i w osobnym pull requeście.
Nie implementuj bezpośrednio na `main`. Obowiązują zasady:

- jedno issue odpowiada jednemu commitowi;
- jeden commit realizuje tylko jedno issue;
- przed rozpoczęciem issue sprawdź jego kryteria akceptacji i zależności;
- przed commitem uruchom właściwe testy, linting i kontrolę typów;
- komunikat commita odwołuje się do numeru issue;
- pull request wymaga niezależnego review i zielonego CI przed scaleniem;
- issue zamykaj dopiero po weryfikacji kryteriów akceptacji;
- nie wykonuj `force push` i nie przepisuj opublikowanej historii;
- nie omijaj nieudanych kontroli jakości.

Prace równoległe muszą używać odrębnych gałęzi lub worktree i nie mogą
jednocześnie modyfikować tych samych plików bez uzgodnionej własności.

## Role w pracy wieloagentowej

Role są rozdzielone logicznie nawet wtedy, gdy początkowo wykonuje je jeden agent:

- **Planner** — rozbija cele na milestone'y i atomowe issue, zarządza zależnościami;
- **Implementer** — realizuje jedno przydzielone issue bez rozszerzania zakresu;
- **Reviewer** — sprawdza zgodność z kryteriami, architekturą i jakością kodu;
- **QA/Evaluator** — tworzy przypadki brzegowe, uruchamia testy i ocenia regresje językowe;
- **Maintainer** — rozstrzyga konflikty architektoniczne, zatwierdza wydania i pilnuje spójności specyfikacji.

Implementer nie powinien samodzielnie uznawać istotnej zmiany za gotową w trybie wieloagentowym. Agenci nie mogą równocześnie modyfikować tych samych plików bez uzgodnienia własności zadania. Przekazanie pracy musi zawierać numer issue, zmienione pliki, wyniki testów, znane ograniczenia i kolejne kroki.

## Definition of Done

Issue jest ukończone wyłącznie wtedy, gdy:

- spełniono wszystkie kryteria akceptacji;
- dodano lub zaktualizowano testy;
- właściwe testy przechodzą;
- linting, formatowanie i sprawdzanie typów przechodzą;
- zaktualizowano dokumentację, jeśli zmienił się interfejs lub zachowanie;
- nie pozostawiono nieopisanych obejść, placeholderów ani ukrytych zmian zakresu;
- commit jest mały, spójny i odwołuje się do issue;
- wynik zweryfikowano, a nie tylko zaimplementowano.

Milestone jest ukończony dopiero wtedy, gdy wszystkie wymagane issue są zamknięte, testy integracyjne przechodzą, a znane ograniczenia są udokumentowane.

## Rozpoczęcie pracy przez agenta

Przed implementacją:

1. Przeczytaj cały ten dokument, `AGENTS.md`, aktualną roadmapę i bieżące issue.
2. Potwierdź zależności, kryteria akceptacji i granice chronionych danych.
3. Sprawdź, czy plan jest atomowy i nie koliduje z równoległą pracą.
4. Utwórz krótkotrwałą gałąź lub worktree.
5. Realizuj zaakceptowany plan zgodnie z workflow i Definition of Done.

Nie twórz masowo issue ani nie rozszerzaj zakresu bez potwierdzenia właściciela.
