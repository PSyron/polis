# Przekazanie jakości v4 do #368

Ten dokument jest maszynowo używalnym handoffem z #367 do #368. Kanoniczne
dowody regresji pozostają w wersjonowanych artefaktach
`docs/regression-*-v4*.json`; historyczne `quality-*` są wyłącznie aliasami;
ten skrót nie zastępuje ich walidacji i nie jest zgodą na implementację reguły.

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

Kanoniczne dowody regresji pozostają w wersjonowanych artefaktach
`docs/regression-*-v4*.json`; historyczne `quality-*` pozostają wyłącznie
niezmiennymi aliasami zgodności.

Canonical digest datasetu v4:

`0a767850af7f5d37ccb8f4b63544dad91a7bd11744fe02b9652ebf33f644af5c`

Digest manifestu:

`120247819ff38ec45341b0ad44ea72d3a1015c19d48f7d0b8ab298a9329382bf`

Digest kompletnej listy przejrzanych identyfikatorów:

`0ca59077aa406d02128147b63a95116eec67f886c569129207a6b872d2ab7703`

Review nadal obejmuje wszystkie 124 przypadki. Poprzednicy v1–v3 pozostają
chronieni i niezmienieni.

## Zatwierdzony pomiar #367

- source SHA: `07cd485d9778c56d195f93da899917035a808a39`;
- wheel SHA-256:
  `7b8df55e83df14cfadf1cff974131a3030912346672e33bf3f4e0b0e6662e091`;
- proposal: `docs/regression-threshold-proposal-v4.json`, status `approved`,
  `enforced: true`, SHA-256
  `166bf574cbda19b2f4f386ab602db6ba31d986b3b2cf44ede99491359de72610`;
- comparison: `docs/regression-comparison-v4.json`, `aggregate_verdict: pass`,
  SHA-256
  `adb52d0e8b53ef553f08977eb42345a0df05bcd7190641fc1ef25c18d4666016`;
- default: TP 39 / FP 0 / FN 0;
- morphology: TP 45 / FP 0 / FN 0;
- conflict violations: 0; abstention violations: 0 w obu profilach;
- pięć deterministycznych powtórzeń w każdym baseline i result.

Comparison pozostaje fail-closed przy naruszeniu kontroli, rozjeździe
tożsamości, brakującej metryce, regresji kategorii/straty lub
niedeterministycznych powtórzeniach.

## Następne dozwolone czynności

1. W #368 odczytać publiczne luki i case IDs z kanonicznych baseline'ów v4.
2. Zachować kolejność i pełną tożsamość 59 źródeł.
3. Nie zmieniać goldów v4 ani zatwierdzonych gate'ów, aby dopasować przyszłą
   implementację.
4. Każde poszerzenie reguły utrzymać review-only do osobnej kwalifikacji i
   ponownie sprawdzić comparison v4.

Walidacja publicznego zbioru, bez sieci, modelu, Javy, kalibracji i holdoutu:

```bash
uv run --locked --extra dev python scripts/validate_quality_dataset_v4.py --json
```

Po wykonaniu pomiarów zweryfikuj artefakty skryptem
`scripts/validate_runtime_performance_v2.py`, podając rzeczywiste wartości
identyfikatorów źródła, wheel, datasetu, manifestu, protokołu i workera. Każdy
placeholder w dokumentacji jest wartością wejściową do zastąpienia; żaden nie
może trafić do artefaktu.
