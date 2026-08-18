# Publiczny zbiór jakości v4

Zbiór `polis_v4_quality_development` jest publicznym, projektowym zbiorem
rozwojowym dla konserwatywnych reguł v1. Nie jest korpusem kalibracyjnym,
holdoutem ani raportem wyników. Etykiety i oczekiwane sugestie zostały opisane
przez autora projektu niezależnie od analizatora, modelu, sieci i Javy.

## Zakres

Artefakt zawiera 124 przypadki w pięciu kategoriach: agreement, inflection,
punctuation, spelling i syntax. Każda kategoria ma co najmniej osiem
oczekiwanych znalezisk, szesnaście kontrolowanych hard negative, co najmniej
trzy odrębne audytowane rodziny reguł lub zjawiska i co najmniej cztery
pary pozytyw/negatyw. Pary pokrywają wszystkie siedem wymaganych strat.
Każda kategoria jest obecna w siedmiu
stratach kształtu wejścia: `simple-local`, `sentence-internal`,
`multi-sentence`, `repeated-occurrence`, `unicode-and-case`,
`quotation-or-literal` oraz `conflict-or-abstention`.

Każde znalezisko ma półotwarty zakres `[start, end)`, zgodny z oryginalnym
tekstem, minimalną sugestię, uzasadnienie i dokładną rodzinę reguły `rule:*`.
Traceability każdego przypadku wiąże identyczne `source_identity`, `rule_family`
i `audit_row` z aktualnym `behavior_version` z publicznego audytu źródeł.
Nieznane, podstawione albo niespójne identyfikatory są odrzucane. Hard negative
musi wyjaśniać granicę językową, a para wskazuje oba identyfikatory oraz cechę,
która rozróżnia przypadki. Przypadki zależne od morfologii opisują osobno
zachowanie bez providera i po uzyskaniu kwalifikowanej zdolności.

## Proweniencja i wersjonowanie

Manifest wiąże zbiór z zaakceptowanym kontraktem pokrycia reguł z issue #364,
pełnym zestawem identyfikatorów po przeglądzie maintenera, skrótem treści oraz
osobnym skrótem manifestu. Wersje v1, v2 i v3 są niezmiennymi poprzednikami i
nie są przenoszone do v4. Manifest przechowuje również skróty bajtów v3, aby
walidacja wykrywała przypadkową zmianę wcześniejszych artefaktów.

### Korekta kontroli konfliktu (#376)

Kontrolka `v4_control_conflict_agreement` używa tekstu `Te dziecko śpi.`.
Obie konkurencyjne, nakładające się reprezentacje edycji są językowo poprawne
i prowadzą do tego samego poprawnego zdania `To dziecko śpi.`:

- `Te` → `To`, zakres `[0, 2)`;
- `Te dziecko` → `To dziecko`, zakres `[0, 10)`.

Pierwotna wersja kontrolki błędnie dopuszczała `Te` → `Ten` w `Te zdanie.`.
Forma `zdanie` ma rodzaj nijaki, więc wynik `Ten zdanie` jest niepoprawny i
nie może być złotą konkurencyjną sugestią. Korekta zachowuje rolę konfliktu,
abstencję runtime'u oraz minima kontraktu #364/#366; zmienia wyłącznie publiczny
v4 gold control, nie regułę `rule:agreement.te_zdanie` ani politykę korekt.
Walidator wiąże tę semantykę z kontrolką i odrzuca powrót starego przypadku.

Po korekcie canonical digest zbioru to
`e87ad62b54d5d77c00b32c43cc5ee74d7347cdaa5501bc72080eddd79e12fba4`, a digest
manifestu to `0561200bd16319737e4c484ba220ff588ae964dddd680f0285d88e35140cc07b`.
Digest listy przejrzanych identyfikatorów pozostaje
`f8a36263a0d42e9b3eb68688752416ab51bf073b4cb19125ddfaca1530750c0e`;
review obejmuje nadal wszystkie 124 przypadki. Wiązania bajtów v3 pozostają
bez zmian.

Konflikty i abstencje pozostają wynikami review-only. Zbiór nie ustanawia
progów jakości, nie zmienia zachowania runtime'u i nie upoważnia do
automatycznego wdrażania żadnej reguły. Przekazanie do #367 wymaga ponownego
pomiaru clean-wheel z nową tożsamością zbioru; dopiero wynik #367 może zasilić
kwalifikację #368.

## Walidacja

Walidator czyta wyłącznie publiczne pliki v4 i nie uruchamia sieci, modelu,
Javy, kalibracji ani holdoutu. Przekazanie techniczne do ponownego pomiaru #367
oraz późniejszej kwalifikacji #368 znajduje się w
[`quality-v4-368-handoff.md`](quality-v4-368-handoff.md): nie jest ono zgodą na
próg ani implementację reguły.

```bash
uv run --locked --extra dev python scripts/validate_quality_dataset_v4.py --json
```

Walidacja odrzuca między innymi duplikaty identyfikatorów, rozjazd skrótów,
niezgodne zakresy, nieoznaczone nakładanie znalezisk, niekompletne pary,
brakujące uzasadnienia hard negative, niepełną proweniencję i niespełnione
minima kategorii lub strat.
