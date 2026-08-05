# Ryzyka runtime'u v1

| Ryzyko | Ograniczenie |
| --- | --- |
| Reguła proponuje zmianę bez lokalnego uzasadnienia | Reguły są deterministyczne; niepewność i konflikt oznaczają brak automatycznej korekty. |
| Zmiana narusza znaczenie tekstu | v1 nie koryguje intencji, faktów, czasu, aspektu, stylu ani tonu. |
| Nieprawidłowe przesunięcie uszkadza wybór poprawki | Wyniki używają zakresów `[start, end)` względem oryginalnego tekstu i są walidowane. |
| Niezgodne zachowanie reguły uzyska automatyczne uprawnienie | Polityka sprawdza pełną tożsamość źródła, kategorii, operacji, wersji zachowania i polityki. |
| Wydanie zależy od zasobu poza urządzeniem | Domyślna ścieżka jest offline i nie wymaga sieci, usługi ani procesu pomocniczego. |
| Historia badań zostanie uznana za obietnicę produktu | Dokumentacja v1 wskazuje [archiwum v2](v2-research-archive-manifest.md); historyczne dowody nie definiują funkcji runtime'u. |

Aktualne decyzje produktu ustala [ADR-0022](../architecture/decisions/0022-conservative-v1-product-scope.md).
