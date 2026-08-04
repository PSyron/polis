# Lista kontrolna przeglądu polskiego korpusu korekt v3

Korpus v3 zawiera kandydatów CC0-1.0 przygotowanych przez model. Każdy przypadek
zaczyna ze stanem `pending-human-review`; nie jest ani danymi wzorcowymi, ani
zamrożonym holdoutem. Wyłącznie Paweł Cyroń może zapisać zatwierdzenie wymagane
przez politykę przeglądu schematu v3.

Wykonuj przegląd po jednym przypadku naraz, zarówno w kanonicznym JSON-ie, jak
i w wyrenderowanym polskim tekście. Zatwierdź przypadek dopiero po spełnieniu
każdego z poniższych punktów:

- [ ] **Poprawność:** wejście zawiera dokładnie deklarowany problem gramatyczny
  lub interpunkcyjny albo jest rzeczywiście poprawne, gdy stanowi trudny
  przypadek negatywny.
- [ ] **Kategoria:** warstwa, kategoria znaleziska, tagi i chronione zjawisko
  opisują zachowanie językowe, a nie preferencję stylistyczną.
- [ ] **Minimalność:** każda proponowana edycja jest najmniejszą uzasadnioną
  zmianą i zachowuje znaczenie, ton, wielkość liter oraz nieobjęte zmianą
  formatowanie.
- [ ] **Przesunięcia:** każdy zakres `[start, end)` wybiera zadeklarowany fragment
  `original` z użyciem indeksowania punktów kodowych Unicode w Pythonie.
- [ ] **Rekonstrukcja:** zastosowanie wszystkich edycji od prawej do lewej daje
  dokładny `expected_output`, bez nakładania się zakresów ani niejednoznacznej
  kolejności wstawień.
- [ ] **Obsługa nazw własnych:** imiona, nazwiska, nazwy miejsc i formy
  nieodmienne są poprawnie odmieniane albo chronione w swoim kontekście.
- [ ] **Składnia i szyk wyrazów:** przypadek błędny jest niegramatyczny, a nie
  jedynie nacechowany; chroniony przypadek z nacechowanym szykiem pozostaje bez
  zmian.
- [ ] **Proweniencja:** przypadek jest syntetyczny, nie zawiera prywatnego ani
  skopiowanego tekstu i zachowuje pełny zapis proweniencji kandydata.
- [ ] **Licencjonowanie:** kandydat może zostać wydany jako CC0-1.0 i nie zawiera
  fragmentu podmiotu trzeciego ani objętych ograniczeniami danych osobowych.
- [ ] **Izolacja:** wejście, kanoniczna kombinacja encji i znormalizowany szablon
  nie występują nigdzie indziej w korpusie, przykładach promptów ani żadnym
  zasobie treningowym; zakresy encji wybierają każdą dokładną formę
  powierzchniową z kontrolowanego katalogu, mapują warianty fleksyjne na jedną
  tożsamość i odtwarzają znormalizowany szablon. Krótkie szablony siostrzane
  różniące się tylko jednym tokenem należą do jednej rodziny i nie mogą
  przekraczać granic rekordów ani podziałów.

Po ukończeniu listy kontrolnej Paweł Cyroń może zmienić wyłącznie zapis
przeglądu danego przypadku z:

```json
{
  "status": "pending-human-review",
  "reviewer": null,
  "reviewed_at": null,
  "checklist_version": "corpus-v3-review-v1"
}
```

na `status: "human-reviewed"`, `reviewer: "Paweł Cyroń"` oraz datę przeglądu
w formacie ISO. Odrzucony kandydat musi zostać poprawiony i ponownie poddany
przeglądowi albo usunięty i zastąpiony bez przenoszenia innego przypadku między
częścią deweloperską a holdoutem.

Holdout pozostaje w stanie `unfrozen-candidates`, dopóki wszystkie 240 przypadków
nie przejdą przeglądu, a wszystkie kontrole integralności nie będą zielone.
Zamrożenie jest osobną, jawną zmianą: ustaw `holdout_state` na `frozen`, ponownie
wygeneruj równoważny XML, zapisz SHA-256 JSON-u i uruchom pełny szybki zestaw
testów. Po zamrożeniu zmiany wymagają nowej wersji korpusu; nie naprawiaj
holdoutu użytego w benchmarku w miejscu.
