# Wyjątek inwentarza dokumentacji dla aktywnego zbioru jakości

## Kontekst

Issue #229 dodaje aktywny, edytowalny zbiór danych produktu pod prefiksem
`src/polis/evaluation/datasets/quality/`. Obecna walidacja inwentarza traktuje
każdy plik `cases.json` lub `manifest.json` pod `src/polis/evaluation/` jako
chroniony, historyczny dowód badawczy. Ta heurystyka poprawnie chroni starszy
zbiór `src/polis/evaluation/datasets/v1/`, lecz błędnie obejmuje nowy zbiór
runtime-first.

## Decyzja

Walidator otrzyma jeden wąski wyjątek dla dokładnego prefiksu
`src/polis/evaluation/datasets/quality/`. Funkcja ustalająca wymagane
rozporządzenie chronionego artefaktu zwróci brak wymagania przed zastosowaniem
ogólnej heurystyki dowodów wyłącznie dla ścieżek pod tym prefiksem.

Wyjątek oznacza, że aktywne pliki jakości nie trafiają do
`docs/project/documentation-migration-inventory.json` jako
`retain_research_evidence`. Nie zmienia to ochrony żadnej innej ścieżki,
nazwy pliku ani korzenia dowodów. W szczególności historyczny
`src/polis/evaluation/datasets/v1/cases.json` nadal wymaga dokładnej reguły
`retain_research_evidence`.

## Przepływ walidacji

1. Walidator normalizuje ścieżkę repozytorium.
2. Jeśli ścieżka należy do `src/polis/evaluation/datasets/quality/`, pomija
   klasyfikację jako chroniony dowód badawczy.
3. Dla wszystkich pozostałych ścieżek stosuje dotychczasowe reguły korzeni,
   nazw plików i wymaganych rozporządzeń.
4. Test kompletności repozytorium używa tej samej granicy, aby aktywny zbiór
   jakości nie był kandydatem do historycznego inwentarza.

## Obsługa błędów i granice

Nie powstaje mechanizm konfiguracyjny ani ogólny system wyjątków. Literówka,
nowy sąsiedni katalog lub historyczny `cases.json` poza dokładnym prefiksem
pozostają fail-closed i nadal wymagają wpisu inwentarza. Format komunikatów
błędów pozostaje bez zmian.

Granica aktywnych danych zostanie opisana po polsku w
`docs/project/DOCUMENTATION-ROADMAP.md`: `datasets/quality/` jest edytowalnym
składnikiem produktu, natomiast zamrożone zbiory badawcze pozostają chronione
przez inwentarz.

## Testy akceptacyjne

- walidator akceptuje `datasets/quality/v1/cases.json` i `manifest.json` bez
  wpisów `retain_research_evidence`;
- test kompletności nie dodaje plików pod dokładnym aktywnym prefiksem do
  kandydatów chronionego inwentarza;
- niezarejestrowany historyczny `cases.json` pod inną ścieżką
  `src/polis/evaluation/` nadal powoduje błąd;
- istniejąca ochrona `src/polis/evaluation/datasets/v1/cases.json` pozostaje
  zielona;
- pełny zestaw testów bez markerów `research` i `slow` przechodzi bez wyjątków.

## Zakres zmiany

Zmiana obejmuje wyłącznie walidator inwentarza, jego test regresyjny i opis
granicy w dokumentacji projektu. Nie zmienia danych jakości, schematu
inwentarza, klasyfikacji innych artefaktów ani polityki niezmienności dowodów.
