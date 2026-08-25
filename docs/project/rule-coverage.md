# Jak czytać kontrakt pokrycia reguł v1

Polis nie używa liczby zarejestrowanych źródeł jako skrótu dla pokrycia języka.
Jedno źródło opisuje jedną obserwowalną tożsamość, a roszczenie o zdolności
kategorii wymaga osobnych publicznych dowodów, hard negatives i przypadków
abstencji.

Pełny kontrakt jest zapisany maszynowo w
[`rule-coverage-contract-v1.json`](rule-coverage-contract-v1.json), a decyzję
normatywną opisuje [ADR-0028](../architecture/decisions/0028-conservative-v1-rule-coverage-contract.md),
a wykonywanie validatora doprecyzowuje [ADR-0029](../architecture/decisions/0029-rule-coverage-contract-validator-hardening.md).
Podstawy normatywne i kandydackie oraz aplikowalność stratum doprecyzowuje
[ADR-0030](../architecture/decisions/0030-rule-coverage-authority-and-applicability-clarification.md).
Validator `scripts/rule_coverage_contract.py` odrzuca brakujące pola,
duplikaty, nieznane profile, niepełne minima próbkowania oraz drift zasad parity.
Uruchomienie `uv run --locked --extra dev python scripts/rule_coverage_contract.py`
sprawdza cały kontrakt i parity lokalnego repozytorium; ta sama komenda jest
wymagana przez fast CI i kończy się błędem przy każdym driftcie.

Po każdej zmianie reguły runtime'u maintainer musi wykonać sekwencję
`zmiana kodu → commit → --refresh → commit kontraktu`; opcja `--refresh`
odświeża dokładnie trzy pola pochodnych digestów: `planning_baseline.full_sha`,
`planning_baseline.snapshot_sha256` i `maintained_rule_inventory.rows_sha256`,
a przed zapisem odrzuca zmiany staged i unstaged w `_RUNTIME_SOURCE_PATHS`.
Polecenie bez `--refresh` pozostaje wyłącznie walidacyjne i nie modyfikuje
kontraktu.

## Profile

Raportuj osobno:

- `provider-absent`: działa bez opcjonalnego dostawcy morfologii; rodziny
  zależne od niego abstainują;
- `qualified-morphology`: rodziny zależne działają tylko z dokładnie
  zakwalifikowanym providerem, słownikiem i wersją noty.

Brak providera lub jego drift nie jest powodem do zgadywania. Wynik bez
wystarczających danych pozostaje abstencją.

## Metryki

Podstawą są exact-edit `TP`, `FP`, `FN`, precision, recall i F1, a także
zgodność zakresu `[start, end)`, sugestii oraz correct-sentence false-alarm rate.
Każdy wynik jest raportowany dla profilu, kategorii i straty. Zero w mianowniku
oznacza `null` i brak bramki, nie automatyczny sukces.
Exact-span accuracy obejmuje wyłącznie determinate incorrect cases: licznik to
nieużyte expected findings z dokładnym `[start, end)`, a mianownik to wszystkie
expected findings w tych przypadkach. Konflikty i abstencje nie mają span
denominatora.

Konflikty i przypadki abstencji nie są cicho dopisywane do zwykłego mianownika.
Mają własne oczekiwanie: brak sugestii. Aggregate recall nie może ukryć
niezbadanej kategorii ani zastąpić hard negative.

## Minimalna reprezentacja public-v4

Każda kategoria potrzebuje co najmniej 8 oczekiwanych pozytywów, 16 poprawnych
hard negatives, 3 różnych zjawisk/rodzin i 4 kontrolowanych par. Każda
stosowalna kategoria powinna mieć pozytyw i hard negative w stratach:

`simple-local`, `sentence-internal`, `multi-sentence`, `repeated-occurrence`,
`unicode-and-case`, `quotation-or-literal` oraz `conflict-or-abstention`.

Jeśli stratum albo rozróżnienie providera nie ma zastosowania, maszynowy
kontrakt musi zawierać status `not-applicable` i niepusty, konkretny powód.
Pominięcie bez powodu nie jest dowodem pokrycia.

## Źródła i polityka korekt

Ordered snapshot pochodzi z publicznego
`Analyzer(AnalyzerConfig()).source_identity_snapshot`. `docs/rules.md`, wersje
zachowania, polityka korekty i artefakty suity regresyjnej muszą zachować parity z tym
snapshotem. Nowa rodzina zaczyna jako `review-only`; automatic correction wymaga
osobnego, dokładnego klucza polityki i osobnej akceptacji.

Wyniki F1 z projektowego zbioru deweloperskiego są dowodem pokrycia regresji,
nie miarą jakości produktu. Przyszłe pomiary jakości wymagają osobnego zbioru,
którego reguły nie były pisane pod oceniane przypadki. Kanoniczne artefakty tej
suity używają prefiksu `regression-`; pliki `quality-*` są zachowanymi,
niezmienionymi aliasami historycznymi, a ich wartości liczbowe muszą pozostać
identyczne.

`planning_baseline` jest parą dokładnego, rozwiązywalnego SHA źródła oraz digestu
snapshotu. Validator odrzuca baseline, którego audytowane ścieżki runtime'u nie
są identyczne z bieżącymi, dlatego stary SHA nie może pozostać cichym źródłem
prawdy po zmianie zachowania.

Validator wiąże również kanoniczny digest uporządkowanych wierszy wykazu
(`source`, `category`, `scope`) oraz kompletną listę aktywnych kluczy polityki
automatycznej. Historyczne artefakty v3 publikują SHA źródła, dataset, profil i
tożsamość providera, ale nie publikują digestu snapshotu ani wersji zachowania;
ich opublikowane identyfikatory są sprawdzane dokładnie, a snapshot i wersje są
sprawdzane niezależnie z bieżącego runtime'u. SHA historycznych źródeł są
dodatkowo związane z lokalnym manifestem provenance zawierającym dokładne URL-e
commitów GitHub; validator nie pobiera sieci.

Katalog [`rule-coverage-normative-candidate-inventory-v1.json`](rule-coverage-normative-candidate-inventory-v1.json)
wiąże każdą kategorię z jawną podstawą normatywną albo statusem `not-claimed`.
RJP jest podstawą tylko dla jawnie zmapowanych przypadków pisowni i interpunkcji;
wykaz reguł i artefakty v3 pozostają źródłami kandydackimi, nie normą.

Kontrakt nie obejmuje release/packaging, modeli, sieci, Java, szerokiego
LanguageTool, stylu, semantyki, prywatnego tekstu ani chronionych dowodów.
