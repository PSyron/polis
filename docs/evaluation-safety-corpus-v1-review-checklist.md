# Lista kontrolna przeglądu korpusu bezpieczeństwa zdań v1

`polis_polish_correction_safety_corpus_v1` zawiera autorskie, syntetyczne
przypadki projektu na licencji CC0-1.0. Paweł Cyroń ukończył wymagany przegląd
właścicielski 2026-07-22 po poprawieniu i ponownym przeglądzie 49 odrzuconych
kandydatów. Korpus jest obecnie w stanie `frozen`; issue #114 nie uzyskuje
dostępu do jego holdoutu ani go nie ocenia.

Wykonaj przegląd wszystkich 240 przypadków, po jednym naraz, w kanonicznym JSON-ie
i wyrenderowanym polskim tekście. Oznacz przypadek jako zatwierdzony dopiero po
spełnieniu każdego z poniższych punktów:

- [x] **Poprawność:** wejście zawiera dokładnie deklarowany obiektywny problem
  albo jest rzeczywiście poprawne, gdy stanowi chroniony trudny przypadek
  negatywny.
- [x] **Kategoria:** warstwa, kategoria edycji, tagi i chronione zjawisko opisują
  zachowanie językowe, a nie preferencję stylistyczną.
- [x] **Minimalność:** edycja jest najmniejszą uzasadnioną zmianą i zachowuje
  znaczenie, ton, wielkość liter oraz nieobjęte zmianą formatowanie.
- [x] **Przesunięcia:** każdy półotwarty zakres `[start, end)` wybiera
  zadeklarowany oryginalny fragment z użyciem indeksowania punktów kodowych
  Unicode w Pythonie.
- [x] **Rekonstrukcja:** zastosowanie edycji od prawej do lewej daje dokładny
  `expected_output`, bez nakładania się zakresów ani niejednoznacznej kolejności
  wstawień.
- [x] **Obsługa nazw własnych:** nazwy osób i miejsc są poprawnie odmieniane
  albo chronione; każda kontrolowana forma powierzchniowa ma jeden dokładny
  zakres i kanoniczny identyfikator.
- [x] **Składnia i szyk wyrazów:** pozytywne przypadki składniowe są
  niegramatyczne, a nie jedynie nacechowane, natomiast chronione przypadki
  z nacechowanym szykiem pozostają bez zmian.
- [x] **Proweniencja:** zdanie jest nową, autorską i syntetyczną treścią projektu,
  nie zawiera prywatnego ani skopiowanego tekstu i zachowuje zapis proweniencji
  issue #114.
- [x] **Licencjonowanie:** przypadek może zostać wydany na licencji CC0-1.0 i nie
  zawiera fragmentu podmiotu trzeciego, materiału poufnego ani objętych
  ograniczeniami danych osobowych.
- [x] **Izolacja:** wejście, kombinacja encji, znormalizowany szablon i rodzina
  bliskich duplikatów są niezależne między splitami oraz od korpusu v3, danych
  do dostrajania, przykładów promptów i danych testowych E2E.

Po ukończeniu listy kontrolnej Paweł Cyroń może zmienić wyłącznie zapis
przeglądu danego przypadku z:

```json
{
  "status": "pending-human-review",
  "reviewer": null,
  "reviewed_at": null,
  "checklist_version": "safety-corpus-review-v1"
}
```

na `status: "human-reviewed"`, `reviewer: "Paweł Cyroń"` oraz rzeczywistą datę
przeglądu w formacie ISO. Odrzucony przypadek musi zostać poprawiony albo zastąpiony
i ponownie poddany przeglądowi; nie przenoś innego przypadku między częścią
deweloperską a holdoutem.

Holdout pozostaje w stanie `unfrozen-candidates`, dopóki każdy przypadek nie
przejdzie przeglądu, a wszystkie kontrole integralności i wycieku nie będą zielone.
Zamrożenie jest osobnym krokiem końcowym: zapisz właściciela, datę, zakres
`all-cases`, skrót kandydata i skrót zamrożony w osobnym manifeście
zatwierdzenia. Generator weryfikuje ten manifest, stosuje metadane przeglądu,
sprawdza każdy zastrzeżony zasób pod kątem wycieku, a dopiero potem zapisuje
zamrożone JSON i XML. Issue #114 nie może wytworzyć wyniku holdoutu. Po pierwszym
dostępie bramki jakości korekty wymagają nowej wersji korpusu.

## Zapis zamrożenia

- Recenzent właścicielski: Paweł Cyroń
- Data przeglądu: 2026-07-22
- Stan zamrożony: `frozen`
- SHA-256 kanonicznego JSON-u:
  `2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982`
- Wynik holdoutu wytworzony przez issue #114: nie
