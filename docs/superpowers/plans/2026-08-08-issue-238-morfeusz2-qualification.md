# Kwalifikacja Morfeusz2 — plan implementacji

> **Dla agentów wykonawczych:** realizuj kroki test-first, zachowaj jeden
> skupiony commit i nie przechodź do integracji runtime'u.

**Cel:** Dostarczyć reprodukowalną, offline'ową kwalifikację Morfeusz2 dla
issue #238 z nowym przejrzanym fixture, raportem i dowodem dwóch zgodnych
uruchomień.

**Architektura:** Ścisły kontrakt i parser danych oddziela niezaufane JSON-y od
wewnętrznych niemutowalnych typów. Mały adapter dynamicznie importuje
Morfeusz2 tylko w benchmarku. Orkiestrator mierzy wyniki i buduje raport;
entrypoint obsługuje kody wyjścia i atomowy zapis. Nic nie trafia do
`src/polis`.

## Zadanie 1: kontrakt i RED danych

**Pliki:**
- `tests/fixtures/v1/morphology_provider_qualification.json`
- `tests/fixtures/v1/morphology_provider_qualification.manifest.json`
- `tests/test_morphology_provider_dataset.py`
- `scripts/morphology_provider_contract.py`

- [ ] Dodaj testy odrzucenia nieznanych pól, duplikatów, złego hasha i
  niepełnego przeglądu.
- [ ] Potwierdź RED z powodu brakującego modułu.
- [ ] Zaimplementuj ścisły parser do niemutowalnych typów oraz kanoniczny hash.
- [ ] Potwierdź GREEN dla dziewięciu prerejestrowanych przypadków.

## Zadanie 2: adapter i fail-closed

**Pliki:**
- `tests/test_morphology_provider_morfeusz.py`
- `scripts/morphology_provider_morfeusz.py`

- [ ] Testami zapisz deduplikację identycznych rekordów, dokładne filtry
  lemmatu/POS/cech, `ign` i niejednoznaczność.
- [ ] Potwierdź RED.
- [ ] Zaimplementuj mały adapter bez importu Morfeusz2 przy imporcie modułu.
- [ ] Potwierdź GREEN dla pozytywów i wszystkich abstencji.

## Zadanie 3: pomiary, raport i CLI

**Pliki:**
- `tests/test_morphology_provider_report.py`
- `tests/test_benchmark_morphology_provider_cli.py`
- `scripts/morphology_provider_benchmark.py`
- `scripts/benchmark_morphology_provider.py`

- [ ] Testami zapisz metryki, pięć stabilnych hashy, zakres normalizowanego
  digestu, brak tekstu w raporcie i atomowość wyjścia.
- [ ] Potwierdź RED.
- [ ] Zaimplementuj pomiary startu, czasu przypadków, przepustowości, RSS i
  rozmiaru dystrybucji oraz prerejestrowane bramki.
- [ ] Zaimplementuj kody 0/2/3 i kanoniczny zapis JSON.
- [ ] Potwierdź GREEN.

## Zadanie 4: zależność deweloperska i granice dystrybucji

**Pliki:**
- `pyproject.toml`
- `uv.lock`
- `docs/development/dependency-licenses.md`
- `tests/test_morphology_provider_packaging.py`
- `tests/test_distribution_artifacts.py`

- [ ] Dodaj testy, że zależności produkcyjne pozostają puste, a wheel/sdist nie
  zawierają Morfeusz2, benchmarku, fixture ani raportu.
- [ ] Przypnij `morfeusz2==1.99.15` wyłącznie w `dev` i odśwież lockfile.
- [ ] Zapisz oddzielnie licencję programu i dołączonych danych oraz ograniczenia
  platformowe; nie rozszerzaj BSD na cały SGJP.
- [ ] Zbuduj i sprawdź obie dystrybucje.

## Zadanie 5: przegląd danych i realny raport

**Pliki:**
- `docs/morphology-provider-qualification.md`
- `docs/morphology-provider-qualification-v1.json`
- `docs/project/documentation-migration-inventory.json`

- [ ] Zleć niezależny przegląd wszystkich przypadków i ich licencji; dopiero po
  akceptacji ustaw status manifestu na reviewed.
- [ ] Uruchom dokładne polecenie z #238 dwa razy, zachowując oba raporty jako
  dowód, i porównaj normalized digest.
- [ ] Zapisz drugi kanoniczny wynik w dokumentacji oraz konsekwencję PASS,
  FAIL albo INCONCLUSIVE bez zmiany progów.
- [ ] Sklasyfikuj nowe utrzymywane dokumenty i historyczne plan/spec w
  inwentarzu.

## Zadanie 6: bramki, review i publikacja

- [ ] Uruchom focused pytest, `ruff check`, `ruff format --check`, `mypy`, pełny
  pytest bez `research`, build/install oraz ochronę historycznych ścieżek.
- [ ] Potwierdź ręcznie rzeczywisty interfejs CLI i brak tekstów wejściowych w
  raporcie.
- [ ] Utwórz jeden commit `#238`, uruchom niezależne review i runtime audit na
  dokładnym SHA; napraw wyłącznie blokery i powtórz bramki po nowym SHA.
- [ ] Wypchnij gałąź, otwórz draft PR i zaczekaj na zielone CI.
