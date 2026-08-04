# Architektura zbioru danych do fine-tuningu

Issue: #62

## Decyzja

Polis utrzymuje dane do fine-tuningu oddzielnie od correction corpus v3. Zbiór
danych został stworzony w projekcie, jest objęty licencją CC0-1.0,
deterministycznie generowany z małego rejestru sprawdzonych transformacji
językowych i zapisywany w repozytorium jako JSONL. Corpus v3 pozostaje
przeznaczony wyłącznie do ewaluacji.

Zbiór danych ma dwa rozłączne podziały:

- `train`: 1,200 rekordów, po 300 na kategorię;
- `validation`: 240 rekordów, po 60 na kategorię.

Kategorie to `inflection`, `syntax`, `punctuation` i `no_change`. Rekordy
fleksyjne używają protokołu skończonego zbioru kandydatów. Pozostałe kategorie
używają specjalistycznego protokołu poprawionego tekstu. Każdy rekord zachowuje
tekst źródłowy, ustrukturyzowany cel, wiadomości promptu, oficjalną serializację
Bielik ChatML, tożsamość transformacji, zakresy encji, proweniencję i stan
przeglądu transformacji.

## Bezpieczeństwo i izolacja

Generowanie i ładowanie działają fail-closed, gdy rekordy są zduplikowane,
wadliwe, niezbalansowane, nieprawidłowo licencjonowane, stworzone przez model
albo niebezpieczne. Przykłady pozytywne muszą wprowadzać minimalną zmianę
odpowiednią dla kategorii. Przykłady bez zmian muszą pozostać niezmienione i
łącznie obejmować poprawną fleksję, nazwy własne, nacechowany szyk wyrazów,
interpunkcję, liczby, adresy URL i cytaty.

Istniejąca bramka izolacji corpus-v3 odrzuca między oboma podziałami
ewaluacyjnymi nakładanie się tekstu dokładnego i znormalizowanego,
znormalizowanego szablonu oraz kombinacji encji. Train i validation używają
dodatkowo rozłącznych szablonów transformacji i tożsamości encji.

## Formatowanie czatu

Wiadomości używają wybranych kontraktów specjalistycznych i są serializowane za
pomocą oficjalnego szablonu Bielik 1.5B v3 ChatML:

```text
<s><|im_start|>system
...<|im_end|>
<|im_start|>user
...<|im_end|>
<|im_start|>assistant
...<|im_end|>
```

Zapisany ciąg ChatML jest artefaktem audytowym. Integracje treningowe powinny
preferować ustrukturyzowane pole `messages` i implementację tokenizera
`apply_chat_template`.

Implementacja referencyjna i kontrakt tokenizera:

- [karta modelu Bielik-1.5B-v3.0-Instruct](https://huggingface.co/speakleash/Bielik-1.5B-v3.0-Instruct)
- [oficjalna konfiguracja tokenizera](https://huggingface.co/speakleash/Bielik-1.5B-v3.0-Instruct/blob/main/tokenizer_config.json)

## Odrzucone alternatywy

- Ponowne użycie corpus v3 unieważniłoby ewaluację i naruszyłoby jego politykę
  użycia do treningu.
- Traktowanie wyniku modelu jako gold uczyniłoby cel niesprawdzonym i
  cyklicznym.
- Przechowywanie wyłącznie wyrenderowanego ChatML odrzuciłoby ustrukturyzowany
  kontrakt promptu i uczyniłoby walidację kruchą.
