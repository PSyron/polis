# Audyt prywatności

Granica produktu v1 jest lokalna: `Analyzer` nie wysyła analizowanego tekstu
przez sieć i nie uruchamia usługi pomocniczej. Domyślna konfiguracja nie pobiera
zasobów.

Przed wydaniem sprawdź:

- test instalacji i analizy w izolowanym środowisku offline;
- brak sekretów, prywatnych tekstów i dużych danych w śledzonych plikach;
- brak wrażliwego tekstu w komunikatach wyjątków Polis;
- zgodność zawartości wheel i sdist z zatwierdzoną listą;
- aktualność licencji zależności deweloperskich.

Ten audyt ocenia produkt v1. Historyczne dowody i materiały archiwalne pozostają
niezmienne i nie są ponownie uruchamiane ani przepisywane.
