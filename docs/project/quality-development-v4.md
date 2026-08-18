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

Kontrolka `v4_control_conflict_punctuation` używa projektu `Pada deszcz Anna
wraca.`. To celowo nieinterpunkcyjna granica dwóch niezależnych zdań. Bez
kontekstu dyskursowego obie następujące, normatywnie dopuszczalne interpunkcje
są uzasadnione:

- wstawienie kropki w offset `[11, 11)`: `Pada deszcz. Anna wraca.`;
- wstawienie średnika w offset `[11, 11)`: `Pada deszcz; Anna wraca.`.

Są to dwie minimalne insercje (pusty oryginał, brak niezmienionego kontekstu),
mają różne teksty końcowe i pozostają konfliktem według produkcyjnego
`findings_conflict`, ponieważ dzielą ten sam offset insercji. Żaden aktualny
runtime source nie rozstrzyga tej niejednoznaczności; traceability jawnie używa
projektowej tożsamości `project-authored:ambiguity.punctuation_boundary`, a nie
podszywa kandydatów pod niepasującą regułę. Walidator dopuszcza tę jedną
projektową tożsamość wyłącznie w kontrolce konfliktu, jako najmniejszą korektę
schematu zgodną z #364/#366.

Poprzednia wersja błędnie używała `Te dziecko śpi.`: druga sugestia była
nieminimalnym zakresem prowadzącym do tego samego tekstu, a analizator emitował
`rule:agreement.te_neuter_noun`. Zastąpienie kontrolki nie zmienia runtime'u
ani polityki korekt. Dla dokładnego nowego tekstu aktualny Analyzer zasadnie
abstenuje w profilu bez providera i z kwalifikowaną morfologią: wybór kropki lub
średnika wymaga niedostępnego kontekstu dyskursowego, którego v1 nie wnioskuje.

Po korekcie canonical digest zbioru to
`0a767850af7f5d37ccb8f4b63544dad91a7bd11744fe02b9652ebf33f644af5c`, a digest
manifestu to `120247819ff38ec45341b0ad44ea72d3a1015c19d48f7d0b8ab298a9329382bf`.
Digest listy przejrzanych identyfikatorów to
`0ca59077aa406d02128147b63a95116eec67f886c569129207a6b872d2ab7703`;
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
