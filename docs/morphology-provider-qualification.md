# Kwalifikacja dostawcy morfologii offline

## Wynik

Morfeusz2 `1.99.15` ze słownikiem `pl.sgjp.sgjp-2026.06.01` uzyskał `PASS`
dla ograniczonego kontraktu issue #238. Znormalizowany digest dwóch osobnych
uruchomień był identyczny:
`7f55d0c4e0223653081493281be853eeda71d8077199a08e3536464a22c8eb11`.

Wynik pozwala rozpocząć osobne issue pierwszej reguły review-only. Nie dodaje
Morfeusz2 do runtime'u, nie zatwierdza szerokiej korekty fleksji, zgody ani
rekcji i nie nadaje żadnemu zachowaniu prawa do automatycznej korekty.

## Kandydaci

| Kandydat | Decyzja przed benchmarkiem | Uzasadnienie |
| --- | --- | --- |
| Morfeusz2 1.99.15 | wykonano | Lokalny analizator i generator morfologiczny bez modelu, Javy i sieci. |
| spaCy Polish | odrzucono | Dostępne polskie pipeline'y są modelami statystycznymi i nie zapewniają wymaganego kontraktu generowania. |
| Stanza | odrzucono | Pipeline neuronowy z modelami i PyTorch narusza granicę produktu oraz nie zapewnia generatora. |
| Hunspell | odrzucono | Interfejs pisowni i słownika nie zapewnia dokładnego kontraktu syntezy potrzebnego do fleksji, zgody i rekcji. |

## Tożsamość, licencja i platformy

Pakiet i dołączone dane fleksyjne SGJP/Polimorf są udostępniane na warunkach
BSD-2-Clause. Ochrona obejmuje dołączone dane form fleksyjnych, nie cały
słownik gramatyczny SGJP. Nota słownika ma SHA-256
`84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`.

PyPI 1.99.15 nie publikuje sdistu i publikuje trzy koła `cp310-abi3`:

| Platforma | Rozmiar | SHA-256 |
| --- | ---: | --- |
| macOS 11 universal2 | 15 772 667 B | `8ff0d3f9d2ab814b905afc471bc9b70415b3abb4ffcbf6ed3904735de88dbdac` |
| manylinux 2.28 x86_64 | 9 210 531 B | `089a83ab03a137a57e23d9d42028d80b8858d1a4de78f1db86a18ba504400a98` |
| Windows amd64 | 9 688 808 B | `1f20fefc457ea674640f87bd8de129b6310bb063ac21a68ea02b0f86bbd9aafe` |

Nie ma opublikowanego koła Linux arm64/musl ani udokumentowanej ścieżki
budowania ze źródeł. Zależność natywna pozostaje więc wyłącznie narzędziem
deweloperskim o ograniczonej macierzy platform. Na macOS arm64 instalacja koła
universal2 nie wymagała dodatkowego pakietu systemowego; nie wolno uogólniać
tego wyniku na nieobsługiwane platformy.

## Dane i progi

Fixture `tests/fixtures/v1/morphology_provider_qualification.json` jest nowym,
autorskim, syntetycznym i edytowalnym zbiorem CC0-1.0. Niezależny przegląd
objął wszystkie dziewięć przypadków związanych z kanonicznym SHA-256
`6a1dfca36682ee7e5524ef7a97fbd1438ebc11c124916ee6f2154741ff7ce68b`.
Zbiór nie pochodzi z holdoutu ani chronionych dowodów badawczych.

Przed pomiarem ustalono progi: precision, recall i correction accuracy równe
1.0, false-alarm rate równe 0.0, obowiązkową abstencję dla wieloznaczności i
nieznanego wejścia oraz pięć identycznych powtórzeń. Czasy i rozmiary są
informacyjne.

## Zarejestrowany pomiar

Drugi z dwóch zgodnych przebiegów na CPython 3.14.3 i macOS arm64 zapisał:

- 3 true positives, 0 false positives i 0 false negatives;
- precision 1.0, recall 1.0 i correction accuracy 1.0;
- 0 alarmów w 6 przypadkach negatywnych;
- startup 25 839 125 ns, p50 29 000 ns, p95 100 334 ns;
- przepustowość 29 160,87 przypadku/s;
- peak RSS 60 588 032 B;
- rozmiar zainstalowanej dystrybucji 40 725 689 B;
- pięć identycznych hashy wyników.

Pełny raport znajduje się w
`docs/morphology-provider-qualification-v1.json`. Nie zawiera analizowanych
tekstów, tylko identyfikatory przypadków i audytowalne wyniki.
Osobny rekord
`docs/morphology-provider-qualification-reproduction-v1.json` zachowuje kody
wyjścia, digesty i SHA-256 raportów z obu uruchomień; drugi raport jest
dokładnie plikiem zarejestrowanym w repozytorium.

## Reprodukcja

```console
uv run --locked --extra dev python scripts/benchmark_morphology_provider.py --dataset tests/fixtures/v1/morphology_provider_qualification.json --output build/morphology-provider-qualification.json
```

Polecenie można wykonać wielokrotnie; zakończony wynik atomowo zastępuje plik.
`PASS` i `FAIL` zwracają kod 0, `INCONCLUSIVE` kod 3, a niepoprawne dane kod 2
bez naruszania istniejącego raportu. `FAIL` i `INCONCLUSIVE` blokują dalszą
integrację.
