# Roadmapa polskiej dokumentacji

Status: polityka `1.0` przyjęta w ramach issue #158.

## Cel

Aktywnie utrzymywana, autorska dokumentacja Polis jest tworzona po polsku.
Migracja nie może zmieniać zachowania runtime'u, kontraktów maszynowych ani
historycznych dowodów. Kod, identyfikatory, importy, schematy, flagi CLI, klucze
konfiguracji, literały protokołów oraz metadane GitHub pozostają po angielsku.

Repozytorium zachowuje wspierany produkt i dokładną powłokę dowodową badań.
Pełny wykonywalny stan sprzed sprzątania jest dostępny na
`feature/v2-research-archive` zgodnie z
[manifestem archiwum](v2-research-archive-manifest.md). Wheel i sdist zachowują
ścisłą granicę runtime-first.

## Inwentarz i kolejność reguł

Maszynowym źródłem klasyfikacji jest
[`documentation-migration-inventory.json`](documentation-migration-inventory.json).
Reguły są uporządkowane, a pierwsze dopasowanie rozstrzyga klasyfikację. Każdy
chroniony dowód ma dokładny wpis `paths`; reguły ochronne nie używają prefiksów.
Dzięki temu dowód zawsze wygrywa z ogólną regułą dla `docs/`, a wykonywalny plik
pod `experiments/`, `data/` lub `third_party/` nie zyskuje ochrony tylko przez
położenie w katalogu.

Walidator analizuje wyłącznie ścieżki zwrócone przez `git ls-files`; nie otwiera,
nie kopiuje i nie haszuje treści dokumentów:

```console
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
```

Każdy śledzony plik Markdown musi otrzymać jedną efektywną dyspozycję:

| Dyspozycja | Znaczenie |
| --- | --- |
| `maintain_polish` | Dokument jest już po polsku i pozostaje aktywnie utrzymywany. |
| `translate_polish` | Dokument zostanie przetłumaczony w przypisanej fali. |
| `retain_machine_facing_english` | Materiał obsługuje angielskie metadane GitHub lub kontrakt maszynowy. |
| `retain_upstream_original` | Treść pochodzi z vendored/upstream i zachowuje oryginał. |
| `retain_historical_evidence` | Historyczny plan, zaakceptowany ADR lub niezmienny zapis wydania nie podlega mechanicznemu tłumaczeniu. |
| `retain_research_evidence` | Zamrożony materiał badawczy pozostaje niezmiennym dowodem. |

## Nienaruszalne granice

- Każdy istniejący plan i każda specyfikacja w `docs/superpowers/` ma dokładny
  chroniony wpis i pozostaje historycznym zapisem pracy.
- W `experiments/` i `data/` pozostają tylko dokładnie wymienione pliki
  dowodowe klas zatwierdzonych w ADR-0022. Wykonywalne runnery nie są chronione
  samym prefiksem i mogą zostać usunięte w osobnym issue.
- W `third_party/languagetool-pl/` dokładnie wymienione licencje, noty,
  manifest, benchmark, README i patch pozostają dowodem upstream. Źródła
  vendorowe nie są chronione samym prefiksem.
- Każdy zaakceptowany ADR ma dokładny chroniony wpis i pozostaje niezmienny.
  Polski indeks może streszczać decyzję, ale nie zastępuje oryginału.
- `CHANGELOG.md` i każdy opublikowany wpis release notes mają dokładne chronione
  wpisy. Korekty są dopisywane jako errata, nie przez zmianę historii.
- Trzy zamrożone checklisty przeglądu korpusów są chronione przez dokładne
  ścieżki zapisane w inwentarzu.
- Zużyte holdouty, zamrożone raporty, manifesty, digesty i dowody wydania nie są
  modyfikowane, ponownie uruchamiane ani reinterpretowane przez migrację języka.
- Tłumaczenie nie zmienia kodu, API, source policy, progów jakości ani zawartości
  pakietów poza dokumentami jawnie objętymi danym issue.

## Fale migracji

Wszystkie poniższe issue należą do milestone'u `Runtime 0.x Hardening`, mają
etykietę `type:docs` i zależą od przyjęcia polityki w #158. Kolejność ogranicza
ryzyko semantyczne: najpierw ustala język wejścia do produktu, następnie
governance i kontrakty runtime'u, a dopiero potem dokumenty historycznie
powiązane z decyzjami i badaniami.

| Kolejność | Zakres | Issue | Area / priorytet | Następuje po | Główna weryfikacja |
| ---: | --- | --- | --- | --- | --- |
| 0 | Polityka, inwentarz i aktualizacja governance | [#158](https://github.com/PSyron/polis/issues/158) | `area:packaging`, `priority:P1` | — | testy polityki i pełność inwentarza |
| 1 | `README.md`, szybki start i ograniczenia produktu | [#159](https://github.com/PSyron/polis/issues/159) | `area:packaging`, `priority:P1` | #158 | linki oraz budowa i instalacja dystrybucji |
| 2 | Aktywna roadmapa produktu i rejestr ryzyk | [#160](https://github.com/PSyron/polis/issues/160) | `area:packaging`, `priority:P1` | #159 | niezmienność zależności i testy product charter |
| 3 | Publiczne API, personalizacja, reguły, segmentacja i kompatybilność | [#161](https://github.com/PSyron/polis/issues/161) | `area:core`, `priority:P1` | #160 | kontrakty publicznego API i architektury |
| 4 | Prywatność i praca offline | [#162](https://github.com/PSyron/polis/issues/162) | `area:packaging`, `priority:P1` | #161 | testy granicy offline-only |
| 5 | Dystrybucja i zależności; bez niezmiennych release notes | [#163](https://github.com/PSyron/polis/issues/163) | `area:packaging`, `priority:P1` | #162 | wheel/sdist, instalacja i tożsamość wydania |
| 6 | Indeks architektury, polskie streszczenia ADR-ów i aktywne dokumenty projektowe | [#164](https://github.com/PSyron/polis/issues/164) | `area:core`, `priority:P2` | #163 | kontrakty architektury i linki; oryginalne ADR-y bez zmian |
| 7 | Aktywne przewodniki ewaluacji i jakości | [#167](https://github.com/PSyron/polis/issues/167) | `area:evaluation`, `priority:P2` | #164 | wersje danych, progi i niezmienność dowodów |
| 8 | Kontrakty LLM i workflow badań | [#168](https://github.com/PSyron/polis/issues/168) | `area:llm`, `priority:P2` | #167 | schematy, quality gates i granica badań |

Issue #165 i #166 zostały wycofane przed implementacją: proponowały tłumaczenie
zaakceptowanych, niezmiennych ADR-ów. Polski indeks i streszczenia decyzji należą
do #164, natomiast oryginalne ADR-y nie są modyfikowane.

Każda fala jest osobnym, atomowym issue i PR-em. Nie wolno łączyć tłumaczenia z
refaktoryzacją kodu ani zmianą zachowania. Przed scaleniem należy sprawdzić linki,
ścieżki, `git diff --check`, właściwe testy kontraktów dokumentacyjnych oraz — gdy
dokument trafia do dystrybucji — budowę i instalację wheel/sdist.
