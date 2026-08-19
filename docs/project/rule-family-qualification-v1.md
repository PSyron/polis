# Kwalifikacja rodzin reguł v1 — zatwierdzona (#368)

## Cel i metoda

`rule-family-qualification-v1.json` jest macierzą kwalifikacji przed zgodą
maintainera. Łączy ona wyłącznie jawne artefakty #364, #365 i #367. Uniwersum
jest dokładną sumą:

- czterech wierszy #365 oznaczonych `deterministic_v1_candidate` lub
  `provider_dependent_candidate` (RJP-03, RJP-04, RJP-09a i RJP-10);
- wierszy źródeł #365 oznaczonych `change_required`;
- rzeczywistych, osobno wyemitowanych niewyjaśnionych luk publicznego v4;
- rzeczywistych konfliktów z kontraktem #364.

Bieżące artefakty nie emitują wiersza `change_required`, niewyjaśnionej luki
v4 ani konfliktu kontraktu. Zera są wynikiem walidacji artefaktów, a nie
uzupełnieniem intuicją. W szczególności wynik v4 ma zero FN na zmierzonym,
obsługiwanym podzbiorze; wiersze `unmeasured` oraz provider-absent `abstained`
nie są lukami.

Każda pozycja ma osobną tożsamość, pochodzenie, ocenę normatywną, granicę
deterministyczną, kontrakt wyniku, dowody publiczne, oczekiwaną wartość, ryzyko
oraz decyzję z dowodem możliwego wznowienia. Nie łączymy kandydatów w ogólną
rodzinę implementacyjną. Offsety są półotwarte `[start, end)` względem
oryginalnego tekstu.

## Wynik

Macierz zawiera **4 kandydatów**:

| Kandydat | Pochodzenie | Profil | Decyzja |
| --- | --- | --- | --- |
| `rjp-2026-03` | RJP-03 | `provider-absent` | `reject: insufficient public evidence` |
| `rjp-2026-04` | RJP-04 | `qualified-morphology` | `reject: insufficient public evidence` |
| `rjp-2026-09a` | RJP-09a | `provider-absent` | `reject: insufficient public evidence` |
| `rjp-2026-10` | RJP-10 | `provider-absent` | `reject: insufficient public evidence` |

Liczba zaakceptowanych pozycji wynosi **0**. Nie ma zatem rankingu
implementacyjnego ani dziecięcych issue. Nie jest też nadawana etykieta priorytetu;
przyszły zaakceptowany wiersz musi jawnie wskazać własny priorytet, bez cichego
dziedziczenia P1. To poprawny stan kontraktu: braki
dowodów nie mogą być zastąpione obietnicą dodania testów w przyszłym issue.
Wszystkie cztery pozycje nie mają kandydata-specyficznych publicznych
pozytywów, hard negatives, kontrolowanych par, kompletnego pokrycia siedmiu
strat, obu profili ani wykonywalnych dowodów ryzyka. Sumy kategorii v4 nie są
substytutem takich dowodów.

## Priorytety i bezpieczeństwo

Ranking dotyczy wyłącznie pozycji zaakceptowanych. Algorytm jest
reprodukowalnym porządkiem leksykograficznym opisanym w JSON-ie; najpierw
uwzględnia kompletność/siłę dowodów, bezpieczeństwo precision i FAR, zakres
providera, koszt implementacji, a na końcu stabilną tożsamość kandydata.
Regresja precision, correct-sentence FAR, konflikt, dryf providera, brak
parzystości wejść albo brak dowodu ma pierwszeństwo przed recall. Oczekiwany
aggregate recall jest wyłącznie kontekstem i nie może uzasadnić akceptacji.

## Digest i zgoda

Digest macierzy jest propozycją SHA-256 kanonikalizowaną jako UTF-8 JSON z
`sort_keys=true`, zwartymi separatorami i `ensure_ascii=false`. Z obliczenia
wyłączone są pola cyklu życia `stage` i `status`, główne `approval`, pola stanu
`integrity`, a także `maintainer_approval` w każdym wierszu. Dzięki temu późniejsza
zgoda może związać dokładną treść kwalifikacji bez zmiany digestu i bez kołowego
haszowania. Bieżący digest to:

`66040415f9c9491054fda0232c00d39f4d8a2c311d1e44240acb797ca4a5e20d`

Maintainer zatwierdził dokładną treść kwalifikacji 19 sierpnia 2026 r. Zgoda
wiąże digest `66040415f9c9491054fda0232c00d39f4d8a2c311d1e44240acb797ca4a5e20d`.
W macierzy nie ma zaakceptowanych wierszy, dlatego prawidłowym i wymaganym
wynikiem jest zero child issues.

## Ograniczenia i wznowienie

Macierz nie implementuje reguł i nie zmienia runtime'u, etykiet zachowania,
polityki korekty, gold labels v4 ani zamrożonych dowodów. #367 nie dostarcza
kandydata-specyficznych luk dla tych czterech zmian, więc oczekiwana wartość
została zapisana jako zero zmierzonego v4, bez prognozowania przyszłego recall.

Wznowienie pozycji wymaga nowego, publicznego i licencjonowanego zestawu
przypadków spełniającego wszystkie minima #364: pozytywy, hard negatives,
kontrolowane pary, każdą wymaganą stratum, profile providera i wykonywalne
dowody precision/FAR, konfliktów, offsetów oraz wydajności. Dla RJP-04 musi
być użyta dokładna, już autoryzowana tożsamość Morfeusz2; brak lub dryf
providera musi kończyć się abstencją.

Walidator działa lokalnie dla macierzy i bezpiecznie odczytuje live issues
GitHuba przez wyłącznie `gh api --method GET`. Nie tworzy, nie edytuje ani nie
komentuje issue. Stan zero-dzieci jest reprezentowalny i przechodzi, gdy macierz
nie ma zaakceptowanych wierszy, a odczyt GitHuba potwierdzi brak dzieci. Dla
zaakceptowanej pozycji walidator wymaga finalnej zgody maintainera związanej z
digestem zarówno na poziomie macierzy, jak i wiersza oraz dokładnego markera
`Qualification matrix SHA-256: <digest>` w treści dziecka. Pending matrix z
zaakceptowanym wierszem nie przechodzi nawet wtedy, gdy dziecko jeszcze nie
istnieje.

Przykłady:

```bash
python -m polis.evaluation.rule_family_qualification \
  validate-matrix \
  --matrix docs/project/rule-family-qualification-v1.json \
  --repo .

python -m polis.evaluation.rule_family_qualification \
  validate-children \
  --matrix docs/project/rule-family-qualification-v1.json \
  --repo PSyron/polis
```
