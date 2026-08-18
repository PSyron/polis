# ADR-0030: Doprecyzowanie podstaw normatywnych i aplikowalności pokrycia reguł

- Status: Accepted
- Data: 2026-08-18
- Decydent: Paweł Cyroń
- Issue: #364
- Uzupełnia: ADR-0028 i ADR-0029; nie zmienia ich treści

## Kontekst

Review kontraktu pokrycia reguł wykazał trzy miejsca, w których sama proza
mogłaby pozwolić na różne interpretacje: brak jawnego katalogu podstaw
normatywnych i kandydackich, brak maszynowego statusu aplikowalności straty oraz
nieprecyzyjny zakres metryki dokładnego zakresu. Kontrakt v1 ma być wystarczająco
ścisły, aby kolejny autor v4 nie musiał podejmować tych decyzji ponownie.

## Decyzja

1. Katalog
   [`rule-coverage-normative-candidate-inventory-v1.json`](../../project/rule-coverage-normative-candidate-inventory-v1.json)
   jest częścią kontraktu. Rozdziela on normatywną Radę Języka Polskiego od
   kandydackiego wykazu reguł i publicznych artefaktów v3. Kandydackie źródło
   może dostarczyć przykładu lub hipotezy, ale nigdy samo nie ustanawia normy.
   Dla agreement, inflection i syntax kontrakt nie rości sobie normatywnej
   kompletności. Dla spelling i punctuation RJP jest podstawą tylko dla
   jawnie zmapowanych przypadków, nie dla kompletności kategorii.
2. Validator wymaga dokładnie pięciu map kategorii z katalogu i sprawdza, że
   każda uporządkowana tożsamość runtime'u ma dokładnie jeden mapowany wykaz
   kategorii. Brak, nadmiar, duplikat, reorder albo nieużywana mapa kończy
   walidację fail-closed. Validator porównuje URL-e i identyfikatory lokalnie;
   nie pobiera RJP ani żadnej innej sieci.
3. Każda wymagana stratum ma maszynowy status `required` albo `not-applicable`.
   Status `not-applicable` wymaga niepustego, specyficznego powodu i nie może
   zmieniać się w ciche pominięcie. Obecny kontrakt oznacza wszystkie siedem
   shape strata jako `required` dla każdej wspieranej kategorii; przyszłe
   odstępstwo musi zapisać status i powód w artefakcie oraz przejść osobną
   decyzję.
4. `exact-half-open-span-accuracy` ma zakres `determinate incorrect cases`.
   Licznik to predykcje, których `[start, end)` dokładnie odpowiadają
   niewykorzystanemu oczekiwanemu findingowi, a mianownik to wszystkie expected
   findings w tych samych determinate cases. Konflikty i abstencje pozostają
   poza mianownikiem zgodnie z polityką metryki; zero daje `null` i brak bramki.
5. Końcowy kanoniczny digest maszynowego kontraktu po tym doprecyzowaniu to
   `62ebb4892db4ac60100bb5595f53d50e60617d69c18deb21157b58ec95a3cc3f`.

## Konsekwencje

Kontrakt nie rozszerza runtime'u, nie dodaje zależności, nie uruchamia sieci i
nie kwalifikuje nowych rodzin. Zmiana podstawy normatywnej, mapy kategorii,
statusu aplikowalności albo definicji mianownika wymaga nowego ADR-u oraz
świeżego digestu kontraktu.
