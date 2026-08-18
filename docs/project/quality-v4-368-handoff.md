# Przekazanie jakości v4 do #367 i #368

Ten dokument wiąże korektę publicznego gold control z dalszym pomiarem #367.
Nie jest baseline'em, propozycją progu ani zgodą na implementację reguły.

## Stan po #376

- `v4_control_conflict_agreement` używa `Te dziecko śpi.`.
- Jego dwie konkurencyjne reprezentacje są językowo poprawne:
  `Te` → `To` oraz `Te dziecko` → `To dziecko`.
- Obie edycje prowadzą do `To dziecko śpi.` i nakładają się na zakresach
  `[0, 2)` oraz `[0, 10)`, dlatego przypadek nadal wymaga abstencji zamiast
  arbitralnego wyboru zakresu.
- Nie występuje już goldowa sugestia `Ten zdanie`; `Ten` nie zgadza się z
  nijakim rzeczownikiem `zdanie`.
- Provider-absent i qualified-morphology zachowują odpowiednio wykonanie tej
  niezależnej od providera kontrolki; oczekiwaniem obu profili pozostaje
  zero sugestii dla konfliktu.
- Minima kategorii, kształtu i profili z kontraktu #364/#366 oraz wszystkie
  wiązania v3 pozostają niezmienione.

## Tożsamość artefaktu

Canonical digest datasetu v4:

`e87ad62b54d5d77c00b32c43cc5ee74d7347cdaa5501bc72080eddd79e12fba4`

Digest manifestu:

`0561200bd16319737e4c484ba220ff588ae964dddd680f0285d88e35140cc07b`

Digest kompletnej listy przejrzanych identyfikatorów:

`f8a36263a0d42e9b3eb68688752416ab51bf073b4cb19125ddfaca1530750c0e`

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
