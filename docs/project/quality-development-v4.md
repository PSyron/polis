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

Konflikty i abstencje pozostają wynikami review-only. Zbiór nie ustanawia
progów jakości, nie zmienia zachowania runtime'u i nie upoważnia do
automatycznego wdrażania żadnej reguły.

## Walidacja

Walidator czyta wyłącznie publiczne pliki v4 i nie uruchamia sieci, modelu,
Javy, kalibracji ani holdoutu:

```bash
uv run --locked --extra dev python scripts/validate_quality_dataset_v4.py --json
```

Walidacja odrzuca między innymi duplikaty identyfikatorów, rozjazd skrótów,
niezgodne zakresy, nieoznaczone nakładanie znalezisk, niekompletne pary,
brakujące uzasadnienia hard negative, niepełną proweniencję i niespełnione
minima kategorii lub strat.
