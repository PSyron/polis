# Kategorie analizatora v1

Ta strona jest kanonicznym opisem kategorii, które faktycznie emitują
deterministyczne reguły domyślnego `Analyzer` w v1. Pełny, wersjonowany spis
źródeł i ich dokładnych granic zawierają [reguły](rules.md). Ani liczba
kategorii, ani liczba źródeł nie oznacza kompletnego pokrycia języka polskiego:
każda reguła działa tylko dla jawnie opisanych, lokalnych wzorców i abstenuje,
gdy brak pewności.

## Kategorie obsługiwane przez analizatory v1

| Wartość `Category` | Znaczenie i przykład | Granice i morfologia | Status korekty |
| --- | --- | --- | --- |
| `inflection` | Ograniczone błędy odmiany i rekcji, np. `Potrzebuję pomoc.` → `Potrzebuję pomocy.` | Nie jest to pełna kontrola fleksji. Część zamkniętych wzorców wymaga lokalnego, zakwalifikowanego Morfeusz2; brak, dryft lub niejednoznaczność danych oznacza abstencję. | Źródło może być `review-only`; sama kategoria nie kwalifikuje poprawki do automatyzacji. |
| `agreement` | Ograniczona zgoda osoby, liczby, rodzaju albo przypadka, np. `Te zdanie` → `To zdanie`. | Nie obejmuje ogólnej zgody całego zdania. Reguły grup nominalnych i podmiotu z czasownikiem mogą wymagać Morfeusz2 i wtedy działają fail-closed. | Źródło może być `review-only`; sama kategoria nie kwalifikuje poprawki do automatyzacji. |
| `syntax` | Wybrane lokalne konstrukcje składniowe, np. `Jeśli pada zostaję w domu.` → `Jeśli pada, zostaję w domu.` | Nie interpretuje znaczenia, intencji ani dyskursu. Każdy wzorzec ma własne warunki segmentacji i abstynencji; część korzysta z pojedynczego zdania. | Źródło może być `review-only`; sama kategoria nie kwalifikuje poprawki do automatyzacji. |
| `spelling` | Zamknięte błędy pisowni, np. `zeby` → `żeby`. | Nie jest słownikiem wszystkich literówek ani nazw własnych. Reguły zachowują granice, wielkość liter i odpuszczają między innymi w nieobsługiwanym kontekście cytatu lub kodu. | Źródło może być `review-only`; sama kategoria nie kwalifikuje poprawki do automatyzacji. |
| `punctuation` | Wybrane lokalne problemy interpunkcyjne, np. `Witaj,świecie.` → `Witaj, świecie.` | Nie stanowi pełnej korekty interpunkcji. Dotyczy tylko konkretnych separatorów i konstrukcji opisanych w spisie reguł. | Źródło może być `review-only`; sama kategoria nie kwalifikuje poprawki do automatyzacji. |

Kategoria nie nadaje poprawce prawa do automatycznego zastosowania. Status
`review-only` albo kwalifikacja do automatyzacji zależą od dokładnego klucza
źródła, kategorii, operacji, wersji zachowania i wersji polityki. Zawsze
sprawdzaj go w wyniku oraz w [opisie reguł](rules.md); `apply_suggestions()`
pozostaje jawną decyzją wywołującego.

## Zgodnościowe `style`

`Category.STYLE` oraz tekstowa wartość `style` pozostają w enumie i schemacie
JSON dla zgodności danych. Nie są szóstą obsługiwaną kategorią analizatora v1:
domyślny `Analyzer` nie rejestruje źródła o tej kategorii i nie emituje dla niej
znalezisk. Filtr `categories={"style"}` lub `categories = ["style"]` jest więc
poprawny składniowo, ale może prawidłowo zwrócić pusty wynik.

Polis v1 nie poprawia tonu, dyskursu ani stylu i nie tworzy dla nich automatycznej
korekty. Wartość zgodnościowa nie jest obietnicą przyszłej funkcji.

## Filtrowanie i konfiguracja

`AnalysisOptions(categories=...)`, `[analysis].categories` oraz powtarzalna
flaga CLI `--category` przyjmują wartości `Category`. Przykład poniżej wybiera
pięć wspieranych kategorii v1; pominięcie `categories` wybiera wszystkie
kategorie zarejestrowane przez analizator.

```toml
[analysis]
categories = ["inflection", "agreement", "syntax", "spelling", "punctuation"]
minimum_confidence = 0.8
```

`minimum_confidence` jest wyłącznie filtrem wyniku. Nie zastępuje lokalnego
uzasadnienia reguły, wymagań morfologii ani polityki `review-only`.
