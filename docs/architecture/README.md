# Rejestr decyzji architektonicznych

Rejestry decyzji architektonicznych (Architecture Decision Records, ADR-y)
zachowują decyzje kształtujące Polis na przestrzeni wielu milestone'ów. Po
zaakceptowaniu ADR jest niezmienny; w razie zmiany polityki zastępuje go
późniejszy ADR.

| ADR | Status | Decyzja |
| --- | --- | --- |
| [ADR-0001](decisions/0001-python-platform-licensing-policy.md) | Zaakceptowany | Polityka wersji Pythona, platform, licencji i zasobów |
| [ADR-0002](decisions/0002-polish-nlp-dependency-strategy.md) | Zaakceptowany | Strategia zależności NLP dla polszczyzny oparta najpierw na bibliotece standardowej |
| [ADR-0003](decisions/0003-public-api-and-exception-contract.md) | Zaakceptowany | Kontrakt publicznego API i wyjątków |
| [ADR-0004](decisions/0004-local-llm-backend-selection.md) | Zaakceptowany | Pierwsza strategia lokalnego backendu i wybór zalążka dla MVP |
| [ADR-0005](decisions/0005-real-local-polish-model-benchmark.md) | Zaakceptowany | Żaden rzeczywisty model nie został jeszcze wybrany do automatycznej korekty |
| [ADR-0006](decisions/0006-local-languagetool-benchmark.md) | Zaakceptowany | LanguageTool pozostaje opcjonalny do czasu powstania wąskiego adaptera z allowlistą |
| [ADR-0007](decisions/0007-vendored-polish-languagetool-module.md) | Zaakceptowany | Budowany ze źródeł podzbiór polskiego LanguageTool 6.8 dla M4 |
| [ADR-0008](decisions/0008-hybrid-correction-policy.md) | Zaakceptowany | Hybrydowa polityka korekt i sugestii rules-first dla M5 |
| [ADR-0009](decisions/0009-specialist-prompt-benchmark.md) | Zaakceptowany | Żaden protokół promptu specjalistycznego nie uzyskał kwalifikacji |
| [ADR-0010](decisions/0010-inflection-candidate-generation.md) | Zaakceptowany | LanguageTool dostarcza skończony zbiór kandydatów fleksyjnych |
| [ADR-0011](decisions/0011-reject-bielik-1.5b-qlora.md) | Zaakceptowany | Bielik 1.5B QLoRA został odrzucony jako backend produkcyjny |
| [ADR-0012](decisions/0012-reject-constrained-qwen35-2b.md) | Zaakceptowany | Ograniczony Qwen3.5 2B został odrzucony jako backend produkcyjny |
| [ADR-0013](decisions/0013-reject-sentence-category-routing.md) | Zaakceptowany | Obecna macierz modeli routingu kategorii zdaniowych została odrzucona |
| [ADR-0014](decisions/0014-qualify-broader-polish-languagetool-rules.md) | Zaakceptowany | Cztery szersze polskie reguły zdaniowe LanguageTool uzyskały kwalifikację |
| [ADR-0015](decisions/0015-qualify-contextual-inflection-routing.md) | Zaakceptowany | Deterministyczny routing fleksji kontekstowej uzyskał kwalifikację jako źródło sugestii |
| [ADR-0016](decisions/0016-reject-qwen17-sentence-syntax-route.md) | Zaakceptowany | Ścieżka szczątkowej składni zdaniowej Qwen3 1.7B została odrzucona |
| [ADR-0017](decisions/0017-reviewable-residual-sentence-syntax-rules.md) | Zaakceptowany | Reguły szczątkowej składni zdaniowej pozostają sugestiami do przeglądu i nie są stosowane automatycznie |
| [ADR-0018](decisions/0018-runtime-composition-protocols.md) | Zaakceptowany | Protokoły kompozycji runtime'u używają wykonywanych operacji |
| [ADR-0019](decisions/0019-evaluation-namespace-compatibility.md) | Zaakceptowany | `polis.evaluation` zachowuje zgodność importów w całej linii 0.x |
| [ADR-0020](decisions/0020-runtime-first-product-charter.md) | Zaakceptowany | Karta produktu runtime-first nadaje nadrzędność runtime'owi offline |

[Granica protokołów analizatora i lokalnego backendu](protocols.md) opisuje
punkty rozdziału implementacji runtime'u zgodne z zaakceptowanym kontraktem
publicznego API.

[Inwentarz katalogu reguł](rule-catalog-inventory.md) zapisuje obecne
identyfikatory standardowych reguł runtime'u i ich dyspozycje polityki przed
rozstrzygnięciem własności katalogu.
