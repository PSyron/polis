# Bramki jakości korekty hybrydowej

ADR-0008 oddziela automatyczne poprawki deterministyczne od sugestii modelu
podlegających przeglądowi. Każda ścieżka jest mierzona niezależnie względem
dokładnych edycji tekstu oryginalnego na zamrożonym holdoucie. Płynność,
poprawność JSON, szybkość, pewność modelu ani silny wynik zbiorczy nie mogą
zrekompensować niezaliczonej bramki właściwej dla ścieżki.

## Wspólne bramki bezpieczeństwa

- Chronione trudne przypadki negatywne obejmują poprawną fleksję, imiona i
  nazwiska, nacechowany, ale gramatyczny szyk, liczby, adresy URL, cytaty i
  formatowanie nieobjęte zmianą.
- Po jawnym przygotowaniu artefaktów cały analizowany tekst pozostaje lokalny.
  Runtime modelu wykonuje bezpośrednią inferencję lokalną albo używa wyłącznie
  numerycznego endpointu loopback.
- Odpowiedzi referencyjne (gold) nie mogą być osadzane w wykonywanym benchmarku,
  przykładach promptów, rekordach treningowych ani gałęziach wyszukiwania
  właściwych dla korpusu.
- Recall, F1, trafność kompletnego wyjścia, opóźnienie, przepustowość, pamięć i
  liczba wywołań na przypadek są raportowane dla każdej kategorii, nawet gdy nie
  stanowią bramek wydania.

Niezaliczenie wspólnej bramki bezpieczeństwa lub prywatności odrzuca dokładną
testowaną konfigurację źródła, operacji, runtime'u i artefaktu.

## Bramki automatycznej korekty

Uprawnienie do automatycznego zastosowania jest oceniane dla każdej kombinacji
deterministycznego źródła, kategorii, operacji, wersji zachowania i wersji
polityki źródeł:

- precision dokładnej edycji: **1.00**;
- trafność korekty: **1.00**;
- chronione trudne przypadki negatywne: **0** zmienionych przypadków.

Zaliczenie tych metryk samo w sobie nie zmienia polityki runtime'u. Dokładne
zachowanie musi również zostać dodane do wersjonowanej polityki źródeł
automatycznej korekty. Aktywna polityka `1.2` wymusza pełny niezmienny klucz
`(source, category, operation, behavior_version, source_policy_version)` i
sprawdza pewność dopiero po dopasowaniu tego klucza. Pochodzenie reguły,
tożsamość silnika, nazwa źródła ani sama pewność nigdy nie nadają uprawnienia.
Zmiana wersji zachowania wymaga nowych bezpośrednich dowodów i osobnego,
dokładnego wpisu polityki; znaleziska modelu pozostają do przeglądu niezależnie
od dowodów lub pewności.

## Bramki sugestii

Bramki sugestii i modelu są dowodami na potrzeby promowania opcjonalnego
rozszerzenia. Nie są bramkami wydania produktu, a opcjonalne badania nad modelem
nigdy nie blokują wydania runtime'u. Ścieżka wydania runtime'u nie wymaga
modelu, procesu Java, usługi sieciowej, korpusu badawczego ani zużytego holdoutu.

Edycje zależne od modelu pozostają wyłącznie sugestiami w pierwszym wydaniu
hybrydowym, w tym wybory ze skończonego zbioru kandydatów i propozycje
zaakceptowane przez weryfikator:

- precision dokładnej edycji: co najmniej **0.90**;
- prawidłowe wyniki ustrukturyzowane: **100%**;
- chronione trudne przypadki negatywne: **0** znalezisk.

Recall jest raportowany dla `inflection`, `syntax` i `punctuation` oraz kieruje
późniejszymi usprawnieniami. Niski recall jest dopuszczalny w wydaniu
zachowawczym; nigdy nie zezwala na obniżenie progu precision, poprawności lub
chronionych przypadków negatywnych.

## Dowody wyboru

Dowody zapisują wersje promptu i schematu, dokładną rewizję i kwantyzację modelu,
wersję runtime'u, klasę sprzętu, system operacyjny, skróty korpusu i podziału,
zajętą pamięć, opóźnienie zimne i rozgrzane, przepustowość, liczbę wywołań modelu
oraz weryfikację offline. Wyniki zbioru deweloperskiego i holdoutu pozostają
oddzielone.

Pierwotny dwuregulowy podzbiór LanguageTool i każdy model z ADR-0005 poprzedzają
te bramki M5. ADR-0014 zakwalifikował później cztery dokładne identyfikatory
reguł LanguageTool, a historyczna wersja polityki źródeł `1.1` zapisuje powstałą
listę pięciu dozwolonych identyfikatorów. Aktywna polityka `1.2` zachowuje tę
kwalifikację wyłącznie dla zachowania `check.allowlisted_comma`
`pl-6.8-five-rule-comma/1.0`; nie poszerza wsparcia LanguageTool. Adapter modelu
może przejść dalej dopiero po zaliczeniu odpowiednich bramek przez jego dokładny
prompt, runtime, model i polityki źródeł.

## Korpus ponownej kwalifikacji bezpieczeństwa zdań

Issue #114 wprowadza `polis_polish_correction_safety_corpus_v1`, ponieważ
jednorazowy holdout corpus-v3 został zużyty przez nieudaną bramkę i nie może
zostać naprawiony, ponownie uruchomiony ani wylosowany na nowo do ponownej
kwalifikacji. Nowy 240-przypadkowy korpus na licencji CC0-1.0 jest niezależny od
corpus-v3, zasobów fine-tuningu, przykładów promptów i danych E2E. Paweł Cyroń
sprawdził wszystkie przypadki 2026-07-22, a korpus ma stan `frozen` i kanoniczny
skrót JSON SHA-256
`2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982`.

Żadna bramka jakości nie może wybrać jego 160 przypadków holdoutowych przed
zamrożeniem, a żadna ścieżka deweloperska nie może załadować ich odpowiedzi
referencyjnych (gold). Powyższy skrót zamrożonego zbioru zapisano przed pierwszym
dostępem. Samo issue #114 nie uruchamia bramki i nie tworzy wyniku holdoutu; za
jednorazowe uruchomienie odpowiada kolejne issue. Ten korpus nie zastępuje
corpus-v3 ani nie nakłada się na szersze prace nad korpusem w #85.

Issue #115 zakwalifikowało 80-przypadkową fazę deweloperską zainstalowanego
pakietu 2026-07-23. Automatyczne edycje uzyskały `10 TP / 0 FP`, precision `1.00`
i trafność korekty `1.00`; edycje do przeglądu uzyskały `18 TP / 0 FP`,
precision `1.00` i trafność korekty `1.00`. Poprawność ustrukturyzowanego wyniku
wyniosła `1.00`, a obie liczby chronionych przypadków negatywnych były zerowe.
Dokładne skróty raportu deweloperskiego i artefaktu zachowano w pliku
`frozen_gate.json` eksperymentu. Następnie 160-przypadkowy holdout został
autoryzowany, zarezerwowany i uruchomiony dokładnie raz 2026-07-23. Automatyczne
edycje uzyskały `11 TP / 0 FP`, precision `1.00` i trafność korekty `1.00`.
Edycje do przeglądu uzyskały `0 TP / 2 FP`, precision `0.00` i trafność korekty
`1.00`; dlatego wymagane precision kanału do przeglądu `0.90` nie zostało
osiągnięte. Poprawność strukturalna pozostała na poziomie `1.00`, liczby
chronionych przypadków pozostały zerowe, a wszystkie bramki prywatności i
wydajności zostały zaliczone. Zachowany znacznik sprawia, że holdout jest trwale
zużyty, ogólna decyzja brzmi „niezakwalifikowane”, a #76 pozostaje otwarte.

Issue #119 tworzy `polis_polish_correction_safety_corpus_v2` jako kolejny
niezależny zasób kwalifikacyjny. Jego 240 przypadków na licencji CC0-1.0 jest
zamrożonych po pełnym przeglądzie przez uprawnioną rolę
`Polis architecture owner`. Kanoniczny skrót JSON SHA-256 zamrożonego korpusu to
`53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
Korpus jest mechanicznie odizolowany od obu wcześniejszych korpusów oraz
wszystkich zarezerwowanych zasobów promptów, treningowych i E2E. Jego utworzenie
i przegląd nie dają wyniku jakości zbioru deweloperskiego ani holdoutu i nie
ujawniają odpowiedzi referencyjnych (gold) holdoutu.

Zamrożenie v2 samo w sobie nie kwalifikuje #76. Osobne kolejne issue musi
najpierw zaliczyć fazę deweloperską, a następnie może jednokrotnie zarezerwować
nowy holdout przy niezmienionych bramkach automatycznych i kanału do przeglądu.
Ta ścieżka jest oddzielona od corpus-v4 w #85 oraz bramki większościowego pokrycia
zainstalowanego pakietu w #90.

Issue #146 odpowiada za to jednorazowe uruchomienie ograniczone do zdań. Jest to
opcjonalne badanie. Nie blokuje wydania runtime'u i zachowuje każdą powyższą
bramkę bez zmian. Zaakceptowana autonomiczna autoryzacja wymagała kontroli
wstępnej, kwalifikującej fazy deweloperskiej, weryfikacji zamrożenia i
niezależnego przeglądu. 80 przypadków deweloperskich uruchomiono w dwóch stabilnych
powtórzeniach, ale nie zostały zakwalifikowane: automatyczne precision i trafność
korekty wyniosły `1.00`, automatyczny recall `0.3333333333333333`, a kanał do
przeglądu nie zaproponował żadnych edycji, więc nie wykazał wymaganej precyzji.
Poprawność strukturalna wyniosła `1.00`, a obie liczby chronionych
przypadków negatywnych były zerowe. Skrót SHA-256 raportu zbiorczego to
`7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141`.
Nie istnieje zamrożona bramka, znacznik pozostaje nieobecny, a holdout nie został
zarezerwowany, zmaterializowany ani uruchomiony. Ponowne uruchomienie ani
dostrajanie nie jest dozwolone. #76 pozostaje otwarte, a `Task 6` jest
zabronione. Eksperyment nie kwalifikuje modelu produkcyjnego ani zachowania dla
akapitów.
