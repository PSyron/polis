# Projekt routingu kontekstowej fleksji polszczyzny

- Status: zaakceptowany dla issue #71
- Data: 2026-07-22
- Właściciel: Paweł Cyroń

## Cel

Wybrać skończoną formę LanguageTool dla wąsko wykrytego celu fleksyjnego w
jednym polskim zdaniu. Wykrywanie i wybór otrzymują wyłącznie tekst źródłowy,
zakresy tokenów i lokalną morfologię. Identyfikatory przypadków, warstwy korpusu,
tagi, oczekiwane wyniki i zakresy gold pozostają dostępne wyłącznie dla modułu
oceniającego.

## Alternatywy

1. **Jawne wymaganie przypadka i zgoda sąsiadujących imion i nazwisk — wybrane.**
   Wykrywa mały zamknięty zbiór relacji kontekstowych i wybiera wyłącznie
   unikalną skończoną formę spełniającą ich ograniczenia morfologiczne.
2. **Polecenie kompaktowemu modelowi wyboru spośród wszystkich form.** Odłożone,
   ponieważ ograniczenia deterministyczne mogą najpierw zmniejszyć
   niejednoznaczność i ustanowić bezpieczny baseline bez wag modelu ani
   zmienności promptu.
3. **Ranking form według częstości korpusowej.** Odrzucony, ponieważ sama
   częstość nie ustala wymaganego przypadka ani zgody, a runtime nie zawiera
   obecnie zatwierdzonego lokalnego zasobu częstości.

## Dowody wyłącznie ze źródła

Router rozpoznaje wyłącznie następujące wzorce lokalne dla zdania:

- dwa sąsiadujące tokeny słowne rozpoczynające się wielką literą: drugi token
  jest docelowym nazwiskiem, gdy jego obecna morfologia nie pokrywa się z
  obecnym przypadkiem i liczbą pierwszego tokenu ani ze zgodnym rodzajem;
- `bez`, po którym występuje jeden rzeczownik albo para przymiotnik–rzeczownik:
  fraza wymaga dopełniacza liczby pojedynczej przy zachowaniu liczby i rodzaju
  rzeczownika nadrzędnego;
- forma źródłowa zaczynająca się od `przygląd`, po której występują `się` oraz
  jeden rzeczownik albo para przymiotnik–rzeczownik: fraza wymaga celownika
  liczby pojedynczej;
- forma źródłowa zaczynająca się od `podzięk`, po której występuje jeden token
  rozpoczynający się wielką literą: token jest docelowym imieniem wymagającym
  celownika liczby pojedynczej.

Tokenizacja i zakresy celu powstają z tekstu źródłowego przed użyciem wrappera
korpusu. Nieobsługiwane układy interpunkcji, więcej niż dwa tokeny frazy, brak
analiz, formy nieodmienne, niejednoznaczność liczby mnogiej, niezgodne lematy
i nieunikalne wybory powodują wstrzymanie się od sugestii.

## Ograniczenia kandydatów

Istniejąca lokalna operacja `synthesize` dostarcza każdego kandydata. Propozycja
musi zachować żądany półotwarty zakres Unicode, wskazywać identyfikator kandydata
`ltpl:`, różnić się od formy źródłowej i być jedyną odrębną formą spełniającą
dowody. Przymiotniki dodatkowo zachowują stopień równy i zgadzają się z wybranym
rzeczownikiem pod względem przypadka, liczby i rodzaju. Nazwiska zachowują obecny
przypadek i liczbę sąsiadującego imienia oraz wymagają zgodnego rodzaju.

Niezmieniona forma źródłowa służy wyłącznie do wywnioskowania jej widocznych cech
morfologicznych. Gold nigdy nie wybiera celu, cechy, kandydata ani wstrzymania.

## Ewaluacja i holdout

Zbiór deweloperski (`development`) obejmuje wszystkie 69 zdań corpus-v3, a nie
tylko znane przypadki fleksyjne. Metryki obejmują wykrywanie celu, proweniencję
kandydatów, TP/FP/FN
dokładnych edycji, sugestie dla chronionych przykładów negatywnych, recall klas
dla imion, nazwisk i zwykłych słów, wstrzymania, warm p95, RSS procesu oraz
rozmiar runtime'u na dysku. Surowe zdania i odpowiedzi syntezy nie są zapisywane
w repozytorium.

Kandydat oceniany na zbiorze deweloperskim wymaga precyzji edycji co najmniej
0.90, recall wspieranej fleksji co najmniej 0.25, zera sugestii dla chronionych
przykładów negatywnych,
poprawnych niekolidujących zastosowań oraz warm p95 najwyżej 50 ms ponad
rozgrzany proces lokalny. Router i konfiguracja są zamrażane przed jednym
uruchomieniem holdoutu. Nieudany wynik na zbiorze deweloperskim pozostawia
holdout nieotwarty.

## Granica produkcyjna

Eksperyment działa wyłącznie jako źródło sugestii i nie jest zarejestrowany w
analizatorze. Wynik przechodzący bramki wymaga osobnej decyzji source-policy
przed automatyczną korektą. Akapity, generowane formy, wywołania chmurowe i
nieograniczone przepisywanie są wykluczone.
