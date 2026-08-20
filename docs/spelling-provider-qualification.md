# Kwalifikacja offline providerów kandydatów pisowni

Issue #388 został wykonany jako badanie bez zmian w runtime Polis. Wynik
kwalifikacji brzmi `NO_PROVIDER_QUALIFIED`: żaden provider ani słownik nie
został dodany do zależności, koła, sdistu, publicznego API ani polityki
automatycznej korekty.

## Protokół

Badanie używa projektu autorskiego, syntetycznego korpusu
`tests/fixtures/v1/spelling_provider_qualification.json` na licencji CC0-1.0.
Manifest przypina kanoniczny digest, kolejność 25 stabilnych przypadków,
proweniencję i brak nakładania z chronionymi dowodami. Każdy przypadek ma
oryginalny tekst, dokładny zakres `[start, end)` i oczekiwane kandydaty albo
jawną abstencję. Raport nie zapisuje analizowanego tekstu.

Guard przed providerem odrzuca URL-e, e-maile, literały, akronimy, numery,
mieszany język i tokeny techniczne przed wywołaniem biblioteki; test z
providerem rejestrującym potwierdza zero wywołań dla dziewięciu takich
przypadków. Oba providery uruchomiono na tym samym
tekście, sprzęcie, Pythonie 3.12.13,
limicie pięciu kandydatów, maksymalnym dystansie edycji 2 i pięciu
powtórzeniach. Zmierzono osobno detekcję literówki, recall kandydata, top-1
exactness, alarmy na negatywach, abstencję dla niejednoznacznych diakrytyk,
niejednoznaczne wielokrotne kandydatury, guardy graniczne, czas startu, czas
zapytań, pamięć RSS, rozmiar pakietu i rozmiar danych. Protokół nie zawiera
progów ustalonych przed baseline'em.

## Wyniki baseline'u

| Provider i dane | Recall | Top-1 | False alarms | Start | P95 / throughput (16 tokenów) | RSS | Rozmiar zależności | Decyzja |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `spylls==0.1.7` + LibreOffice `pl_PL` | 1.000 | 1.000 | 1/6 | 1.014 s | 1.810 s / 1.19 q/s | 351.4 MiB | 1.44 MiB | odrzucony: licencja nierozstrzygnięta |
| `symspellpy==6.10.0` + K7TRY | 0.700 | 0.700 | 4/6 | 1.065 s | 0.071 ms / 36,524 q/s | 273.3 MiB | 2.49 MiB | odrzucony: dane GPL-3.0 i jakość baseline'u |

Wyniki są obserwacją tego przypiętego korpusu, a nie obietnicą jakości
produkcyjnej. `spylls` poprawnie znalazł wszystkie dziesięć oczekiwanych
kandydatów i nie alarmował na pięciu z sześciu naturalnojęzykowych negatywów;
zgłosił wieloznaczny `rzd` jako kandydatury, co potwierdza potrzebę abstencji
na tym typie przypadku. Jednak
źródła opisują licencję pakietu niespójnie (MPL-2.0 upstream, UNKNOWN/MIT w
metadanych wheel, brak pola licencji w PyPI), a polski słownik deklaruje rodzinę
GPL/LGPL/MPL/Apache/CC ShareAlike. `symspellpy` ma licencję MIT, lecz nie
zawiera polskich danych; użyta lista K7TRY jest na poziomie repozytorium
GPL-3.0, a baseline pomylił cztery z sześciu negatywów.

## Przypięte źródła

- `spylls-0.1.7-py2.py3-none-any.whl`, SHA-256
  `0c7fa4b66615f390bd12fd37939b85934c012309fd3cce8584844c54270b7776`.
- LibreOffice dictionaries revision
  `f2ff99058268502bdcf4cad25c1ca2935ad8aa7d`, pliki `pl_PL.aff`, `pl_PL.dic`
  i `README_en.txt`, z digestami zapisanymi w raporcie JSON.
- `symspellpy-6.10.0-py3-none-any.whl`, SHA-256
  `e31707f6d6e06b89973588c02c0c7941c9ca1e3144859a8e2e46d8b815dda75e`.
- Źródłowa lista K7TRY `Polish Word Frequency List.txt` z rewizji
  `204bc67cca6daee769137ec95169afb5ccb2b565`, SHA-256
  `956b2071998cbe72edb8eac070aa792cf00b171faddf7403116d8d9b8f47e783`.
  Została deterministycznie przekształcona do dwóch kolumn SymSpell przez
  pominięcie wierszy usuniętych i niealfabetycznych, normalizację do lower
  case oraz zapis `word max(totalcount, 1)`.

Dokładne identity, digesty, metryki, powtórzenia i decyzja znajdują się w
`docs/spelling-provider-qualification-v1.json`. Pole
`runtime_network_used` ma wartość `false`; pobieranie danych dotyczyło tylko
jednorazowego badania poza runtime.

## Odtworzenie

Runner `scripts/spelling_provider_qualification.py` przyjmuje zewnętrzne,
tymczasowe ścieżki pakietu i danych oraz wymaga oczekiwanych wersji i digestów.
Przed uruchomieniem można pobrać przypięte zewnętrzne artefakty poleceniami z
`docs/spelling-provider-qualification-reproduction-v1.json` i zweryfikować je
jednym `shasum`; ta faza jest jedynym miejscem, w którym badanie dopuszcza
sieć. Reprodukcja używa potem lokalnych wheelów przez
`uv run --offline --no-index`, a runner dodatkowo blokuje wszystkie ścieżki
gniazd sieciowych podczas importu i pomiaru. Zapisuje raport wyłącznie do
podanego katalogu tymczasowego i tylko wtedy, gdy wszystkie powtórzenia są
stabilne. Niestabilny przebieg kończy się jako `qualification inconclusive` i
nie zapisuje raportu; standardowe wejścia do tworzenia procesów są również
blokowane podczas kwalifikacji. Nie wolno dodawać tych
pakietów do `pyproject.toml` ani `uv.lock` bez osobnej decyzji po kwalifikacji.

Powtórzenia muszą zachować identyczne hashe wyników przypadków. Zmiana wersji,
jakiegokolwiek digestu danych lub digestu artefaktu kończy przebieg jako
`qualification inconclusive`.
