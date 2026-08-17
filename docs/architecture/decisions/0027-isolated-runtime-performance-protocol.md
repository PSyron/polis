# ADR-0027: izolowany protokół pomiaru wydajności runtime'u

- Status: Zaakceptowany
- Data: 2026-08-17
- Decydent: Paweł Cyroń

## Kontekst

Propozycja progów v3 zatwierdzona w #339 F1.3 odziedziczyła sposób pomiaru
wydajności z protokołu jakości: dataset, scoring, raportowanie oraz `Analyzer`
działały w jednym procesie. `peak_rss_bytes` oznaczało więc szczytowe RSS całego
procesu, a nie pamięć runtime'u.

Pomiar referencyjny Wave 0 używał `quality-development-v2` (92 przypadki).
Zamykająca weryfikacja Umbrella F używała `quality-development-v3` (340
przypadków i większy manifest). W świeżym procesie sam import Polis i
załadowanie v3 osiągały limit RSS profilu default przed analizą. W profilu
morfologicznym znaczną część RSS zajmował dostawca przed załadowaniem datasetu.
Porównanie absolutnego RSS mieszało zatem koszt runtime'u ze zmiennym kosztem
harnessu i nie miało wspólnego mianownika.

#355 i częściowy #358 zmniejszyły koszt dispatchu bez zmiany semantyki. Nie
rozwiązały nieporównywalnego mianownika RSS. Poszerzenie capów w miejscu
ukryłoby problem metodologiczny.

## Decyzja

Wprowadzamy `polis.runtime-performance` w wersji 2 jako repozytorium-only
protokół pomiarowy z izolowanym procesem workera.

### Proces nadrzędny

- ładuje dataset, goldy i scoring;
- uruchamia workera z czystego środowiska zainstalowanego wheel;
- przesyła tekst lokalnym JSON Lines przez stdin/stdout;
- zapisuje RSS harnessu oddzielnie i nie używa go jako gate'u runtime'u.

### Worker runtime'u

- importuje wyłącznie zainstalowany wheel i tworzy jeden `Analyzer`;
- nie ładuje datasetu, manifestu, goldów ani scoringu;
- mierzy czas wyłącznie wokół `Analyzer.analyze`;
- raportuje startup RSS, peak RSS, kanoniczne findings i tożsamość środowiska;
- dla `default` wymaga braku Morfeusz2;
- dla `morphology` wymaga dokładnie Morfeusz2 1.99.15, słownika
  `pl.sgjp.sgjp-2026.06.01` i zaakceptowanego hasha noty;
- odrzuca nieznane pola, operacje, wersje i niespójne sekwencje.

Tekst pozostaje lokalny i offline. JSONL jest kanałem między procesami na tym
samym urządzeniu, nie interfejsem sieciowym ani publicznym API produktu.

### Nowe progi

Nie przepisujemy historycznego `quality-threshold-proposal-v3.json`. Zamiast
tego mierzymy referencję Wave 0 i bieżący runtime tym samym protokołem v2, na
tym samym datasecie v3, Pythonie, platformie, profilach i liczbie powtórzeń.
Nowy addytywny artefakt governance wiąże capy protokołu v2 z pomiarem Wave 0 i
zachowuje zero tolerance.

## Co zostaje w mocy

- ADR-0026 i `exact-ordered-59`;
- quality-development-v3 i floors jakości;
- review-only wszystkich dodatków Umbrella F;
- brak zmian automatic policy;
- fail-closed przy braku metryki, niedeterministyczności lub różnicy środowiska;
- wymóg clean wheel, Python 3.13.12 i Darwin arm64 dla porównania;
- historyczne artefakty Wave 0 i propozycja v3 pozostają niezmienne.

## Co zostaje zastąpione

Wyłącznie interpretacja absolutnych performance gates #339 F1.3 jako metryk
całego procesu `quality_runner` dla zamknięcia #337. Dla nowych decyzji
wydajnościowych obowiązuje runtime-only denominator protokołu v2. Historyczny
wynik starego protokołu pozostaje audytowalny i nie jest przepisywany.

## Konsekwencje

### Pozytywne

- RSS runtime'u jest porównywalny niezależnie od rozmiaru datasetu;
- latency/throughput nie zawierają IPC ani scoringu;
- reference i current mają wspólny mianownik;
- można osobno diagnozować pamięć harnessu i runtime'u;
- capów nie trzeba poluzowywać, aby naprawić eksperyment.

### Negatywne

- pomiar wymaga procesu podrzędnego i ścisłego protokołu JSONL;
- trzeba budować dwa clean wheels lub odtwarzać referencyjny SHA;
- stare liczby whole-process i nowe runtime-only nie są bezpośrednio
  porównywalne; raport musi zawsze podawać wersję protokołu.
