# Przekazanie jakości v4 do #367 i #368

Ten dokument wiąże korektę publicznego gold control z dalszym pomiarem #367.
Nie jest baseline'em, propozycją progu ani zgodą na implementację reguły.

## Stan po #376

- `v4_control_conflict_punctuation` używa `Pada deszcz Anna wraca.`.
- Jego dwie konkurencyjne i minimalne insercje w `[11, 11)` to kropka oraz
  średnik: `Pada deszcz. Anna wraca.` i `Pada deszcz; Anna wraca.`.
- Insercje mają różne teksty końcowe i konfliktują według produkcyjnego
  `findings_conflict`, więc przypadek wymaga abstencji zamiast arbitralnego
  wyboru znaku.
- Traceability używa jawnej projektowej tożsamości niejednoznaczności, a nie
  niepasującej aktualnej reguły runtime.
- Provider-absent i qualified-morphology zwracają zero sugestii dla dokładnego
  tekstu, ponieważ runtime nie rozstrzyga wyboru interpunkcji bez kontekstu
  dyskursowego.
- Minima kategorii, kształtu i profili z kontraktu #364/#366 oraz wszystkie
  wiązania v3 pozostają niezmienione.

## Tożsamość artefaktu

Canonical digest datasetu v4:

`0a767850af7f5d37ccb8f4b63544dad91a7bd11744fe02b9652ebf33f644af5c`

Digest manifestu:

`120247819ff38ec45341b0ad44ea72d3a1015c19d48f7d0b8ab298a9329382bf`

Digest kompletnej listy przejrzanych identyfikatorów:

`0ca59077aa406d02128147b63a95116eec67f886c569129207a6b872d2ab7703`

Review nadal obejmuje wszystkie 124 przypadki. Poprzednicy v1–v3 pozostają
chronieni i niezmienieni.

## Następne dozwolone czynności

1. Uruchomić publiczny validator v4 z finalnych bajtów.
2. Wykonać świeży clean-wheel baseline i powtórny pomiar #367 dla obu profili,
   wiążąc wynik z nowym digestem datasetu, manifestu, pełnym SHA źródeł oraz
   digestem koła.
3. Sprawdzić osobno zero naruszeń konfliktu i abstencji oraz pełną tożsamość
   źródeł, profilu i providera.
4. Dopiero po niezależnym przeglądzie i akceptacji wyników #367 przekazać
   zweryfikowane luki do #368. Ten dokument nie wybiera progów i nie otwiera
   żadnej pracy nad regułą.

Walidacja publicznego zbioru, bez sieci, modelu, Javy, kalibracji i holdoutu:

```bash
uv run --locked --extra dev python scripts/validate_quality_dataset_v4.py --json
```
