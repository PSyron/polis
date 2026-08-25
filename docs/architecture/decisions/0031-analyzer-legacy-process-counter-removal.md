# ADR-0031: Usunięcie historycznego licznika procesu z publicznego `Analyzer`

- Status: Accepted
- Date: 2026-08-25
- Owner: Paweł Cyroń
- Issue: #420
- Zastępuje: wyłącznie zobowiązanie dotyczące `Analyzer.language_tool_process_start_count` zapisane w ADR-0022; nie zmienia treści ADR-0022

## Kontekst

ADR-0022 zachował `Analyzer.language_tool_process_start_count` przez całą linię
0.x, mimo że wspierany runtime v1 nie uruchamia procesu Java ani pełnego
LanguageTool. Licznik zawsze zwracał `0`, więc opisywał usuniętą architekturę i
tworzył publiczną powierzchnię bez wspieranego zastosowania.

Issue #420 usuwa tę pozostałość z publicznego API. Zmiana dotyczy wyłącznie
nieużywanego licznika; nie przywraca procesu, sieci, modelu ani zależności i
nie zmienia wyników analizy.

## Decyzja

`Analyzer.language_tool_process_start_count` zostaje usunięty z publicznego
API w linii 0.x. Kod klienta nie powinien już odczytywać tego atrybutu; migracja
polega na usunięciu odwołania, ponieważ wspierany runtime nie uruchamia procesu,
którego stan można by obserwować.

Pozostałe powierzchnie zgodności pozostają bez zmian:

- `Analyzer.close()`, `Analyzer.__enter__()` i `Analyzer.__exit__()` pozostają
  bezpiecznymi operacjami no-op;
- `Category.STYLE`, `polis.evaluation`, znaleziska, zakresy `[start, end)` oraz
  pozostałe publiczne punkty wejścia zachowują dotychczasowy kontrakt;
- runtime nadal działa offline, fail-closed i bez lokalnego modelu, sieci,
  procesu pomocniczego ani nowej zależności.

ADR-0022 pozostaje zaakceptowanym, niezmienionym zapisem historycznej decyzji.
Niniejszy ADR jest aktualną decyzją dla wąskiego wyjątku dotyczącego licznika i
powinien być przywoływany w dokumentacji opisującej tę zmianę.

## Konsekwencje

- `hasattr(analyzer, "language_tool_process_start_count")` zwraca `False`, a
  bezpośredni odczyt usuniętego atrybutu kończy się standardowym
  `AttributeError`;
- klient nie może już błędnie traktować wartości `0` jako obserwacji procesu;
- nie zmienia się zachowanie analizy, korekty, filtrów kategorii,
  `polis.evaluation` ani innych elementów publicznego API;
- historyczne odwołania do ADR-0022 pozostają bez zmian, natomiast bieżące
  opisy usunięcia licznika wskazują ADR-0031.
