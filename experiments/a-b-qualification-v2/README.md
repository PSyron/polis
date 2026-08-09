# Niezależne zbiory kwalifikacji A+B v2

Ten katalog publikuje wyłącznie metadane zamrożenia eksperymentu
`polis-a-b-qualification-v2-v1`. Teksty przypadków, odpowiedzi wzorcowe,
klucz overlap i payloady ręcznego przeglądu pozostają poza śledzonym drzewem
w `.omo/sealed/`.

Kalibracja `polis-a-b-calibration-v2-v1` zawiera 1073 niezależnie napisane
przypadki CC0: 273 błędne i 800 poprawnych. Holdout
`polis-a-b-holdout-v2-v1` zawiera 530 rozłącznych przypadków CC0: 130 błędnych
i 400 poprawnych. Odrębni autorzy, kustosze oraz recenzenci sprawdzili każdy
przypadek, jego rolę, przypisanie źródła, zakres Unicode, minimalność poprawki,
naturalność językową, proweniencję i brak danych osobowych.

Siedem reguł opartych na skończonych dopasowaniach pełnego tekstu ma tylko
1 albo 3 dopuszczalne powierzchnie błędne. Zgodnie z jawną decyzją te klucze są
strukturalnie oznaczone jako `insufficient_evidence` i nie mogą zostać
promowane. Pozostałe 13 kluczy zachowuje mianowniki 20 błędnych + 40 poprawnych
w kalibracji oraz 10 błędnych + 20 poprawnych w holdoucie.

Keyed overlap oracle porównał kanały wejściowe i poprawione obu zbiorów oraz
trzy jawne publiczne źródła. Wynik zawiera dokładnie 78 prerejestrowanych
dopasowań exact pochodzących wyłącznie ze skończonych powierzchni kalibracji,
zero innych dopasowań exact i zero dopasowań near. Holdout nie ma wyjątku.
Publiczny raport nie zawiera tekstu, identyfikatorów przypadków, HMAC-ów ani
klucza.

Pliki tworzą acykliczny łańcuch:

```text
dataset -> review -> dataset manifest -> overlap report -> freeze verification
```

Metadane nie uruchamiają kalibracji ani holdoutu. Nie wybrano jeszcze wartości
`minimum_confidence`, nie podpisano wyboru progów i nie wykonano one-shotu.
Kalibracyjny plaintext został zmaterializowany wyłącznie dla późniejszej,
powtarzalnej kalibracji po osobnej autoryzacji. Holdout pozostaje zapieczętowany
i nie wolno go otwierać przed prerejestracją, podpisaną autoryzacją oraz
odrębnym jednorazowym wykonaniem.

Narzędzie operatora jest wyłącznie repozytoryjne. Wheel i sdist produktu nie
zawierają tego katalogu, zbiorów ani runnera ewaluacyjnego.
