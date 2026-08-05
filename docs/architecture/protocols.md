# Granice protokołów runtime'u

Runtime v1 składa się z małych, deterministycznych elementów. `Rule` zwraca
znaleziska jednego stabilnego źródła, `VersionedRule` dodaje operację i wersję
zachowania, a `RuleRegistry` wykonuje ustaloną kolejność reguł. `Analyzer`
tworzy gotowy rejestr i zwraca zwalidowany `AnalysisResult`.

## DeterministicAnalyzer

`DeterministicAnalyzer` opisuje źródło znalezisk dla tekstu i lokalnych opcji.
Nie interpretuje znaczenia ani nie wybiera korekty.

## Rule

`Rule` ma jedno stabilne źródło. `VersionedRule` dodaje identyfikator operacji
i wersję zachowania potrzebne polityce source-policy.

## RuleRegistry

`RuleRegistry` uruchamia reguły w ustalonej kolejności, waliduje ich wynik i
zachowuje filtrowanie kategorii.

## AnalysisOrchestrator

`AnalysisOrchestrator` opisuje wspólny kontrakt wejść synchronicznych i
asynchronicznych: pełny wynik albo kontrolowany błąd; nie zwraca wyniku
częściowego.
Protokoły nie odpowiadają za zmianę tekstu ani wybór automatycznej korekty.
Ten wybór należy do `Analyzer.correct()` i obowiązującej polityki źródeł.

Interfejsy są celowo wąskie. Nowe źródło wymaga bieżącego konsumenta,
deterministycznego kontraktu, testów i osobnej decyzji, jeżeli zmieniałoby
granicę produktu. Granicę tę określa
[ADR-0022](decisions/0022-conservative-v1-product-scope.md).
