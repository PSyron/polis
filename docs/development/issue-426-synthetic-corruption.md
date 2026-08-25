# Issue #426 — granica korpusu syntetycznego

## Stan artefaktu

Issue #426 dostarcza generator i kontrakt odtwarzania, ale nie dodaje dużego
pliku danych do repozytorium. Generator działa wyłącznie w checkout, wymaga
opcjonalnego extra `morphology` i zapisuje tekst tylko do jawnie wskazanych
artefaktów deweloperskich.

## Granica oparta na zasobach

W checkout nie ma redystrybuowalnego podkorpusu czystego polskiego tekstu o
rozmiarze potrzebnym do bezpiecznego uzyskania co najmniej 5000 odrębnych
mutacji we wszystkich czterech klasach. Dostępne pliki ewaluacyjne są małymi,
autorskimi zbiorami kontraktowymi; zamrożone i zużyte holdouty są poza zakresem
i nie były używane do budowy tego generatora.

To jest granica wejścia, nie ciche obniżenie kryterium: `generate_synthetic_corpus`
odrzuca źródło bez kandydata w dowolnej klasie albo z mniejszą liczbą bezpiecznych
kandydatów niż `pair_count`. Nie powiela kandydatów, nie tworzy form
morfologicznych ręcznie i nie dopisuje tekstu, którego nie ma w źródle.

## Dowody kontraktu

- test deterministyczności wiąże ten sam seed z tym samym SHA-256 kanonicznych
  bajtów;
- testy przechodzą po całym wygenerowanym zbiorze i odwracają każdą edycję w
  pełnym tekście źródłowym;
- test klasy morfologicznej sprawdza, że forma błędna jest elementem wyników
  `generate()` dla tego samego lematu;
- test z kwalifikowanym Morfeuszem potwierdza obecność wszystkich klas;
- test deweloperski generuje 5000 par z odpowiednio dużego źródła testowego,
  bez powtarzania offsetów źródłowych;
- test pakowania sprawdza wykluczenie modułu generatora z wheel i sdist.

Po dostarczeniu legalnego, lokalnego źródła komenda z
`docs/evaluation-dataset.md` odtworzy wymagane 5000 lub więcej par i zapisze
manifest z licencją, proweniencją, SHA źródła, parametrami i SHA korpusu.
