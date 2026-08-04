# Kontrakty korekty specjalistycznej

Ten dokument definiuje wersjonowane kontrakty korekty przez model
specjalistyczny z issue #59. ADR-0009 nie zakwalifikował żadnego testowanego
modelu, dlatego te interfejsy pozostają eksperymentalne i zwracają wyłącznie
sugestie. Nie zezwalają na ich automatyczne stosowanie.

## Wspólne ograniczenia

- Tekst wejściowy i dane kandydatów są serializowane jako jeden kanoniczny
  obiekt JSON wewnątrz `<INPUT_JSON_START>` i `</INPUT_JSON_END>`, a nie łączone
  z instrukcjami. Dosłowne nawiasy ostre w danych są kodowane znakami ucieczki
  Unicode, aby tekst użytkownika nie mógł zakończyć koperty.
- Prompty używają osobnych wiadomości systemowej i użytkownika.
- Żądania promptu zawierają jawne ograniczenia operacyjne:
  - maksymalny rozmiar tekstu wejściowego: `8192` znaków;
  - surowa odpowiedź z poprawionym tekstem: `16384` znaki;
  - surowa odpowiedź wyboru kandydata: `512` znaków;
  - surowa odpowiedź weryfikatora: `128` znaków;
  - wartość poprawionego lub proponowanego tekstu: `8192` znaków.
- Schematy odpowiedzi są wersjonowane i rygorystycznie walidowane.
- Nie jest akceptowane żadne wyjście modelu, które nie jest prawidłowym JSON-em
  zgodnym z żądanym schematem.
- Prywatny tekst nie trafia do diagnostyki wyjątków.
- Runtime stosuje oficjalny szablon rozmowy swojego modelu do `messages`;
  kontrakt nie spłaszcza ról ani nie wskazuje runtime'u lub modelu.

## Operacja poprawionego tekstu (`specialist-corrected-text`)

`build_specialist_corrected_text_prompt_request(text, focus)` buduje prompt o
następujących właściwościach:

- identyfikator protokołu: `specialist-corrected-text`;
- wersja protokołu: `1.0`;
- zakres systemowy: dokładnie jeden z `inflection`, `syntax`, `punctuation`;
- wersja schematu odpowiedzi: `1`;
- schemat odpowiedzi:

```json
{"required":["corrected_text"],"type":"object","properties":{"corrected_text":{"type":"string"}},"additionalProperties":false}
```

Tryby niepowodzenia:

- Brakujące lub dodatkowe pola najwyższego poziomu.
- Zbyt wiele zakresów przepisania.
- Brak wspólnych tokenów z tekstem źródłowym.
- Niezgodność typu odpowiedzi.
- Przekroczenie długości odpowiedzi surowej lub poprawionego tekstu.
- Przepisanie nakładające się na chronione zakresy źródła podane przez
  wywołującego.
- Zmiana słowa przy zakresie interpunkcyjnym albo zmiana elementu niebędącego
  słowem przy zakresie fleksyjnym.

`validate_corrected_text_response(raw, source_text=..., focus=...)` wymaga tego
samego jawnego zakresu; wywołujący nie mogą walidować odpowiedzi bez określonej
kategorii specjalistycznej.

## Operacja wyboru kandydata fleksyjnego (`specialist-candidate-selection`)

`build_inflection_candidate_prompt_request(text, candidates)` oczekuje jednego
z dwóch wyników:

- `{"unchanged": true}`
- `{"candidate_id": "..."}`

`candidate_id` musi zostać dostarczony przez wywołującego i należeć do podanej
listy kandydatów.

Wszyscy dostarczeni kandydaci muszą opisywać ten sam dodatni zakres źródłowy.
Identyfikatory i formy są unikatowe, wartości lematu i cech są typowane oraz —
jeśli występują — niepuste, cechy są unikatowe, offsety odnoszą się do
oryginalnego łańcucha Pythona, a oryginalna forma powierzchniowa jest dołączona.
Formy i morfologia pozostają wyłącznie danymi; ich obecność nie stanowi
deklaracji poprawności kontekstowej.

Tryby niepowodzenia:

- Powielone lub brakujące identyfikatory kandydatów.
- Powielone formy lub cechy, mieszane zakresy, nieprawidłowe offsety albo brak
  kandydata zachowującego formę powierzchniową bez zmian.
- Identyfikatory kandydatów spoza dostarczonego zbioru.
- Nieprawidłowy kształt danych.

## Operacja weryfikatora propozycji (`specialist-proposal-verifier`)

`build_proposal_verifier_prompt_request(source_text, proposal_text)` akceptuje
wyłącznie:

- `{"decision": "accept"}`
- `{"decision": "reject"}`

Tryby niepowodzenia:

- Nieprawidłowa wartość decyzji.
- Dodatkowe pola w odpowiedzi.
- Jakakolwiek próba zwrócenia treści zastępczej.

## Wyprowadzone edycje

`derive_text_edits(source_text, corrected_text)` przekształca wyjście modelu w
deterministyczne, nienakładające się, półotwarte zakresy punktów kodowych Unicode
Pythona względem tekstu oryginalnego. Odrzuca nadmierne przepisywanie, edycje
dotykające opcjonalnie chronionych tokenów przypominających nazwy oraz edycje
nakładające się na jawne zakresy chronione podane przez wywołującego.

## Powierzchnia błędów rozszerzeń

Konstruktory promptów specjalistycznych i walidatory są celowo zachowawcze.
Surowy JSON i dane źródłowe nigdy nie trafiają do komunikatów walidacji. Adapter
backendu mapuje te bezpieczne dla prywatności błędy kontraktu na
`InvalidBackendResponseError` z własnym bezpiecznym identyfikatorem backendu i
kontekstem operacji, zanim wywołujący będą mogli użyć sugestii.

Starszy ogólny kontrakt znaleziska pozostaje możliwy do odczytania bez
reinterpretacji. Nowa orkiestracja specjalistyczna używa wyłącznie powyższych
operacji i musi zachować ich rozdział ról, wersje, schematy, limity i status
wyłącznie sugestii.
